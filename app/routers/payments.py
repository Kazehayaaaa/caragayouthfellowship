"""Routes: payments."""

import datetime
import uuid
from typing import List

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import (
    ADMIN_SESSION_KEY,
    PAYMONGO_API_URL,
    PAYMONGO_LIVE,
    PAYMONGO_SECRET_KEY,
)
from app.database import get_db
from app.models import (
    Participant,
    Payment,
    RegistrationItem,
)
from app.schemas import (
    PaymentCreateSchema,
    PaymentResponse,
)

router = APIRouter()

# Statuses that count as a completed payment.
SUCCESSFUL_STATUSES = {
    "paid",
    "success",
    "succeeded",
    "completed"
}

ALLOWED_TSHIRT_SIZES = {
    "S",
    "M",
    "L",
    "XL",
    "2XL"
}


# ======================================================
# SMALL HELPERS
# ======================================================

def _norm(value) -> str:
    return str(value or "").strip().lower()


def _normalize_bool(value):

    if isinstance(value, bool):
        return value

    if value is None:
        return False

    if isinstance(value, int):
        return value != 0

    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "1",
            "yes",
            "on",
            "selected",
            "checked"
        }

    return bool(value)


def require_admin(request: Request):
    """
    Guard for admin-only list endpoints.

    Enforced only when ADMIN_SESSION_KEY is configured. Adapt this to
    your real auth (for example, check a role in request.session).
    """

    if not ADMIN_SESSION_KEY:
        return

    if not request.session.get(ADMIN_SESSION_KEY):
        raise HTTPException(
            status_code=401,
            detail="Admin authentication required."
        )


def _link_matches_mode(checkout_url: str) -> bool:
    """
    Test-mode PayMongo links contain '/test/' in the URL
    (for example https://pm.link/org-xxx/test/abc123).
    A link only matches if its mode equals the server's mode.
    """

    is_test_link = "/test/" in (checkout_url or "")

    return is_test_link == (not PAYMONGO_LIVE)


def _find_items(db: Session):
    """Return (tshirt_item, lanyard_item) from active RegistrationItems."""

    items = (
        db.query(RegistrationItem)
        .filter(RegistrationItem.is_active == True)
        .all()
    )

    def find(name):
        return next(
            (
                item for item in items
                if item.item_name
                and item.item_name.strip().lower() == name
            ),
            None
        )

    return find("t-shirt"), find("lanyard")


def _paid_flags(participant, payments):
    """
    Work out which items a participant has paid for.

    Successful Payment rows count, and an admin-set participant status
    of 'paid' also counts. The same rule is used by /payment_status and
    /create_payment so they can never disagree.
    """

    tshirt_paid = any(
        bool(getattr(p, "tshirt_selected", False))
        and _norm(getattr(p, "status", "")) in SUCCESSFUL_STATUSES
        for p in payments
    )

    lanyard_paid = any(
        bool(getattr(p, "lanyard_selected", False))
        and _norm(getattr(p, "status", "")) in SUCCESSFUL_STATUSES
        for p in payments
    )

    if _norm(getattr(participant, "tshirt_status", "")) == "paid":
        tshirt_paid = True

    if _norm(getattr(participant, "lanyard_status", "")) == "paid":
        lanyard_paid = True

    return tshirt_paid, lanyard_paid


def _discard_payment_rows(db: Session) -> None:
    """
    Throw away the uncommitted local payment rows.

    Rows are only flushed (not committed) until PayMongo succeeds, so a
    rollback leaves no 'Failed' clutter in the payment history.
    """

    try:
        db.rollback()
    except Exception as e:
        print("ROLLBACK FAILED:", repr(e))


# ======================================================
# VIEW PARTICIPANT PAYMENT STATUS
#
# READ-ONLY. Statuses are written by the PayMongo webhook.
# ======================================================

@router.get("/payment_status/{participant_id}")
def payment_status(
    participant_id: int,
    db: Session = Depends(get_db)
):

    participant = (
        db.query(Participant)
        .filter(
            Participant.id == participant_id,
            Participant.is_archived == 0
        )
        .first()
    )

    if not participant:
        raise HTTPException(
            status_code=404,
            detail="Participant not found."
        )

    fullname = " ".join(
        part
        for part in [
            participant.fname,
            participant.mname,
            participant.lname
        ]
        if part and str(part).strip()
    ).strip()

    # Items and prices come from the database
    tshirt_item, lanyard_item = _find_items(db)

    tshirt_price = int(tshirt_item.price or 0) if tshirt_item else 0
    lanyard_price = int(lanyard_item.price or 0) if lanyard_item else 0

    payments = (
        db.query(Payment)
        .filter(Payment.participant_id == participant.id)
        .order_by(
            Payment.created_at.desc(),
            Payment.id.desc()
        )
        .all()
    )

    tshirt_paid, lanyard_paid = _paid_flags(participant, payments)

    # Lanyard is mandatory. T-shirt is optional.
    mandatory_payment_complete = (
        lanyard_paid
        if lanyard_item
        else True
    )

    paid_items = []
    registration_item_names = []
    remaining_items = []
    remaining_amount = 0

    if tshirt_item:
        registration_item_names.append("T-Shirt")

        if tshirt_paid:
            paid_items.append("T-Shirt")
        else:
            remaining_items.append("T-Shirt")
            remaining_amount += tshirt_price

    if lanyard_item:
        registration_item_names.append("Lanyard")

        if lanyard_paid:
            paid_items.append("Lanyard")
        else:
            remaining_items.append("Lanyard")
            remaining_amount += lanyard_price

    all_items_paid = (
        len(registration_item_names) > 0
        and len(remaining_items) == 0
    )

    can_proceed_to_payment = (
        len(remaining_items) > 0
        and remaining_amount > 0
    )

    payment_success = mandatory_payment_complete

    # Display-only: the webhook is what actually persists "Confirmed".
    registration_status = getattr(
        participant,
        "registration_status",
        None
    )

    if mandatory_payment_complete:
        registration_status = "Confirmed"

    # Keep the newest successful payment per item combination
    history_payments = []
    seen_payment_combinations = set()

    for p in payments:

        combination = (
            bool(getattr(p, "tshirt_selected", False)),
            bool(getattr(p, "lanyard_selected", False))
        )

        if _norm(getattr(p, "status", "")) in SUCCESSFUL_STATUSES:

            if combination in seen_payment_combinations:
                continue

            seen_payment_combinations.add(combination)

        history_payments.append(p)

    print(
        f"[payment_status] participant={participant.id} "
        f"tshirt_paid={tshirt_paid} lanyard_paid={lanyard_paid} "
        f"remaining={remaining_items} amount={remaining_amount}"
    )

    return {

        # PARTICIPANT
        "participant_id": participant.id,
        "registration_number": participant.registration_number,
        "fullname": fullname,
        "participant_type": participant.participant_type,

        # MAIN PAYMENT FLAGS
        "mandatory_payment_complete": mandatory_payment_complete,
        "payment_success": payment_success,
        "all_items_paid": all_items_paid,
        "can_proceed_to_payment": can_proceed_to_payment,

        # ITEM LISTS
        "paid_items": paid_items,
        "requested_items": registration_item_names,
        "remaining_items": remaining_items,

        # REMAINING PAYMENT
        "remaining_amount": remaining_amount,
        "remaining_amount_display": f"₱{remaining_amount / 100:,.2f}",

        # EXPLICIT FLAGS
        "lanyard_paid": lanyard_paid,
        "tshirt_paid": tshirt_paid,

        # T-SHIRT
        "tshirt": {
            "item_id": tshirt_item.id if tshirt_item else None,
            "item_name": tshirt_item.item_name if tshirt_item else "T-Shirt",
            "price": tshirt_price,
            "price_display": f"₱{tshirt_price / 100:,.2f}",
            "status": "Paid" if tshirt_paid else "Unpaid",
            "paid": tshirt_paid,
            "remaining": not tshirt_paid
        },

        # LANYARD
        "lanyard": {
            "item_id": lanyard_item.id if lanyard_item else None,
            "item_name": lanyard_item.item_name if lanyard_item else "Lanyard",
            "price": lanyard_price,
            "price_display": f"₱{lanyard_price / 100:,.2f}",
            "status": "Paid" if lanyard_paid else "Unpaid",
            "paid": lanyard_paid,
            "remaining": not lanyard_paid
        },

        # ITEM STATUS (computed, not written)
        "tshirt_status": "Paid" if tshirt_paid else "Unpaid",
        "lanyard_status": "Paid" if lanyard_paid else "Unpaid",

        # REGISTRATION STATUS
        "registration_status": registration_status,

        # PAYMENT HISTORY
        "payments": [
            {
                "payment_id": p.id,
                "amount": p.amount,
                "amount_display": f"₱{p.amount / 100:,.2f}",
                "status": p.status,
                "tshirt_selected": bool(getattr(p, "tshirt_selected", False)),
                "lanyard_selected": bool(getattr(p, "lanyard_selected", False)),
                "tshirt_size": getattr(p, "tshirt_size", None),
                "checkout_url": getattr(p, "checkout_url", None),
                "paymongo_reference": getattr(p, "paymongo_reference", None),
                "paymongo_payment_id": getattr(p, "paymongo_payment_id", None),
                "paymongo_link_id": getattr(p, "paymongo_link_id", None),
                "created_at": p.created_at,
                "paid_at": getattr(p, "paid_at", None)
            }
            for p in history_payments
        ]
    }


# ======================================================
# CREATE PAYMONGO PAYMENT
# SUPPORTS SINGLE + BULK PARTICIPANTS
# ======================================================

@router.post("/create_payment")
def create_payment(
    data: PaymentCreateSchema,
    db: Session = Depends(get_db)
):

    print()
    print("=" * 70)
    print("CREATE PAYMENT REQUEST (mode:", "LIVE" if PAYMONGO_LIVE else "TEST", ")")
    print("=" * 70)

    normalize_bool = _normalize_bool
    allowed_sizes = ALLOWED_TSHIRT_SIZES

    # ==================================================
    # DETERMINE PARTICIPANT IDS
    # ==================================================

    participant_ids = []

    if data.participant_ids:

        for pid in data.participant_ids:

            try:
                participant_id = int(pid)

                if participant_id > 0:
                    participant_ids.append(participant_id)

            except (ValueError, TypeError):
                continue

    elif data.participant_id is not None:

        try:
            participant_id = int(data.participant_id)

            if participant_id > 0:
                participant_ids = [participant_id]

        except (ValueError, TypeError):
            participant_ids = []

    if not participant_ids:
        raise HTTPException(
            status_code=400,
            detail="At least one participant is required for payment."
        )

    # Remove duplicates, preserve order
    participant_ids = list(dict.fromkeys(participant_ids))

    is_bulk_payment = (
        len(participant_ids) > 1
        or bool(getattr(data, "bulk", False))
    )

    # ==================================================
    # LOAD + LOCK PARTICIPANTS
    #
    # with_for_update() serializes concurrent requests for the same
    # participants, so a double-click cannot create two payment links.
    # Ordered by id to avoid deadlocks between overlapping bulk requests.
    # ==================================================

    participants = (
        db.query(Participant)
        .filter(
            Participant.id.in_(participant_ids),
            Participant.is_archived == 0
        )
        .order_by(Participant.id.asc())
        .with_for_update()
        .all()
    )

    found_ids = {participant.id for participant in participants}

    missing_ids = [
        pid for pid in participant_ids
        if pid not in found_ids
    ]

    if missing_ids:

        db.rollback()

        raise HTTPException(
            status_code=404,
            detail={
                "message": "One or more participants were not found.",
                "missing_participant_ids": missing_ids
            }
        )

    # Preserve frontend order
    participant_map = {p.id: p for p in participants}
    participants = [participant_map[pid] for pid in participant_ids]

    # ==================================================
    # GLOBAL ITEM VALUES
    # ==================================================

    tshirt_value = getattr(data, "tshirt", None)

    if tshirt_value is None:
        tshirt_value = getattr(data, "tshirt_selected", False)

    lanyard_value = getattr(data, "lanyard", None)

    if lanyard_value is None:
        lanyard_value = getattr(data, "lanyard_selected", False)

    tshirt_requested = normalize_bool(tshirt_value)
    lanyard_requested = normalize_bool(lanyard_value)

    # ==================================================
    # BUILD PARTICIPANT T-SHIRT MAP  e.g. {51: "S", 52: "2XL"}
    # ==================================================

    participant_tshirt_map = {}

    raw_tshirt_selections = getattr(
        data,
        "participant_tshirt_selections",
        None
    )

    if raw_tshirt_selections:

        if not isinstance(raw_tshirt_selections, list):

            db.rollback()

            raise HTTPException(
                status_code=400,
                detail="Invalid participant T-shirt selections."
            )

        for selection in raw_tshirt_selections:

            if not isinstance(selection, dict):
                continue

            try:
                selection_participant_id = int(
                    selection.get("participant_id")
                )
            except (ValueError, TypeError):
                continue

            # Only allow participants included in this request
            if selection_participant_id not in participant_ids:
                continue

            if not normalize_bool(selection.get("tshirt_selected", False)):
                continue

            requested_size = selection.get("tshirt_size")

            if not requested_size:

                db.rollback()

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Please select a T-shirt size for "
                        f"participant {selection_participant_id}."
                    )
                )

            normalized_size = str(requested_size).strip().upper()

            if normalized_size not in allowed_sizes:

                db.rollback()

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid T-shirt size '{normalized_size}' "
                        f"for participant {selection_participant_id}. "
                        "Allowed sizes are S, M, L, XL, and 2XL."
                    )
                )

            participant_tshirt_map[selection_participant_id] = normalized_size

    # ==================================================
    # GLOBAL T-SHIRT SIZE
    # ==================================================

    tshirt_size = None

    requested_global_size = getattr(data, "tshirt_size", None)

    if requested_global_size:

        tshirt_size = str(requested_global_size).strip().upper()

        if tshirt_size not in allowed_sizes:

            db.rollback()

            raise HTTPException(
                status_code=400,
                detail="Invalid T-shirt size. Please select S, M, L, XL, or 2XL."
            )

    has_participant_tshirts = len(participant_tshirt_map) > 0

    # ==================================================
    # VALIDATE ITEM SELECTION
    # ==================================================

    if (
        not tshirt_requested
        and not lanyard_requested
        and not has_participant_tshirts
    ):

        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="Please select at least one registration item."
        )

    if (
        not is_bulk_payment
        and tshirt_requested
        and not tshirt_size
    ):

        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="Please select a T-shirt size."
        )

    if (
        is_bulk_payment
        and tshirt_requested
        and not participant_tshirt_map
        and not tshirt_size
    ):

        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="Please select a T-shirt size for each participant."
        )

    # ==================================================
    # PRICES (CENTAVOS) FROM THE DATABASE
    #
    # Same source as /payment_status, so the amount shown to the
    # user always equals the amount charged.
    # ==================================================

    tshirt_item, lanyard_item = _find_items(db)

    TSHIRT_PRICE = int(tshirt_item.price or 0) if tshirt_item else 0
    LANYARD_PRICE = int(lanyard_item.price or 0) if lanyard_item else 0

    if (tshirt_requested or has_participant_tshirts) and TSHIRT_PRICE <= 0:

        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="T-shirt is not currently available."
        )

    if lanyard_requested and LANYARD_PRICE <= 0:

        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="Lanyard is not currently available."
        )

    payment_rows = []
    total_amount = 0
    all_participant_items = []
    participant_payment_summary = []

    # ==================================================
    # PROCESS EACH PARTICIPANT
    # ==================================================

    for participant in participants:

        print("-" * 70)
        print(
            "PROCESSING PARTICIPANT:", participant.id,
            "|", participant.registration_number
        )

        payments = (
            db.query(Payment)
            .filter(Payment.participant_id == participant.id)
            .order_by(Payment.created_at.desc())
            .all()
        )

        # Same rule as /payment_status (always honours participant status)
        tshirt_paid, lanyard_paid = _paid_flags(participant, payments)

        # Participant-specific T-shirt
        if participant_tshirt_map:

            participant_tshirt_requested = (
                participant.id in participant_tshirt_map
            )

            participant_tshirt_size = participant_tshirt_map.get(
                participant.id
            )

        else:

            # Backward-compatible behaviour
            participant_tshirt_requested = tshirt_requested
            participant_tshirt_size = tshirt_size

        participant_lanyard_requested = lanyard_requested

        # Remove already-paid items
        if participant_tshirt_requested and tshirt_paid:
            participant_tshirt_requested = False
            participant_tshirt_size = None

        if participant_lanyard_requested and lanyard_paid:
            participant_lanyard_requested = False

        # Validate participant T-shirt size
        if participant_tshirt_requested:

            if not participant_tshirt_size:

                db.rollback()

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Please select a T-shirt size for "
                        f"{participant.fname or ''} "
                        f"{participant.lname or ''}."
                    )
                )

            participant_tshirt_size = (
                str(participant_tshirt_size).strip().upper()
            )

            if participant_tshirt_size not in allowed_sizes:

                db.rollback()

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Invalid T-shirt size "
                        f"for participant {participant.id}."
                    )
                )

        # Calculate participant amount
        participant_amount = 0
        participant_items = []

        if participant_tshirt_requested:
            participant_amount += TSHIRT_PRICE
            participant_items.append(f"T-Shirt ({participant_tshirt_size})")

        if participant_lanyard_requested:
            participant_amount += LANYARD_PRICE
            participant_items.append("Lanyard")

        if participant_amount <= 0:

            db.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Participant {participant.registration_number} "
                    "has no remaining items to pay."
                )
            )

        # ----------------------------------------------
        # EXISTING PENDING PAYMENT
        #
        # 1. Link from the other mode (test vs live) -> retire it and
        #    carry on creating a fresh link.
        # 2. Valid link, single payment -> reuse it (HTTP 200) so the
        #    user can simply resume checkout.
        # 3. Valid link, bulk payment -> 409 with the details.
        # ----------------------------------------------
        existing_payment = (
            db.query(Payment)
            .filter(
                Payment.participant_id == participant.id,
                Payment.status == "Pending",
                Payment.tshirt_selected == int(participant_tshirt_requested),
                Payment.lanyard_selected == int(participant_lanyard_requested)
            )
            .order_by(Payment.created_at.desc())
            .first()
        )

        if existing_payment and existing_payment.checkout_url:

            if not _link_matches_mode(existing_payment.checkout_url):

                print(
                    "Retiring stale pending payment from the other mode:",
                    existing_payment.id
                )

                existing_payment.status = "Failed"

            elif not is_bulk_payment:

                # Build the response BEFORE rollback (rollback expires
                # the ORM objects).
                reused = {
                    "message": "Existing pending payment reused.",
                    "reused": True,
                    "payment_type": "single",
                    "participant_count": 1,
                    "participant_ids": [participant.id],
                    "participant_id": participant.id,
                    "payment_id": existing_payment.id,
                    "payment_ids": [existing_payment.id],
                    "amount": existing_payment.amount,
                    "amount_display": f"₱{existing_payment.amount / 100:,.2f}",
                    "tshirt_selected": bool(existing_payment.tshirt_selected),
                    "lanyard_selected": bool(existing_payment.lanyard_selected),
                    "tshirt_size": existing_payment.tshirt_size,
                    "paymongo_link_id": existing_payment.paymongo_link_id,
                    "paymongo_reference": existing_payment.paymongo_reference,
                    "checkout_url": existing_payment.checkout_url,
                }

                db.rollback()

                return reused

            else:

                conflict = {
                    "message": (
                        "A pending payment already exists for "
                        f"participant {participant.registration_number}."
                    ),
                    "participant_id": participant.id,
                    "payment_id": existing_payment.id,
                    "checkout_url": existing_payment.checkout_url
                }

                db.rollback()

                raise HTTPException(
                    status_code=409,
                    detail=conflict
                )

        total_amount += participant_amount

        fullname = (
            f"{participant.fname or ''} "
            f"{participant.mname or ''} "
            f"{participant.lname or ''}"
        ).strip()

        all_participant_items.append({
            "participant_id": participant.id,
            "registration_number": participant.registration_number,
            "fullname": fullname,
            "items": participant_items,
            "tshirt_selected": int(participant_tshirt_requested),
            "tshirt_size": participant_tshirt_size,
            "lanyard_selected": int(participant_lanyard_requested),
            "amount": participant_amount,
            "amount_display": f"₱{participant_amount / 100:,.2f}"
        })

        participant_payment_summary.append({
            "participant_id": participant.id,
            "registration_number": participant.registration_number,
            "tshirt_selected": int(participant_tshirt_requested),
            "lanyard_selected": int(participant_lanyard_requested),
            "tshirt_size": participant_tshirt_size,
            "amount": participant_amount,
            "amount_display": f"₱{participant_amount / 100:,.2f}"
        })

        payment = Payment(
            participant_id=participant.id,
            amount=participant_amount,
            currency="PHP",
            status="Pending",
            payment_type="Participant",
            tshirt_selected=int(participant_tshirt_requested),
            lanyard_selected=int(participant_lanyard_requested),
            tshirt_size=participant_tshirt_size
        )

        db.add(payment)
        payment_rows.append(payment)

    # ==================================================
    # VALIDATE TOTAL
    # ==================================================

    if total_amount <= 0:

        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="There is no remaining amount to pay."
        )

    # ==================================================
    # FLUSH (so payment rows get IDs, but nothing is committed yet)
    # ==================================================

    try:
        db.flush()

    except Exception as e:

        db.rollback()

        print("PAYMENT ROW FLUSH FAILED:", repr(e))

        raise HTTPException(
            status_code=500,
            detail="Failed to create local payment records."
        )

    # ==================================================
    # INTERNAL REFERENCE + DESCRIPTION
    # ==================================================

    prefix = "CYF-BULK" if is_bulk_payment else "CYF-SINGLE"
    local_bulk_reference = f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

    if is_bulk_payment:
        description = (
            "CYF Bulk Merchandise Payment - "
            f"{len(participants)} Participants"
        )
    else:
        description = (
            "CYF Merchandise Payment - "
            f"{participants[0].registration_number}"
        )

    # ==================================================
    # REMARKS
    #
    # PayMongo Links do NOT support metadata, so identifiers go FIRST in
    # remarks. The webhook looks payments up by paymongo_link_id.
    # ==================================================

    payment_ids_text = ",".join(str(p.id) for p in payment_rows)

    participant_remarks = [
        f"{item['registration_number']} | {', '.join(item['items'])}"
        for item in all_participant_items
    ]

    remarks = (
        f"{local_bulk_reference} | "
        f"PaymentIDs: {payment_ids_text} | "
        f"{' || '.join(participant_remarks)}"
    )[:255]

    # ==================================================
    # PAYMONGO REQUEST
    # ==================================================

    base_url = str(PAYMONGO_API_URL or "").rstrip("/")
    url = f"{base_url}/v1/links"

    payload = {
        "data": {
            "attributes": {
                "amount": total_amount,
                "description": description,
                "remarks": remarks
            }
        }
    }

    print("PAYMONGO URL:", url)
    print("PAYMONGO AMOUNT:", total_amount)

    try:

        response = requests.post(
            url,
            auth=(PAYMONGO_SECRET_KEY, ""),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            json=payload,
            timeout=30
        )

    except requests.RequestException as e:

        _discard_payment_rows(db)

        print("PAYMONGO CONNECTION ERROR:", str(e))

        raise HTTPException(
            status_code=502,
            detail=f"PayMongo connection failed: {str(e)}"
        )

    if not response.ok:

        print("PAYMONGO ERROR:", response.status_code, response.text)

        _discard_payment_rows(db)

        try:
            error_data = response.json()
        except Exception:
            error_data = {"error": response.text}

        raise HTTPException(
            status_code=502,
            detail={
                "message": "PayMongo rejected the payment request.",
                "paymongo_status": response.status_code,
                "paymongo_error": error_data
            }
        )

    try:
        paymongo_data = response.json()

    except Exception:

        _discard_payment_rows(db)

        raise HTTPException(
            status_code=502,
            detail="PayMongo returned an invalid JSON response."
        )

    link_data = paymongo_data.get("data", {})

    if not link_data:

        _discard_payment_rows(db)

        raise HTTPException(
            status_code=502,
            detail={
                "message": "PayMongo returned an empty data object.",
                "paymongo_response": paymongo_data
            }
        )

    paymongo_link_id = link_data.get("id")

    link_attributes = link_data.get("attributes", {})

    if not isinstance(link_attributes, dict):
        link_attributes = {}

    checkout_url = (
        link_attributes.get("checkout_url")
        or link_attributes.get("url")
        or link_data.get("checkout_url")
        or link_data.get("url")
    )

    paymongo_reference = (
        link_attributes.get("reference_number")
        or link_data.get("reference_number")
    )

    if not paymongo_link_id:

        _discard_payment_rows(db)

        raise HTTPException(
            status_code=502,
            detail={
                "message": "PayMongo did not return a payment link ID.",
                "paymongo_response": paymongo_data
            }
        )

    if not checkout_url:

        _discard_payment_rows(db)

        raise HTTPException(
            status_code=502,
            detail={
                "message": "PayMongo did not return a checkout URL.",
                "paymongo_response": paymongo_data
            }
        )

    # ==================================================
    # SAVE PAYMONGO DATA TO EVERY LOCAL PAYMENT ROW
    #
    # Bulk: all rows share the SAME PayMongo link, so the webhook can
    # find every row via paymongo_link_id.
    # ==================================================

    for payment in payment_rows:

        if hasattr(payment, "paymongo_link_id"):
            payment.paymongo_link_id = paymongo_link_id

        if hasattr(payment, "paymongo_reference"):
            payment.paymongo_reference = paymongo_reference

        payment.checkout_url = checkout_url
        payment.status = "Pending"

    try:
        db.commit()

    except Exception as e:

        db.rollback()

        print("PAYMENT COMMIT FAILED:", repr(e))

        raise HTTPException(
            status_code=500,
            detail="Payment was created but could not be saved locally."
        )

    for payment in payment_rows:

        try:
            db.refresh(payment)
        except Exception as e:
            print("Payment refresh failed:", repr(e))

    return {

        "message": (
            "Bulk payment link created successfully."
            if is_bulk_payment
            else "Payment link created successfully."
        ),

        "reused": False,

        "payment_type": "bulk" if is_bulk_payment else "single",

        "participant_count": len(participants),

        "participant_ids": participant_ids,

        "participants": all_participant_items,

        "payment_ids": [payment.id for payment in payment_rows],

        "participant_payment_summary": participant_payment_summary,

        "items": list(
            dict.fromkeys(
                item
                for participant_item in all_participant_items
                for item in participant_item["items"]
            )
        ),

        "tshirt_selected": any(
            item["tshirt_selected"]
            for item in all_participant_items
        ),

        "lanyard_selected": any(
            item["lanyard_selected"]
            for item in all_participant_items
        ),

        "tshirt_size": tshirt_size,

        "participant_tshirt_selections": [
            {
                "participant_id": item["participant_id"],
                "tshirt_selected": bool(item["tshirt_selected"]),
                "tshirt_size": item["tshirt_size"]
            }
            for item in all_participant_items
            if item["tshirt_selected"]
        ],

        "amount": total_amount,

        "amount_display": f"₱{total_amount / 100:,.2f}",

        "paymongo_link_id": paymongo_link_id,

        "checkout_url": checkout_url,

        "paymongo_reference": paymongo_reference,

        "bulk_reference": local_bulk_reference
    }


# ============================================================
# VIEW ALL STORE PAYMENTS (ADMIN)
# ============================================================

@router.get(
    "/payments/store",
    response_model=List[PaymentResponse],
    dependencies=[Depends(require_admin)]
)
def view_all_store_payments(
    db: Session = Depends(get_db)
):

    return (
        db.query(Payment)
        .filter(Payment.store_item_id.isnot(None))
        .order_by(Payment.created_at.desc())
        .all()
    )


# ============================================================
# VIEW SINGLE STORE PAYMENT (ADMIN)
# ============================================================

@router.get(
    "/payments/store/{payment_id}",
    response_model=PaymentResponse,
    dependencies=[Depends(require_admin)]
)
def view_single_store_payment(
    payment_id: int,
    db: Session = Depends(get_db)
):

    payment = (
        db.query(Payment)
        .filter(
            Payment.id == payment_id,
            Payment.store_item_id.isnot(None)
        )
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Store payment not found."
        )

    return payment


# ============================================================
# SHARED SERIALIZER FOR T-SHIRT / LANYARD LISTS
# ============================================================

def _serialize_payment_with_participant(payment, participant):

    return {
        "id": payment.id,
        "participant_id": payment.participant_id,
        "payment_type": payment.payment_type,

        "store_item_id": payment.store_item_id,
        "store_quantity": payment.store_quantity,
        "store_size": payment.store_size,

        "amount": payment.amount,
        "currency": payment.currency,
        "status": payment.status,

        "tshirt_selected": payment.tshirt_selected,
        "lanyard_selected": payment.lanyard_selected,
        "tshirt_size": payment.tshirt_size,

        "sponsorship_tier": payment.sponsorship_tier,
        "sponsor_id": payment.sponsor_id,

        "paymongo_link_id": payment.paymongo_link_id,
        "paymongo_payment_id": payment.paymongo_payment_id,
        "paymongo_reference": payment.paymongo_reference,
        "checkout_url": payment.checkout_url,

        "description": payment.description,
        "customer_name": payment.customer_name,
        "customer_contact": payment.customer_contact,
        "customer_email": payment.customer_email,

        "created_at": payment.created_at,
        "paid_at": payment.paid_at,

        # Full participant name
        "participant_name": (
            (
                f"{participant.fname} "
                f"{participant.mname + ' ' if participant.mname else ''}"
                f"{participant.lname}"
            )
            if participant
            else payment.customer_name
        )
    }


def _serialize_payments(db: Session, payments):
    """Serialize payments, loading all participants in ONE query."""

    participant_ids = {
        p.participant_id for p in payments if p.participant_id
    }

    participants_by_id = {}

    if participant_ids:
        participants_by_id = {
            participant.id: participant
            for participant in (
                db.query(Participant)
                .filter(Participant.id.in_(participant_ids))
                .all()
            )
        }

    return [
        _serialize_payment_with_participant(
            payment,
            participants_by_id.get(payment.participant_id)
        )
        for payment in payments
    ]


# ============================================================
# VIEW ALL T-SHIRT PAYMENTS (ADMIN)
# ============================================================

@router.get(
    "/payments/tshirt",
    response_model=List[PaymentResponse],
    dependencies=[Depends(require_admin)]
)
def view_all_tshirt_payments(
    db: Session = Depends(get_db)
):

    payments = (
        db.query(Payment)
        .filter(Payment.tshirt_selected > 0)
        .order_by(Payment.created_at.desc())
        .all()
    )

    return _serialize_payments(db, payments)


# ============================================================
# VIEW SINGLE T-SHIRT PAYMENT (ADMIN)
# ============================================================

@router.get(
    "/payments/tshirt/{payment_id}",
    response_model=PaymentResponse,
    dependencies=[Depends(require_admin)]
)
def view_single_tshirt_payment(
    payment_id: int,
    db: Session = Depends(get_db)
):

    payment = (
        db.query(Payment)
        .filter(
            Payment.id == payment_id,
            Payment.tshirt_selected > 0
        )
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="T-Shirt payment not found."
        )

    return payment


# ============================================================
# VIEW ALL LANYARD PAYMENTS (ADMIN)
# ============================================================

@router.get(
    "/payments/lanyard",
    response_model=List[PaymentResponse],
    dependencies=[Depends(require_admin)]
)
def view_all_lanyard_payments(
    db: Session = Depends(get_db)
):

    payments = (
        db.query(Payment)
        .filter(Payment.lanyard_selected > 0)
        .order_by(Payment.created_at.desc())
        .all()
    )

    return _serialize_payments(db, payments)


# ============================================================
# VIEW SINGLE LANYARD PAYMENT (ADMIN)
# ============================================================

@router.get(
    "/payments/lanyard/{payment_id}",
    response_model=PaymentResponse,
    dependencies=[Depends(require_admin)]
)
def view_single_lanyard_payment(
    payment_id: int,
    db: Session = Depends(get_db)
):

    payment = (
        db.query(Payment)
        .filter(
            Payment.id == payment_id,
            Payment.lanyard_selected > 0
        )
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Lanyard payment not found."
        )

    return payment