"""Routes: webhooks.

PayMongo webhook handling for:
  1. Participant payments (single + bulk, one PayMongo link -> many rows)
  2. Cash sponsorship payments
  3. Store / cart payments

The webhook is the ONLY place that marks payments as Paid and syncs
participant item statuses (GET /payment_status is read-only).
"""

import datetime
import hashlib
import hmac
import json
import time
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import (
    PAYMONGO_LIVE,
    PAYMONGO_WEBHOOK_SECRET,
)
from app.database import get_db
from app.models import (
    CashDonationTotal,
    CashSponsorship,
    Participant,
    Payment,
    StoreItem,
)
from app.services.email import (
    send_cash_sponsorship_confirmation_email,
    send_participant_payment_confirmation_email,
    send_store_payment_receipt_email,
)

router = APIRouter()

SIGNATURE_TOLERANCE_SECONDS = 300

PAID_EVENT_TYPES = {
    "payment.paid",
    "link.payment.paid",
}


@router.get("/webhooks/paymongo")
async def paymongo_webhook_test():
    return {
        "ok": True,
        "mode": "live" if PAYMONGO_LIVE else "test",
        "message": "PayMongo webhook endpoint is reachable"
    }


# ======================================================
# SMALL HELPERS
# ======================================================

def _norm(value) -> str:
    return str(value or "").strip().lower()


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _clean(value):
    if value is None:
        return None

    text = str(value).strip()

    return text or None


def _to_int(value, default=0) -> int:
    try:
        return int(value or 0)
    except (ValueError, TypeError):
        return default


def _reject(status_code: int, message: str):
    """Hard rejection (bad / unauthenticated request)."""

    return JSONResponse(
        status_code=status_code,
        content={
            "received": False,
            "processed": False,
            "message": message
        }
    )


def _skip(message: str, **extra):
    """
    Authentic event that we could not (or should not) process.
    Returns HTTP 200 so PayMongo does not keep retrying.
    """

    return {
        "received": True,
        "processed": False,
        "message": message,
        **extra
    }


def _server_error(message: str, **extra):
    return JSONResponse(
        status_code=500,
        content={
            "received": True,
            "processed": False,
            "message": message,
            **extra
        }
    )


def _parse_id_list(raw) -> list:
    """Accepts a list, a JSON array string, or 'a,b,c'."""

    if not raw:
        return []

    if isinstance(raw, str):

        text = raw.strip()

        if text.startswith("["):
            try:
                raw = json.loads(text)
            except Exception:
                raw = []
        else:
            raw = text.split(",")

    if not isinstance(raw, (list, tuple)):
        raw = [raw]

    ids = []

    for value in raw:
        try:
            ids.append(int(str(value).strip()))
        except (ValueError, TypeError):
            continue

    return list(dict.fromkeys(ids))


def _find_first(db: Session, model, candidates):
    """
    Try (attribute, value) pairs in order and return the first row
    found. Pairs with an empty value or an unknown attribute are skipped.
    """

    for attr, value in candidates:

        if value in (None, "") or not hasattr(model, attr):
            continue

        row = (
            db.query(model)
            .filter(getattr(model, attr) == value)
            .order_by(model.id.asc())
            .first()
        )

        if row:
            return row

    return None


def _lock_payments(db: Session, payment_type: str, *conditions):
    """Load AND lock payment rows of one type."""

    return (
        db.query(Payment)
        .filter(
            Payment.payment_type.ilike(payment_type),
            *conditions
        )
        .order_by(Payment.id.asc())
        .with_for_update()
        .all()
    )


def _save_paymongo_ids(row, link_id, payment_id, reference) -> None:

    if link_id and hasattr(row, "paymongo_link_id"):
        row.paymongo_link_id = link_id

    if payment_id and hasattr(row, "paymongo_payment_id"):
        row.paymongo_payment_id = payment_id

    if reference and hasattr(row, "paymongo_reference"):
        row.paymongo_reference = reference


def _commit_quietly(db: Session) -> None:

    try:
        db.commit()
    except Exception:
        db.rollback()


# ======================================================
# SIGNATURE VERIFICATION
#
# Signed payload is "<timestamp>.<raw body>" (HMAC-SHA256).
# The Paymongo-Signature header carries:
#   t  = timestamp
#   te = signature for TEST mode events
#   li = signature for LIVE mode events
#
# The signature is picked by the SERVER's mode, so a test-mode
# event can never be accepted by a live server (and vice versa).
# ======================================================

def _verify_signature(raw_body: bytes, header):
    """Returns None when valid, otherwise a JSONResponse to send back."""

    if not header:
        return _reject(401, "Missing PayMongo signature.")

    parts = {}

    for item in header.split(","):

        if "=" not in item:
            continue

        key, value = item.split("=", 1)
        parts[key.strip()] = value.strip()

    timestamp = parts.get("t")

    if not timestamp:
        return _reject(401, "Missing webhook timestamp.")

    try:
        timestamp_int = int(timestamp)
    except ValueError:
        return _reject(401, "Invalid webhook timestamp.")

    difference = abs(int(time.time()) - timestamp_int)

    if difference > SIGNATURE_TOLERANCE_SECONDS:
        print("Webhook timestamp expired. Difference:", difference)
        return _reject(401, "Webhook timestamp expired.")

    if not PAYMONGO_WEBHOOK_SECRET:
        print("PAYMONGO_WEBHOOK_SECRET is missing.")
        return _reject(500, "Webhook secret is not configured.")

    expected_signature = hmac.new(
        PAYMONGO_WEBHOOK_SECRET.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + raw_body,
        hashlib.sha256
    ).hexdigest()

    provided_signature = (
        parts.get("li", "")
        if PAYMONGO_LIVE
        else parts.get("te", "")
    )

    if not provided_signature:
        print(
            "No signature for this server mode "
            f"({'live' if PAYMONGO_LIVE else 'test'})."
        )
        return _reject(401, "Missing signature value for this mode.")

    if not hmac.compare_digest(expected_signature, provided_signature):
        print("Invalid PayMongo signature.")
        return _reject(401, "Invalid PayMongo webhook signature.")

    return None


# ======================================================
# CASH SPONSORSHIP
# ======================================================

async def _handle_sponsorship(db: Session, sponsorship, ctx):

    print("CASH SPONSORSHIP FOUND:", sponsorship.id)

    # Lock the row BEFORE the "already paid" check, so two concurrent
    # deliveries cannot both add the donation to the running total.
    locked = (
        db.query(CashSponsorship)
        .filter(CashSponsorship.id == sponsorship.id)
        .with_for_update()
        .first()
    )

    if locked is not None:
        sponsorship = locked

    _save_paymongo_ids(
        sponsorship,
        ctx.link_id,
        ctx.payment_id,
        ctx.reference
    )

    if _norm(getattr(sponsorship, "payment_status", "")) == "paid":

        _commit_quietly(db)

        print("Sponsorship already Paid.")

        return {
            "received": True,
            "processed": True,
            "already_processed": True,
            "payment_type": "sponsor_package",
            "event_id": ctx.event_id,
            "sponsorship_id": sponsorship.id,
            "payment_status": "Paid"
        }

    donation_amount = _to_int(getattr(sponsorship, "donation_amount", 0))

    if donation_amount <= 0:

        db.rollback()

        return _skip(
            "Invalid sponsorship amount.",
            payment_type="sponsor_package",
            sponsorship_id=sponsorship.id
        )

    if ctx.amount > 0 and ctx.amount != donation_amount:

        print("SPONSORSHIP AMOUNT MISMATCH")

        db.rollback()

        return _skip(
            "Payment amount does not match sponsorship amount.",
            payment_type="sponsor_package",
            sponsorship_id=sponsorship.id,
            paymongo_amount=ctx.amount,
            expected_amount=donation_amount
        )

    donation_pesos = donation_amount / 100
    now = datetime.datetime.now()

    donation_total = (
        db.query(CashDonationTotal)
        .order_by(CashDonationTotal.id.asc())
        .with_for_update()
        .first()
    )

    if not donation_total:
        donation_total = CashDonationTotal(total_amount=0)
        db.add(donation_total)
        db.flush()

    try:
        current_total = float(donation_total.total_amount or 0)
    except (ValueError, TypeError):
        current_total = 0.0

    new_total = current_total + donation_pesos

    donation_total.total_amount = new_total

    if hasattr(donation_total, "updated_at"):
        donation_total.updated_at = now

    sponsorship.payment_status = "Paid"

    if hasattr(sponsorship, "donation_status"):
        sponsorship.donation_status = "Paid"

    if hasattr(sponsorship, "paid_at"):
        sponsorship.paid_at = now

    if hasattr(sponsorship, "updated_at"):
        sponsorship.updated_at = now

    if hasattr(sponsorship, "cash_total_added"):
        sponsorship.cash_total_added = donation_pesos

    try:
        db.commit()

    except Exception as e:

        db.rollback()

        print("Sponsorship commit failed:", repr(e))

        return _server_error("Sponsorship database update failed.")

    gmail_success = False

    try:

        if getattr(sponsorship, "email", None):

            gmail_success = bool(
                await send_cash_sponsorship_confirmation_email(
                    sponsorship,
                    sponsorship
                )
            )

            print("Sponsorship Gmail:", gmail_success)

    except Exception as e:

        print("Sponsorship Gmail failed:", repr(e))

    return {
        "received": True,
        "processed": True,
        "payment_type": "sponsor_package",
        "event_id": ctx.event_id,
        "sponsorship_id": sponsorship.id,
        "payment_status": "Paid",
        "donation_amount": donation_pesos,
        "donation_amount_display": f"₱{donation_pesos:,.2f}",
        "cash_donation_total": new_total,
        "cash_donation_total_display": f"₱{new_total:,.2f}",
        "paymongo_reference": ctx.reference,
        "paymongo_payment_id": ctx.payment_id,
        "paymongo_link_id": ctx.link_id,
        "gmail_sent": gmail_success
    }


# ======================================================
# PARTICIPANT / BULK PARTICIPANT
#
# /create_payment saves one Payment row per participant and
# ONE PayMongo link for the combined amount. All rows share
# paymongo_link_id, which is how they are found here.
# ======================================================

async def _handle_participant(db: Session, payment, payment_type, ctx):

    print("PROCESSING PARTICIPANT PAYMENT | type:", payment_type)

    rows = []

    # 1. Exact payment IDs (only present if metadata is available)
    if ctx.payment_ids:
        rows = _lock_payments(
            db, "Participant", Payment.id.in_(ctx.payment_ids)
        )

    # 2. Shared PayMongo link (normal path for Links)
    if not rows and ctx.link_id:
        rows = _lock_payments(
            db, "Participant", Payment.paymongo_link_id == ctx.link_id
        )

    # 3. Reference
    if not rows and ctx.reference:
        rows = _lock_payments(
            db, "Participant", Payment.paymongo_reference == ctx.reference
        )

    # 4. The single row we already matched
    if not rows and getattr(payment, "participant_id", None):
        rows = [payment]

    if not rows:

        db.rollback()

        return _skip(
            "No participant payment rows found.",
            payment_type=payment_type
        )

    rows = sorted(
        {row.id: row for row in rows}.values(),
        key=lambda row: row.id
    )

    # If payment_ids were supplied, never process only part of a bulk.
    if ctx.payment_ids:

        found_ids = {row.id for row in rows}

        missing_ids = [
            pid for pid in ctx.payment_ids
            if pid not in found_ids
        ]

        if missing_ids:

            print("Missing participant payment IDs:", missing_ids)

            recovered = []

            if ctx.link_id:
                recovered = _lock_payments(
                    db,
                    "Participant",
                    Payment.paymongo_link_id == ctx.link_id
                )

            recovered_ids = {row.id for row in recovered}

            if recovered and all(
                pid in recovered_ids for pid in ctx.payment_ids
            ):

                rows = sorted(recovered, key=lambda row: row.id)

            else:

                db.rollback()

                return _skip(
                    "Not all bulk participant payment rows were found.",
                    payment_type=payment_type,
                    payment_ids=ctx.payment_ids,
                    missing_payment_ids=missing_ids
                )

    # Verify the combined amount
    expected_amount = 0

    for row in rows:

        row_amount = _to_int(getattr(row, "amount", 0))

        if row_amount <= 0:

            db.rollback()

            return _skip(
                "Invalid participant payment amount.",
                payment_type=payment_type,
                payment_id=row.id
            )

        expected_amount += row_amount

    print(
        "AMOUNT CHECK | PayMongo:", ctx.amount,
        "| Expected:", expected_amount
    )

    if ctx.amount > 0 and ctx.amount != expected_amount:

        print("PARTICIPANT PAYMENT AMOUNT MISMATCH")

        db.rollback()

        return _skip(
            "Payment amount does not match participant payment total.",
            payment_type=payment_type,
            paymongo_amount=ctx.amount,
            expected_amount=expected_amount,
            payment_ids=[row.id for row in rows]
        )

    # ------------------------------------------------------
    # PROCESS EACH ROW
    # ------------------------------------------------------

    now = datetime.datetime.now()

    # Rows that flip to Paid in THIS delivery. Only these get emails,
    # so retries / duplicate events never resend confirmations.
    newly_paid_ids = set()

    participants_by_row = {}

    for row in rows:

        participant_id = getattr(row, "participant_id", None)

        if not participant_id:

            db.rollback()

            return _skip(
                "Participant ID is missing.",
                payment_type=payment_type,
                payment_id=row.id
            )

        participant = (
            db.query(Participant)
            .filter(Participant.id == participant_id)
            .with_for_update()
            .first()
        )

        if not participant:

            db.rollback()

            return _skip(
                "Participant not found.",
                payment_type=payment_type,
                payment_id=row.id,
                participant_id=participant_id
            )

        participants_by_row[row.id] = participant

        # The local Payment row is the source of truth for items
        tshirt_selected = bool(getattr(row, "tshirt_selected", False))
        lanyard_selected = bool(getattr(row, "lanyard_selected", False))
        tshirt_size = getattr(row, "tshirt_size", None)

        _save_paymongo_ids(
            row,
            ctx.link_id,
            ctx.payment_id,
            ctx.reference
        )

        # Idempotent: a repeat delivery leaves the row Paid
        previous_status = _norm(getattr(row, "status", ""))

        if previous_status != "paid":
            newly_paid_ids.add(row.id)

        row.status = "Paid"

        if hasattr(row, "paid_at") and (
            previous_status != "paid" or not row.paid_at
        ):
            row.paid_at = now

        # Participant item statuses are ALWAYS synced (repairs cases
        # where Payment is Paid but Participant is still Pending).
        if tshirt_selected:

            if hasattr(participant, "tshirt_status"):
                participant.tshirt_status = "Paid"

            if tshirt_size and hasattr(participant, "tshirt_size"):
                participant.tshirt_size = tshirt_size

        if lanyard_selected:

            if hasattr(participant, "lanyard_status"):
                participant.lanyard_status = "Paid"
            else:
                print("WARNING: Participant has no lanyard_status column.")

        # Lanyard is mandatory -> it decides registration status.
        # Never force Pending here.
        if (
            hasattr(participant, "registration_status")
            and _norm(getattr(participant, "lanyard_status", "")) == "paid"
        ):
            participant.registration_status = "Confirmed"

        if hasattr(participant, "updated_at"):
            participant.updated_at = now

    # One transaction for everything
    try:

        db.flush()
        db.commit()

        print(
            "PARTICIPANT PAYMENT UPDATE SUCCESSFUL | rows:",
            len(rows),
            "| newly paid:",
            len(newly_paid_ids)
        )

    except Exception as e:

        db.rollback()

        print("Participant commit failed:", repr(e))

        return _server_error(
            "Participant database update failed.",
            payment_type=payment_type
        )

    # ------------------------------------------------------
    # FINAL STATE (re-read after commit)
    # ------------------------------------------------------

    final_participants = []

    for row in rows:

        participant = participants_by_row.get(row.id)

        if not participant:
            continue

        lanyard_status = getattr(participant, "lanyard_status", None)

        final_participants.append({
            "payment_id": row.id,
            "participant_id": participant.id,
            "registration_number": getattr(
                participant, "registration_number", None
            ),
            "payment_status": row.status,
            "tshirt_selected": bool(getattr(row, "tshirt_selected", False)),
            "tshirt_status": getattr(participant, "tshirt_status", None),
            "lanyard_selected": bool(getattr(row, "lanyard_selected", False)),
            "lanyard_status": lanyard_status,
            "lanyard_paid": _norm(lanyard_status) == "paid",
            "registration_status": getattr(
                participant, "registration_status", None
            )
        })

    # ------------------------------------------------------
    # EMAILS (newly paid rows only)
    #
    # A failed email must NOT undo a successful payment.
    # ------------------------------------------------------

    email_results = []

    for row in rows:

        if row.id not in newly_paid_ids:
            continue

        participant = participants_by_row.get(row.id)

        if not participant:
            continue

        if not getattr(participant, "email", None):

            print("Participant Gmail skipped: no email.", participant.id)

            email_results.append({
                "participant_id": participant.id,
                "sent": False
            })

            continue

        sent = False

        try:

            sent = bool(
                await send_participant_payment_confirmation_email(
                    participant,
                    row
                )
            )

            print("Participant Gmail Result:", participant.id, sent)

        except Exception as e:

            print("Participant Gmail failed:", participant.id, repr(e))

        email_results.append({
            "participant_id": participant.id,
            "sent": sent
        })

    all_rows_paid = all(
        _norm(getattr(row, "status", "")) == "paid"
        for row in rows
    )

    all_lanyards_paid = all(
        item.get("lanyard_paid", False)
        for item in final_participants
    )

    is_bulk = len(rows) > 1 or payment_type == "bulk"

    return {
        "received": True,
        "processed": True,
        "already_processed": len(newly_paid_ids) == 0,
        "payment_type": "bulk" if is_bulk else "participant",
        "event_id": ctx.event_id,
        "payment_id": payment.id,
        "payment_ids": [row.id for row in rows],
        "participant_ids": [row.participant_id for row in rows],
        "participant_count": len(rows),
        "participants": final_participants,
        "payment_status": "Paid" if all_rows_paid else "Pending",
        "payment_success": all_rows_paid,
        "all_lanyards_paid": all_lanyards_paid,
        "paymongo_amount": ctx.amount,
        "expected_amount": expected_amount,
        "paymongo_reference": ctx.reference,
        "paymongo_payment_id": ctx.payment_id,
        "paymongo_link_id": ctx.link_id,
        "email_results": email_results
    }


# ======================================================
# STORE (ONE CART = ONE LINK, ONE ITEM = ONE ROW)
# ======================================================

async def _handle_store(db: Session, payment, ctx):

    print("PROCESSING STORE PAYMENT")

    store_order_id = ctx.store_order_id or _clean(
        getattr(payment, "store_order_id", None)
    )

    if not store_order_id:

        db.rollback()

        return _skip(
            "Store order ID is missing.",
            payment_type="store",
            payment_id=payment.id
        )

    store_payments = (
        db.query(Payment)
        .filter(
            Payment.store_order_id == store_order_id,
            Payment.payment_type.ilike("Store")
        )
        .order_by(Payment.id.asc())
        .with_for_update()
        .all()
    )

    if not store_payments and ctx.link_id:
        store_payments = _lock_payments(
            db, "Store", Payment.paymongo_link_id == ctx.link_id
        )

    if not store_payments:

        db.rollback()

        return _skip(
            "No store payment rows found for this order.",
            payment_type="store",
            store_order_id=store_order_id
        )

    print("Store payment rows:", len(store_payments))

    for store_payment in store_payments:
        _save_paymongo_ids(
            store_payment,
            ctx.link_id,
            ctx.payment_id,
            ctx.reference
        )

    # Cart total
    expected_cart_amount = 0

    for store_payment in store_payments:

        row_amount = _to_int(getattr(store_payment, "amount", 0))

        if row_amount <= 0:

            db.rollback()

            return _skip(
                "Invalid store payment row amount.",
                payment_type="store",
                store_order_id=store_order_id,
                payment_id=store_payment.id
            )

        expected_cart_amount += row_amount

    if ctx.amount > 0 and ctx.amount != expected_cart_amount:

        print("STORE CART AMOUNT MISMATCH")

        db.rollback()

        return _skip(
            "Payment amount does not match the store cart total.",
            payment_type="store",
            store_order_id=store_order_id,
            paymongo_amount=ctx.amount,
            expected_amount=expected_cart_amount
        )

    unpaid_payments = [
        p for p in store_payments
        if _norm(getattr(p, "status", "")) != "paid"
    ]

    # Duplicate delivery: nothing left to do. The receipt was already
    # sent when the order first became Paid, so do NOT resend it.
    if not unpaid_payments:

        _commit_quietly(db)

        return {
            "received": True,
            "processed": True,
            "already_processed": True,
            "payment_type": "store",
            "store_order_id": store_order_id,
            "payment_id": payment.id,
            "payment_ids": [p.id for p in store_payments],
            "payment_status": "Paid",
            "payment_success": True,
            "store_receipt_email_sent": False
        }

    # Validate ALL inventory before changing anything
    store_items_to_update = []

    for store_payment in unpaid_payments:

        store_item_id = getattr(store_payment, "store_item_id", None)

        if not store_item_id:

            db.rollback()

            return _skip(
                "Store item ID is missing.",
                payment_type="store",
                store_order_id=store_order_id,
                payment_id=store_payment.id
            )

        store_quantity = _to_int(
            getattr(store_payment, "store_quantity", 1) or 1,
            default=0
        )

        if store_quantity <= 0:

            db.rollback()

            return _skip(
                "Invalid store quantity.",
                payment_type="store",
                store_order_id=store_order_id,
                payment_id=store_payment.id
            )

        store_item = (
            db.query(StoreItem)
            .filter(StoreItem.id == store_item_id)
            .with_for_update()
            .first()
        )

        if not store_item:

            db.rollback()

            return _skip(
                "Store item not found.",
                payment_type="store",
                store_order_id=store_order_id,
                payment_id=store_payment.id,
                store_item_id=store_item_id
            )

        current_inventory = _to_int(store_item.quantity)

        if current_inventory < store_quantity:

            db.rollback()

            return _skip(
                "Insufficient inventory.",
                payment_type="store",
                store_order_id=store_order_id,
                payment_id=store_payment.id,
                store_item_id=store_item.id,
                item_name=store_item.item_name,
                requested_quantity=store_quantity,
                available_quantity=current_inventory
            )

        store_items_to_update.append({
            "payment": store_payment,
            "store_item": store_item,
            "quantity": store_quantity
        })

    # Apply
    processed_items = []

    now = datetime.datetime.now()

    for entry in store_items_to_update:

        store_payment = entry["payment"]
        store_item = entry["store_item"]
        store_quantity = entry["quantity"]

        store_payment.status = "Paid"

        if hasattr(store_payment, "paid_at"):
            store_payment.paid_at = now

        store_item.quantity = _to_int(store_item.quantity) - store_quantity

        if hasattr(store_item, "updated_at"):
            store_item.updated_at = now

        processed_items.append({
            "payment_id": store_payment.id,
            "store_item_id": store_item.id,
            "item_name": store_item.item_name,
            "quantity": store_quantity,
            "remaining_inventory": store_item.quantity,
            "payment_status": store_payment.status
        })

    try:
        db.commit()

    except Exception as e:

        db.rollback()

        print("Store commit failed:", repr(e))

        return _server_error(
            "Store cart database update failed.",
            payment_type="store",
            store_order_id=store_order_id
        )

    final_order_status = (
        "Paid"
        if all(
            _norm(getattr(p, "status", "")) == "paid"
            for p in store_payments
        )
        else "Pending"
    )

    # Receipt: only here, when the order has just become fully Paid
    store_receipt_sent = False

    try:

        if final_order_status == "Paid":

            store_receipt_sent = bool(
                await send_store_payment_receipt_email(
                    store_payments,
                    store_order_id
                )
            )

        else:
            print("STORE RECEIPT EMAIL SKIPPED: order is not fully Paid")

    except Exception as e:

        print("STORE RECEIPT EMAIL FAILED:", repr(e))

    print(
        "STORE PAYMENT COMPLETED | order:", store_order_id,
        "| rows:", len(store_payments),
        "| status:", final_order_status
    )

    return {
        "received": True,
        "processed": True,
        "payment_type": "store",
        "event_id": ctx.event_id,
        "store_order_id": store_order_id,
        "payment_id": payment.id,
        "payment_ids": [p.id for p in store_payments],
        "item_count": len(store_payments),
        "items": processed_items,
        "paymongo_amount": ctx.amount,
        "expected_cart_amount": expected_cart_amount,
        "total_amount": expected_cart_amount / 100,
        "payment_status": final_order_status,
        "payment_success": final_order_status == "Paid",
        "store_receipt_email_sent": store_receipt_sent,
        "paymongo_reference": ctx.reference,
        "paymongo_payment_id": ctx.payment_id,
        "paymongo_link_id": ctx.link_id
    }


# ======================================================
# PAYMONGO WEBHOOK ENTRY POINT
# ======================================================

@router.post("/webhooks/paymongo")
async def paymongo_webhook(
    request: Request,
    db: Session = Depends(get_db)
):

    print("=" * 80)
    print(
        "PAYMONGO WEBHOOK RECEIVED (server mode:",
        "LIVE)" if PAYMONGO_LIVE else "TEST)"
    )

    # 1. Raw body
    try:
        raw_body = await request.body()
    except Exception as e:
        print("Webhook body read failed:", repr(e))
        return _reject(400, "Unable to read webhook body.")

    if not raw_body:
        return _reject(400, "Empty webhook body.")

    # 2. Signature (chosen by server mode)
    rejection = _verify_signature(
        raw_body,
        request.headers.get("Paymongo-Signature")
    )

    if rejection is not None:
        return rejection

    print("Webhook signature verified.")

    # 3. JSON
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        print("JSON parse failed:", repr(e))
        return _reject(400, "Invalid JSON payload.")

    # 4. Event
    event_data = _as_dict(_as_dict(payload).get("data"))
    event_id = event_data.get("id")
    event_attributes = _as_dict(event_data.get("attributes"))
    event_type = event_attributes.get("type")
    livemode = event_attributes.get("livemode")

    print("Event:", event_id, "|", event_type, "| livemode:", livemode)

    # Wrong-mode event (e.g. a test event reaching a live server)
    if livemode is not None and bool(livemode) != PAYMONGO_LIVE:

        print("Event ignored: livemode does not match server mode.")

        return {
            "received": True,
            "processed": False,
            "event_id": event_id,
            "message": "Event livemode does not match server mode."
        }

    if event_type not in PAID_EVENT_TYPES:

        print("Event ignored:", event_type)

        return {
            "received": True,
            "processed": False,
            "event_id": event_id,
            "event_type": event_type,
            "message": "Event ignored."
        }

    # 5. Resource + identifiers
    resource = _as_dict(event_attributes.get("data"))
    resource_id = resource.get("id")
    resource_attributes = _as_dict(resource.get("attributes"))
    metadata = _as_dict(resource_attributes.get("metadata"))

    # NOTE: PayMongo Links do not carry metadata, so matching normally
    # falls through to paymongo_link_id / reference. Metadata is still
    # honoured when present (e.g. for other integrations).
    ctx = SimpleNamespace(
        event_id=event_id,

        sponsorship_id=_clean(metadata.get("sponsorship_id")),

        store_order_id=_clean(
            metadata.get("store_order_id")
            or metadata.get("order_id")
        ),

        internal_payment_id=_clean(metadata.get("payment_id")),

        payment_ids=_parse_id_list(metadata.get("payment_ids")),

        reference=_clean(
            metadata.get("pm_reference_number")
            or metadata.get("reference_number")
            or resource_attributes.get("external_reference_number")
            or resource_attributes.get("reference_number")
        ),

        payment_id=_clean(
            resource_id
            if event_type == "payment.paid"
            else None
        ) or _clean(metadata.get("paymongo_payment_id")),

        link_id=(
            _clean(resource_id if event_type == "link.payment.paid" else None)
            or _clean(metadata.get("paymongo_link_id"))
            or _clean(resource_attributes.get("link_id"))
        ),

        amount=_to_int(resource_attributes.get("amount")),
    )

    print(
        "IDs | link:", ctx.link_id,
        "| payment:", ctx.payment_id,
        "| reference:", ctx.reference,
        "| store_order:", ctx.store_order_id,
        "| payment_ids:", ctx.payment_ids,
        "| amount:", ctx.amount
    )

    # 6. Cash sponsorship?
    cash_sponsorship = _find_first(
        db,
        CashSponsorship,
        [
            ("id", _to_int(ctx.sponsorship_id) or None),
            ("paymongo_reference", ctx.reference),
            ("paymongo_payment_id", ctx.payment_id),
            ("paymongo_link_id", ctx.link_id),
        ]
    )

    if cash_sponsorship:
        return await _handle_sponsorship(db, cash_sponsorship, ctx)

    # 7. Otherwise find a Payment row
    payment = None

    if ctx.payment_ids:
        payment = (
            db.query(Payment)
            .filter(Payment.id.in_(ctx.payment_ids))
            .order_by(Payment.id.asc())
            .first()
        )

    if not payment:
        payment = _find_first(
            db,
            Payment,
            [
                ("store_order_id", ctx.store_order_id),
                ("id", _to_int(ctx.internal_payment_id) or None),
                ("paymongo_reference", ctx.reference),
                ("paymongo_payment_id", ctx.payment_id),
                ("paymongo_link_id", ctx.link_id),
            ]
        )

    if not payment:

        print("NO LOCAL PAYMENT FOUND")

        return {
            "received": True,
            "processed": False,
            "event_id": event_id,
            "payment_ids": ctx.payment_ids,
            "paymongo_reference": ctx.reference,
            "paymongo_payment_id": ctx.payment_id,
            "paymongo_link_id": ctx.link_id,
            "message": "No matching local payment found."
        }

    payment_type = _norm(getattr(payment, "payment_type", ""))

    print("LOCAL PAYMENT FOUND:", payment.id, "| type:", payment_type)

    # 8. Dispatch
    # /create_payment saves payment_type="Participant" for both single
    # and bulk payments; "bulk" / "single" are accepted for safety.
    if payment_type in {"participant", "bulk", "single"}:
        return await _handle_participant(db, payment, payment_type, ctx)

    if payment_type == "store":
        return await _handle_store(db, payment, ctx)

    db.rollback()

    print("UNSUPPORTED PAYMENT TYPE:", payment_type)

    return _skip(
        "Payment type is not supported.",
        payment_id=payment.id,
        payment_type=payment_type
    )