"""Routes: webhooks."""

from fastapi import Depends
from fastapi.responses import JSONResponse
from fastapi import Request
from sqlalchemy.orm import Session
import datetime
import hashlib
import hmac
import json
import time
from fastapi import APIRouter

from app.config import (
    PAYMONGO_WEBHOOK_SECRET,
)
from app.database import (
    get_db,
)
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

@router.get("/webhooks/paymongo")
async def paymongo_webhook_test():
    print("PAYMONGO WEBHOOK GET TEST HIT")
    return {
        "ok": True,
        "message": "PayMongo webhook endpoint is reachable"
    }


# ======================================================
# PAYMONGO WEBHOOK
#
# SUPPORTS:
# - PARTICIPANT PAYMENTS
# - CASH SPONSORSHIPS
# - STORE PURCHASES
#
# STORE PURCHASES:
# - 1 item
# - 2 items
# - 3 items
# - 10 items
# - Up to the cart limit configured in /store/purchase
#
# ONE STORE CART = ONE PAYMONGO PAYMENT LINK
# ONE STORE CART ITEM = ONE PAYMENT DATABASE ROW
#
# ALL STORE PAYMENT ROWS SHARE:
#     store_order_id
#     paymongo_link_id
#
# When the webhook confirms payment:
#
#     ALL pending rows belonging to the same
#     store_order_id are processed.
#
# Inventory is reduced for EVERY unpaid cart item.
# ======================================================

# ======================================================
# PAYMONGO WEBHOOK
# ======================================================
#
# Handles:
#
# 1. Participant payments
# 2. Bulk participant payments
# 3. Store payments
# 4. Cash sponsorship payments
#
# IMPORTANT PARTICIPANT PAYMENT RULE:
#
# Payment.status being "Paid" does NOT mean that the
# Participant merchandise statuses are already synchronized.
#
# Therefore, participant payment rows are ALWAYS synchronized
# when payment.paid is received.
#
# This fixes cases such as:
#
# Payment.status       = Paid
# Participant.lanyard_status = Pending
#
# The webhook will repair the participant status.
#
# ======================================================

# ============================================================
# PAYMONGO WEBHOOK
# ============================================================
#
# SUPPORTS:
#   1. Normal participant payments
#   2. Bulk participant payments
#   3. Cash sponsorship payments
#   4. Store/cart payments
#
# IMPORTANT:
#
# Participant bulk payment:
#
#   Payment #101 -> Participant 27 -> Lanyard
#   Payment #102 -> Participant 28 -> Lanyard
#   Payment #103 -> Participant 29 -> Lanyard
#
# All rows share ONE PayMongo payment link.
#
# When PayMongo confirms payment, ALL participant rows
# belonging to that link are marked Paid and each participant
# is updated independently.
#
# ============================================================

@router.post("/webhooks/paymongo")
async def paymongo_webhook(
    request: Request,
    db: Session = Depends(get_db)
):

    print("\n")
    print("=" * 80)
    print("PAYMONGO WEBHOOK RECEIVED")
    print("=" * 80)

    # ========================================================
    # 1. READ RAW BODY
    # ========================================================

    try:
        raw_body = await request.body()

    except Exception as e:

        print(
            "Webhook body read failed:",
            repr(e)
        )

        return JSONResponse(
            status_code=400,
            content={
                "received": False,
                "processed": False,
                "message": "Unable to read webhook body."
            }
        )

    if not raw_body:

        print(
            "Webhook body is empty."
        )

        return JSONResponse(
            status_code=400,
            content={
                "received": False,
                "processed": False,
                "message": "Empty webhook body."
            }
        )

    print(
        "Body Length:",
        len(raw_body)
    )

    # ========================================================
    # 2. PAYMONGO SIGNATURE
    # ========================================================

    signature_header = request.headers.get(
        "Paymongo-Signature"
    )

    if not signature_header:

        print(
            "Missing Paymongo-Signature."
        )

        return JSONResponse(
            status_code=401,
            content={
                "received": False,
                "processed": False,
                "message": "Missing PayMongo signature."
            }
        )

    # ========================================================
    # 3. VERIFY SIGNATURE
    # ========================================================

    try:

        parts = {}

        for item in signature_header.split(","):

            if "=" not in item:
                continue

            key, value = item.split(
                "=",
                1
            )

            parts[
                key.strip()
            ] = value.strip()

        timestamp = parts.get("t")

        test_signature = parts.get(
            "te",
            ""
        )

        live_signature = parts.get(
            "li",
            ""
        )

        if not timestamp:

            return JSONResponse(
                status_code=401,
                content={
                    "received": False,
                    "processed": False,
                    "message": "Missing webhook timestamp."
                }
            )

        timestamp_int = int(
            timestamp
        )

        current_timestamp = int(
            time.time()
        )

        difference = abs(
            current_timestamp -
            timestamp_int
        )

        print(
            "Webhook Timestamp Difference:",
            difference,
            "seconds"
        )

        if difference > 300:

            print(
                "Webhook timestamp expired."
            )

            return JSONResponse(
                status_code=401,
                content={
                    "received": False,
                    "processed": False,
                    "message": "Webhook timestamp expired."
                }
            )

        if not PAYMONGO_WEBHOOK_SECRET:

            print(
                "PAYMONGO_WEBHOOK_SECRET is missing."
            )

            return JSONResponse(
                status_code=500,
                content={
                    "received": False,
                    "processed": False,
                    "message": "Webhook secret is not configured."
                }
            )

        signed_payload = (
            f"{timestamp}."
        ).encode(
            "utf-8"
        ) + raw_body

        expected_signature = hmac.new(
            PAYMONGO_WEBHOOK_SECRET.encode(
                "utf-8"
            ),
            signed_payload,
            hashlib.sha256
        ).hexdigest()

        provided_signature = (
            live_signature
            if live_signature
            else test_signature
        )

        if not provided_signature:

            return JSONResponse(
                status_code=401,
                content={
                    "received": False,
                    "processed": False,
                    "message": "Missing signature value."
                }
            )

        if not hmac.compare_digest(
            expected_signature,
            provided_signature
        ):

            print(
                "Invalid PayMongo signature."
            )

            return JSONResponse(
                status_code=401,
                content={
                    "received": False,
                    "processed": False,
                    "message": "Invalid PayMongo webhook signature."
                }
            )

        print(
            "Webhook signature verified."
        )

    except Exception as e:

        print(
            "Webhook signature verification failed:",
            repr(e)
        )

        return JSONResponse(
            status_code=401,
            content={
                "received": False,
                "processed": False,
                "message": "Invalid PayMongo webhook signature."
            }
        )

    # ========================================================
    # 4. PARSE JSON
    # ========================================================

    try:

        payload = json.loads(
            raw_body.decode(
                "utf-8"
            )
        )

    except Exception as e:

        print(
            "JSON parse failed:",
            repr(e)
        )

        return JSONResponse(
            status_code=400,
            content={
                "received": False,
                "processed": False,
                "message": "Invalid JSON payload."
            }
        )

    # ========================================================
    # 5. EVENT
    # ========================================================

    event_data = payload.get(
        "data",
        {}
    )

    if not isinstance(
        event_data,
        dict
    ):
        event_data = {}

    event_id = event_data.get(
        "id"
    )

    event_attributes = event_data.get(
        "attributes",
        {}
    )

    if not isinstance(
        event_attributes,
        dict
    ):
        event_attributes = {}

    event_type = event_attributes.get(
        "type"
    )

    livemode = event_attributes.get(
        "livemode"
    )

    print("=" * 80)
    print("PAYMONGO EVENT")
    print("=" * 80)
    print(
        "Event ID:",
        event_id
    )
    print(
        "Event Type:",
        event_type
    )
    print(
        "Live Mode:",
        livemode
    )
    print("=" * 80)

    # ========================================================
    # 6. ONLY SUCCESSFUL EVENTS
    # ========================================================

    if event_type not in {
        "payment.paid",
        "link.payment.paid"
    }:

        print(
            "Event ignored:",
            event_type
        )

        return {
            "received": True,
            "processed": False,
            "event_id": event_id,
            "event_type": event_type,
            "message": "Event ignored."
        }

    # ========================================================
    # 7. PAYMONGO RESOURCE
    # ========================================================

    resource = event_attributes.get(
        "data",
        {}
    )

    if not isinstance(
        resource,
        dict
    ):
        resource = {}

    resource_id = resource.get(
        "id"
    )

    resource_type = resource.get(
        "type"
    )

    resource_attributes = resource.get(
        "attributes",
        {}
    )

    if not isinstance(
        resource_attributes,
        dict
    ):
        resource_attributes = {}

    print(
        "Resource ID:",
        resource_id
    )

    print(
        "Resource Type:",
        resource_type
    )

    # ========================================================
    # 8. METADATA
    # ========================================================

    metadata = resource_attributes.get(
        "metadata",
        {}
    )

    if not isinstance(
        metadata,
        dict
    ):
        metadata = {}

    print(
        "Metadata:",
        metadata
    )

    # ========================================================
    # 9. IDENTIFIERS
    # ========================================================

    # --------------------------------------------------------
    # SPONSORSHIP ID
    # --------------------------------------------------------

    sponsorship_id = metadata.get(
        "sponsorship_id"
    )

    if sponsorship_id:

        sponsorship_id = str(
            sponsorship_id
        ).strip()

    # --------------------------------------------------------
    # STORE ORDER ID
    # --------------------------------------------------------

    store_order_id = (
        metadata.get(
            "store_order_id"
        )
        or metadata.get(
            "order_id"
        )
    )

    if store_order_id:

        store_order_id = str(
            store_order_id
        ).strip()

    # --------------------------------------------------------
    # INTERNAL PAYMENT ID
    # --------------------------------------------------------

    internal_payment_id = metadata.get(
        "payment_id"
    )

    if internal_payment_id:

        internal_payment_id = str(
            internal_payment_id
        ).strip()

    # --------------------------------------------------------
    # BULK PAYMENT IDS
    #
    # create_payment sends:
    #
    #   "payment_ids": "101,102,103"
    #
    # --------------------------------------------------------

    raw_payment_ids = metadata.get(
        "payment_ids"
    )

    payment_ids = []

    if isinstance(
        raw_payment_ids,
        list
    ):

        for value in raw_payment_ids:

            try:

                payment_ids.append(
                    int(value)
                )

            except (
                ValueError,
                TypeError
            ):

                pass

    elif raw_payment_ids:

        raw_payment_ids_string = str(
            raw_payment_ids
        ).strip()

        # ----------------------------------------------------
        # JSON ARRAY
        # ----------------------------------------------------

        if (
            raw_payment_ids_string.startswith("[")
            and
            raw_payment_ids_string.endswith("]")
        ):

            try:

                decoded_payment_ids = json.loads(
                    raw_payment_ids_string
                )

                if isinstance(
                    decoded_payment_ids,
                    list
                ):

                    for value in decoded_payment_ids:

                        try:

                            payment_ids.append(
                                int(value)
                            )

                        except (
                            ValueError,
                            TypeError
                        ):

                            pass

            except Exception:

                pass

        # ----------------------------------------------------
        # COMMA-SEPARATED
        # ----------------------------------------------------

        else:

            for value in raw_payment_ids_string.split(","):

                value = value.strip()

                if not value:
                    continue

                try:

                    payment_ids.append(
                        int(value)
                    )

                except (
                    ValueError,
                    TypeError
                ):

                    pass

    # Remove duplicates
    payment_ids = list(
        dict.fromkeys(
            payment_ids
        )
    )

    # --------------------------------------------------------
    # PAYMONGO REFERENCE
    # --------------------------------------------------------

    paymongo_reference = (
        metadata.get(
            "pm_reference_number"
        )
        or metadata.get(
            "reference_number"
        )
        or resource_attributes.get(
            "external_reference_number"
        )
        or resource_attributes.get(
            "reference_number"
        )
    )

    if paymongo_reference:

        paymongo_reference = str(
            paymongo_reference
        ).strip()

    else:

        paymongo_reference = None

    # --------------------------------------------------------
    # PAYMONGO PAYMENT ID
    # --------------------------------------------------------

    paymongo_payment_id = None

    if event_type == "payment.paid":

        paymongo_payment_id = resource_id

    if not paymongo_payment_id:

        paymongo_payment_id = metadata.get(
            "paymongo_payment_id"
        )

    if paymongo_payment_id:

        paymongo_payment_id = str(
            paymongo_payment_id
        ).strip()

    # --------------------------------------------------------
    # PAYMONGO LINK ID
    # --------------------------------------------------------

    paymongo_link_id = None

    if event_type == "link.payment.paid":

        paymongo_link_id = resource_id

    if not paymongo_link_id:

        paymongo_link_id = metadata.get(
            "paymongo_link_id"
        )

    if not paymongo_link_id:

        paymongo_link_id = resource_attributes.get(
            "link_id"
        )

    if paymongo_link_id:

        paymongo_link_id = str(
            paymongo_link_id
        ).strip()

    # --------------------------------------------------------
    # AMOUNT
    # --------------------------------------------------------

    paymongo_amount = resource_attributes.get(
        "amount"
    )

    try:

        paymongo_amount = int(
            paymongo_amount or 0
        )

    except (
        ValueError,
        TypeError
    ):

        paymongo_amount = 0

    print("=" * 80)
    print("PAYMENT IDENTIFIERS")
    print("=" * 80)
    print(
        "Store Order ID:",
        store_order_id
    )
    print(
        "Internal Payment ID:",
        internal_payment_id
    )
    print(
        "Bulk Payment IDs:",
        payment_ids
    )
    print(
        "PayMongo Reference:",
        paymongo_reference
    )
    print(
        "PayMongo Payment ID:",
        paymongo_payment_id
    )
    print(
        "PayMongo Link ID:",
        paymongo_link_id
    )
    print(
        "PayMongo Amount:",
        paymongo_amount
    )
    print("=" * 80)

    # ========================================================
    # 10. CASH SPONSORSHIP MATCHING
    # ========================================================

    cash_sponsorship = None

    # --------------------------------------------------------
    # BY SPONSORSHIP ID
    # --------------------------------------------------------

    if sponsorship_id:

        try:

            cash_sponsorship = (
                db.query(
                    CashSponsorship
                )
                .filter(
                    CashSponsorship.id ==
                    int(
                        sponsorship_id
                    )
                )
                .first()
            )

        except (
            ValueError,
            TypeError
        ):

            cash_sponsorship = None

    # --------------------------------------------------------
    # BY REFERENCE
    # --------------------------------------------------------

    if (
        not cash_sponsorship
        and paymongo_reference
        and hasattr(
            CashSponsorship,
            "paymongo_reference"
        )
    ):

        cash_sponsorship = (
            db.query(
                CashSponsorship
            )
            .filter(
                CashSponsorship.paymongo_reference ==
                paymongo_reference
            )
            .first()
        )

    # --------------------------------------------------------
    # BY PAYMONGO PAYMENT ID
    # --------------------------------------------------------

    if (
        not cash_sponsorship
        and paymongo_payment_id
        and hasattr(
            CashSponsorship,
            "paymongo_payment_id"
        )
    ):

        cash_sponsorship = (
            db.query(
                CashSponsorship
            )
            .filter(
                CashSponsorship.paymongo_payment_id ==
                paymongo_payment_id
            )
            .first()
        )

    # --------------------------------------------------------
    # BY PAYMONGO LINK ID
    # --------------------------------------------------------

    if (
        not cash_sponsorship
        and paymongo_link_id
        and hasattr(
            CashSponsorship,
            "paymongo_link_id"
        )
    ):

        cash_sponsorship = (
            db.query(
                CashSponsorship
            )
            .filter(
                CashSponsorship.paymongo_link_id ==
                paymongo_link_id
            )
            .first()
        )

    # ========================================================
    # 11. CASH SPONSORSHIP
    # ========================================================

    if cash_sponsorship:

        print("=" * 80)
        print(
            "CASH SPONSORSHIP FOUND"
        )
        print(
            "Sponsorship ID:",
            cash_sponsorship.id
        )
        print("=" * 80)

        # ----------------------------------------------------
        # SAVE PAYMONGO INFORMATION
        # ----------------------------------------------------

        if (
            paymongo_reference
            and hasattr(
                cash_sponsorship,
                "paymongo_reference"
            )
        ):

            cash_sponsorship.paymongo_reference = (
                paymongo_reference
            )

        if (
            paymongo_payment_id
            and hasattr(
                cash_sponsorship,
                "paymongo_payment_id"
            )
        ):

            cash_sponsorship.paymongo_payment_id = (
                paymongo_payment_id
            )

        if (
            paymongo_link_id
            and hasattr(
                cash_sponsorship,
                "paymongo_link_id"
            )
        ):

            cash_sponsorship.paymongo_link_id = (
                paymongo_link_id
            )

        # ----------------------------------------------------
        # CURRENT STATUS
        # ----------------------------------------------------

        current_status = str(
            getattr(
                cash_sponsorship,
                "payment_status",
                ""
            )
            or ""
        ).strip().lower()

        # ----------------------------------------------------
        # ALREADY PAID
        # ----------------------------------------------------

        if current_status == "paid":

            try:
                db.commit()
            except Exception:
                db.rollback()

            print(
                "Sponsorship already Paid."
            )

            return {
                "received": True,
                "processed": True,
                "already_processed": True,
                "payment_type": "sponsor_package",
                "event_id": event_id,
                "sponsorship_id": cash_sponsorship.id,
                "payment_status": "Paid"
            }

        # ----------------------------------------------------
        # DONATION AMOUNT
        # ----------------------------------------------------

        try:

            donation_amount = int(
                getattr(
                    cash_sponsorship,
                    "donation_amount",
                    0
                )
                or 0
            )

        except (
            ValueError,
            TypeError
        ):

            donation_amount = 0

        if donation_amount <= 0:

            db.rollback()

            return {
                "received": True,
                "processed": False,
                "payment_type": "sponsor_package",
                "sponsorship_id": cash_sponsorship.id,
                "message": "Invalid sponsorship amount."
            }

        # ----------------------------------------------------
        # VERIFY AMOUNT
        # ----------------------------------------------------

        if (
            paymongo_amount > 0
            and
            paymongo_amount != donation_amount
        ):

            print(
                "SPONSORSHIP AMOUNT MISMATCH"
            )

            db.rollback()

            return {
                "received": True,
                "processed": False,
                "payment_type": "sponsor_package",
                "sponsorship_id": cash_sponsorship.id,
                "paymongo_amount": paymongo_amount,
                "expected_amount": donation_amount,
                "message":
                    "Payment amount does not match sponsorship amount."
            }

        donation_pesos = (
            donation_amount / 100
        )

        # ----------------------------------------------------
        # CASH DONATION TOTAL
        # ----------------------------------------------------

        donation_total = (
            db.query(
                CashDonationTotal
            )
            .order_by(
                CashDonationTotal.id.asc()
            )
            .first()
        )

        if not donation_total:

            donation_total = CashDonationTotal(
                total_amount=0
            )

            db.add(
                donation_total
            )

            db.flush()

        try:

            current_total = float(
                donation_total.total_amount
                or 0
            )

        except (
            ValueError,
            TypeError
        ):

            current_total = 0.0

        new_total = (
            current_total +
            donation_pesos
        )

        donation_total.total_amount = (
            new_total
        )

        if hasattr(
            donation_total,
            "updated_at"
        ):

            donation_total.updated_at = (
                datetime.datetime.now()
            )

        # ----------------------------------------------------
        # MARK SPONSORSHIP PAID
        # ----------------------------------------------------

        cash_sponsorship.payment_status = (
            "Paid"
        )

        if hasattr(
            cash_sponsorship,
            "donation_status"
        ):

            cash_sponsorship.donation_status = (
                "Paid"
            )

        if hasattr(
            cash_sponsorship,
            "paid_at"
        ):

            cash_sponsorship.paid_at = (
                datetime.datetime.now()
            )

        if hasattr(
            cash_sponsorship,
            "updated_at"
        ):

            cash_sponsorship.updated_at = (
                datetime.datetime.now()
            )

        if hasattr(
            cash_sponsorship,
            "cash_total_added"
        ):

            cash_sponsorship.cash_total_added = (
                donation_pesos
            )

        # ----------------------------------------------------
        # COMMIT SPONSORSHIP
        # ----------------------------------------------------

        try:

            db.commit()

        except Exception as e:

            db.rollback()

            print(
                "Sponsorship commit failed:",
                repr(e)
            )

            return JSONResponse(
                status_code=500,
                content={
                    "received": True,
                    "processed": False,
                    "message":
                        "Sponsorship database update failed."
                }
            )

        # ----------------------------------------------------
        # SPONSORSHIP EMAIL
        # ----------------------------------------------------

        gmail_success = False

        try:

            sponsor_email = getattr(
                cash_sponsorship,
                "email",
                None
            )

            if sponsor_email:

                gmail_success = bool(
                    await send_cash_sponsorship_confirmation_email(
                        cash_sponsorship,
                        cash_sponsorship
                    )
                )

                print(
                    "Sponsorship Gmail:",
                    gmail_success
                )

        except Exception as e:

            print(
                "Sponsorship Gmail failed:",
                repr(e)
            )

        return {
            "received": True,
            "processed": True,
            "payment_type": "sponsor_package",
            "event_id": event_id,
            "sponsorship_id": cash_sponsorship.id,
            "payment_status": "Paid",
            "donation_amount": donation_pesos,
            "donation_amount_display":
                f"₱{donation_pesos:,.2f}",
            "cash_donation_total": new_total,
            "cash_donation_total_display":
                f"₱{new_total:,.2f}",
            "paymongo_reference":
                paymongo_reference,
            "paymongo_payment_id":
                paymongo_payment_id,
            "paymongo_link_id":
                paymongo_link_id,
            "gmail_sent":
                gmail_success
        }

    # ========================================================
    # 12. FIND PAYMENT ROW
    #
    # For participant bulk payments, payment_ids is the
    # strongest identifier.
    # ========================================================

    payment = None

    # --------------------------------------------------------
    # BY PAYMENT IDS
    # --------------------------------------------------------

    if payment_ids:

        payment = (
            db.query(
                Payment
            )
            .filter(
                Payment.id.in_(
                    payment_ids
                )
            )
            .order_by(
                Payment.id.asc()
            )
            .first()
        )

    # --------------------------------------------------------
    # BY STORE ORDER
    # --------------------------------------------------------

    if (
        not payment
        and store_order_id
    ):

        payment = (
            db.query(
                Payment
            )
            .filter(
                Payment.store_order_id ==
                store_order_id
            )
            .order_by(
                Payment.id.asc()
            )
            .first()
        )

    # --------------------------------------------------------
    # BY INTERNAL PAYMENT ID
    # --------------------------------------------------------

    if (
        not payment
        and internal_payment_id
    ):

        try:

            payment = (
                db.query(
                    Payment
                )
                .filter(
                    Payment.id ==
                    int(
                        internal_payment_id
                    )
                )
                .first()
            )

        except (
            ValueError,
            TypeError
        ):

            payment = None

    # --------------------------------------------------------
    # BY REFERENCE
    # --------------------------------------------------------

    if (
        not payment
        and paymongo_reference
        and hasattr(
            Payment,
            "paymongo_reference"
        )
    ):

        payment = (
            db.query(
                Payment
            )
            .filter(
                Payment.paymongo_reference ==
                paymongo_reference
            )
            .order_by(
                Payment.id.asc()
            )
            .first()
        )

    # --------------------------------------------------------
    # BY PAYMONGO PAYMENT ID
    # --------------------------------------------------------

    if (
        not payment
        and paymongo_payment_id
        and hasattr(
            Payment,
            "paymongo_payment_id"
        )
    ):

        payment = (
            db.query(
                Payment
            )
            .filter(
                Payment.paymongo_payment_id ==
                paymongo_payment_id
            )
            .order_by(
                Payment.id.asc()
            )
            .first()
        )

    # --------------------------------------------------------
    # BY PAYMONGO LINK ID
    # --------------------------------------------------------

    if (
        not payment
        and paymongo_link_id
        and hasattr(
            Payment,
            "paymongo_link_id"
        )
    ):

        payment = (
            db.query(
                Payment
            )
            .filter(
                Payment.paymongo_link_id ==
                paymongo_link_id
            )
            .order_by(
                Payment.id.asc()
            )
            .first()
        )

    # ========================================================
    # PAYMENT NOT FOUND
    # ========================================================

    if not payment:

        print("=" * 80)
        print(
            "NO LOCAL PAYMENT FOUND"
        )
        print("=" * 80)

        return {
            "received": True,
            "processed": False,
            "event_id": event_id,
            "payment_ids": payment_ids,
            "paymongo_reference":
                paymongo_reference,
            "paymongo_payment_id":
                paymongo_payment_id,
            "paymongo_link_id":
                paymongo_link_id,
            "message":
                "No matching local payment found."
        }

    print("=" * 80)
    print(
        "LOCAL PAYMENT FOUND"
    )
    print(
        "Payment ID:",
        payment.id
    )
    print(
        "Payment Type:",
        getattr(
            payment,
            "payment_type",
            None
        )
    )
    print("=" * 80)

    # ========================================================
    # 13. DETERMINE PAYMENT TYPE
    # ========================================================

    payment_type = str(
        getattr(
            payment,
            "payment_type",
            ""
        )
        or ""
    ).strip().lower()

    # ========================================================
    # ========================================================
    # PARTICIPANT / BULK PARTICIPANT PAYMENT
    # ========================================================
    #
    # IMPORTANT:
    #
    # BOTH "participant" AND "bulk" MUST ENTER THIS BLOCK.
    #
    # /create_payment uses:
    #
    #   payment_type = "bulk"
    #
    # for multiple participants.
    #
    # ========================================================

    if payment_type in {
        "participant",
        "bulk",
        "single"
    }:

        print("=" * 80)
        print(
            "PROCESSING PARTICIPANT PAYMENT"
        )
        print(
            "Payment Type:",
            payment_type
        )
        print("=" * 80)

        # ----------------------------------------------------
        # FIND ALL PARTICIPANT PAYMENT ROWS
        # ----------------------------------------------------

        participant_payments = []

        # ----------------------------------------------------
        # FIRST: EXACT PAYMENT IDS FROM METADATA
        # ----------------------------------------------------

        if payment_ids:

            participant_payments = (
                db.query(
                    Payment
                )
                .filter(
                    Payment.id.in_(
                        payment_ids
                    ),
                    Payment.payment_type.ilike(
                        "Participant"
                    )
                )
                .order_by(
                    Payment.id.asc()
                )
                .with_for_update()
                .all()
            )

            print(
                "Participant rows found by payment_ids:",
                len(
                    participant_payments
                )
            )

        # ----------------------------------------------------
        # FALLBACK: SHARED PAYMONGO LINK
        # ----------------------------------------------------

        if (
            not participant_payments
            and paymongo_link_id
        ):

            participant_payments = (
                db.query(
                    Payment
                )
                .filter(
                    Payment.paymongo_link_id ==
                    paymongo_link_id,
                    Payment.payment_type.ilike(
                        "Participant"
                    )
                )
                .order_by(
                    Payment.id.asc()
                )
                .with_for_update()
                .all()
            )

            print(
                "Participant rows found by PayMongo Link ID:",
                len(
                    participant_payments
                )
            )

        # ----------------------------------------------------
        # FALLBACK: REFERENCE
        # ----------------------------------------------------

        if (
            not participant_payments
            and paymongo_reference
        ):

            participant_payments = (
                db.query(
                    Payment
                )
                .filter(
                    Payment.paymongo_reference ==
                    paymongo_reference,
                    Payment.payment_type.ilike(
                        "Participant"
                    )
                )
                .order_by(
                    Payment.id.asc()
                )
                .with_for_update()
                .all()
            )

            print(
                "Participant rows found by reference:",
                len(
                    participant_payments
                )
            )

        # ----------------------------------------------------
        # FALLBACK: SINGLE PAYMENT
        # ----------------------------------------------------

        if (
            not participant_payments
            and payment
            and getattr(
                payment,
                "participant_id",
                None
            )
        ):

            participant_payments = [
                payment
            ]

        # ----------------------------------------------------
        # NO PARTICIPANT ROWS
        # ----------------------------------------------------

        if not participant_payments:

            db.rollback()

            return {
                "received": True,
                "processed": False,
                "payment_type":
                    payment_type,
                "message":
                    "No participant payment rows found."
            }

        # ----------------------------------------------------
        # REMOVE DUPLICATES
        # ----------------------------------------------------

        unique_payments = {}

        for participant_payment in participant_payments:

            unique_payments[
                participant_payment.id
            ] = participant_payment

        participant_payments = list(
            unique_payments.values()
        )

        participant_payments.sort(
            key=lambda p: p.id
        )

        print("=" * 80)
        print(
            "PARTICIPANT PAYMENT ROWS:"
        )
        print("=" * 80)

        for participant_payment in participant_payments:

            print(
                "Payment ID:",
                participant_payment.id,
                "| Participant ID:",
                getattr(
                    participant_payment,
                    "participant_id",
                    None
                ),
                "| Amount:",
                getattr(
                    participant_payment,
                    "amount",
                    None
                ),
                "| T-Shirt:",
                getattr(
                    participant_payment,
                    "tshirt_selected",
                    0
                ),
                "| Lanyard:",
                getattr(
                    participant_payment,
                    "lanyard_selected",
                    0
                ),
                "| Status:",
                getattr(
                    participant_payment,
                    "status",
                    None
                )
            )

        print("=" * 80)

        # ----------------------------------------------------
        # VERIFY PAYMENT IDS
        #
        # If create_payment explicitly supplied payment_ids,
        # do not silently process only part of the bulk payment.
        # ----------------------------------------------------

        if payment_ids:

            found_ids = {
                p.id
                for p in participant_payments
            }

            missing_ids = [
                pid
                for pid in payment_ids
                if pid not in found_ids
            ]

            if missing_ids:

                print(
                    "Missing participant payment IDs:",
                    missing_ids
                )

                # Try shared PayMongo link as recovery.
                if paymongo_link_id:

                    fallback_payments = (
                        db.query(
                            Payment
                        )
                        .filter(
                            Payment.paymongo_link_id ==
                            paymongo_link_id,
                            Payment.payment_type.ilike(
                                "Participant"
                            )
                        )
                        .order_by(
                            Payment.id.asc()
                        )
                        .with_for_update()
                        .all()
                    )

                    fallback_ids = {
                        p.id
                        for p in fallback_payments
                    }

                    if all(
                        pid in fallback_ids
                        for pid in payment_ids
                    ):

                        participant_payments = (
                            fallback_payments
                        )

                    else:

                        db.rollback()

                        return {
                            "received": True,
                            "processed": False,
                            "payment_type":
                                payment_type,
                            "payment_ids":
                                payment_ids,
                            "missing_payment_ids":
                                missing_ids,
                            "message":
                                "Not all bulk participant payment rows were found."
                        }

        # ----------------------------------------------------
        # VERIFY TOTAL
        #
        # /create_payment creates one Payment row per
        # participant, but ONE PayMongo link contains the
        # combined amount.
        # ----------------------------------------------------

        expected_participant_amount = 0

        for participant_payment in participant_payments:

            try:

                row_amount = int(
                    getattr(
                        participant_payment,
                        "amount",
                        0
                    )
                    or 0
                )

            except (
                ValueError,
                TypeError
            ):

                row_amount = 0

            if row_amount <= 0:

                db.rollback()

                return {
                    "received": True,
                    "processed": False,
                    "payment_type":
                        payment_type,
                    "payment_id":
                        participant_payment.id,
                    "message":
                        "Invalid participant payment amount."
                }

            expected_participant_amount += (
                row_amount
            )

        print("=" * 80)
        print(
            "PARTICIPANT AMOUNT VERIFICATION"
        )
        print(
            "PayMongo Amount:",
            paymongo_amount
        )
        print(
            "Expected Amount:",
            expected_participant_amount
        )
        print("=" * 80)

        if (
            paymongo_amount > 0
            and
            paymongo_amount !=
            expected_participant_amount
        ):

            print(
                "PARTICIPANT PAYMENT AMOUNT MISMATCH"
            )

            db.rollback()

            return {
                "received": True,
                "processed": False,
                "payment_type":
                    payment_type,
                "paymongo_amount":
                    paymongo_amount,
                "expected_amount":
                    expected_participant_amount,
                "payment_ids":
                    [
                        p.id
                        for p in participant_payments
                    ],
                "message":
                    "Payment amount does not match participant payment total."
            }

        # ----------------------------------------------------
        # PROCESS EACH PARTICIPANT
        # ----------------------------------------------------

        processed_participants = []

        now = datetime.datetime.now()

        for participant_payment in participant_payments:

            participant_id = getattr(
                participant_payment,
                "participant_id",
                None
            )

            print("=" * 80)
            print(
                "PROCESSING PARTICIPANT"
            )
            print(
                "Payment ID:",
                participant_payment.id
            )
            print(
                "Participant ID:",
                participant_id
            )
            print("=" * 80)

            if not participant_id:

                db.rollback()

                return {
                    "received": True,
                    "processed": False,
                    "payment_type":
                        payment_type,
                    "payment_id":
                        participant_payment.id,
                    "message":
                        "Participant ID is missing."
                }

            # ------------------------------------------------
            # LOCK PARTICIPANT
            # ------------------------------------------------

            participant = (
                db.query(
                    Participant
                )
                .filter(
                    Participant.id ==
                    participant_id
                )
                .with_for_update()
                .first()
            )

            if not participant:

                db.rollback()

                return {
                    "received": True,
                    "processed": False,
                    "payment_type":
                        payment_type,
                    "payment_id":
                        participant_payment.id,
                    "participant_id":
                        participant_id,
                    "message":
                        "Participant not found."
                }

            print(
                "Participant:",
                getattr(
                    participant,
                    "fname",
                    ""
                ),
                getattr(
                    participant,
                    "lname",
                    ""
                )
            )

            # ------------------------------------------------
            # ITEM FLAGS
            #
            # IMPORTANT:
            #
            # The local Payment row is the source of truth.
            #
            # ------------------------------------------------

            tshirt_selected = bool(
                getattr(
                    participant_payment,
                    "tshirt_selected",
                    False
                )
            )

            lanyard_selected = bool(
                getattr(
                    participant_payment,
                    "lanyard_selected",
                    False
                )
            )

            tshirt_size = getattr(
                participant_payment,
                "tshirt_size",
                None
            )

            print(
                "T-Shirt Selected:",
                tshirt_selected
            )

            print(
                "Lanyard Selected:",
                lanyard_selected
            )

            print(
                "T-Shirt Size:",
                tshirt_size
            )

            # ------------------------------------------------
            # SAVE PAYMONGO IDENTIFIERS
            # ------------------------------------------------

            if (
                paymongo_link_id
                and hasattr(
                    participant_payment,
                    "paymongo_link_id"
                )
            ):

                participant_payment.paymongo_link_id = (
                    paymongo_link_id
                )

            if (
                paymongo_payment_id
                and hasattr(
                    participant_payment,
                    "paymongo_payment_id"
                )
            ):

                participant_payment.paymongo_payment_id = (
                    paymongo_payment_id
                )

            if (
                paymongo_reference
                and hasattr(
                    participant_payment,
                    "paymongo_reference"
                )
            ):

                participant_payment.paymongo_reference = (
                    paymongo_reference
                )

            # ------------------------------------------------
            # MARK LOCAL PAYMENT PAID
            #
            # This is intentionally idempotent.
            # If PayMongo sends the webhook twice, it stays Paid.
            # ------------------------------------------------

            previous_payment_status = str(
                getattr(
                    participant_payment,
                    "status",
                    ""
                )
                or ""
            ).strip().lower()

            participant_payment.status = (
                "Paid"
            )

            if hasattr(
                participant_payment,
                "paid_at"
            ):

                if (
                    previous_payment_status !=
                    "paid"
                ):

                    participant_payment.paid_at = (
                        now
                    )

                elif not participant_payment.paid_at:

                    participant_payment.paid_at = (
                        now
                    )

            # ------------------------------------------------
            # T-SHIRT
            # ------------------------------------------------

            if tshirt_selected:

                print(
                    "Updating T-Shirt -> Paid"
                )

                if hasattr(
                    participant,
                    "tshirt_status"
                ):

                    participant.tshirt_status = (
                        "Paid"
                    )

                if (
                    tshirt_size
                    and
                    hasattr(
                        participant,
                        "tshirt_size"
                    )
                ):

                    participant.tshirt_size = (
                        tshirt_size
                    )

            # ------------------------------------------------
            # LANYARD
            # ------------------------------------------------

            if lanyard_selected:

                print(
                    "Updating Lanyard -> Paid"
                )

                if hasattr(
                    participant,
                    "lanyard_status"
                ):

                    participant.lanyard_status = (
                        "Paid"
                    )

                else:

                    print(
                        "WARNING: Participant has no "
                        "lanyard_status column."
                    )

            # ------------------------------------------------
            # REGISTRATION STATUS
            #
            # Lanyard is mandatory.
            #
            # IMPORTANT:
            # Only change registration status based on the
            # resulting lanyard status.
            # ------------------------------------------------

            lanyard_status = str(
                getattr(
                    participant,
                    "lanyard_status",
                    ""
                )
                or ""
            ).strip().lower()

            lanyard_paid = (
                lanyard_status ==
                "paid"
            )

            if hasattr(
                participant,
                "registration_status"
            ):

                if lanyard_paid:

                    participant.registration_status = (
                        "Confirmed"
                    )

                # Do NOT force Pending here if this webhook
                # was only for another optional item.
                #
                # Existing registration state is preserved
                # when the mandatory lanyard is still unpaid.

            # ------------------------------------------------
            # UPDATED TIME
            # ------------------------------------------------

            if hasattr(
                participant,
                "updated_at"
            ):

                participant.updated_at = (
                    now
                )

            # ------------------------------------------------
            # ADD RESULT
            # ------------------------------------------------

            processed_participants.append({
                "payment_id":
                    participant_payment.id,

                "participant_id":
                    participant.id,

                "registration_number":
                    getattr(
                        participant,
                        "registration_number",
                        None
                    ),

                "payment_status":
                    participant_payment.status,

                "tshirt_selected":
                    tshirt_selected,

                "tshirt_status":
                    getattr(
                        participant,
                        "tshirt_status",
                        None
                    ),

                "tshirt_size":
                    getattr(
                        participant,
                        "tshirt_size",
                        None
                    ),

                "lanyard_selected":
                    lanyard_selected,

                "lanyard_status":
                    getattr(
                        participant,
                        "lanyard_status",
                        None
                    ),

                "registration_status":
                    getattr(
                        participant,
                        "registration_status",
                        None
                    )
            })

        # ====================================================
        # FLUSH EVERYTHING
        # ====================================================

        try:

            db.flush()

            print("=" * 80)
            print(
                "ALL PARTICIPANT CHANGES FLUSHED"
            )
            print("=" * 80)

        except Exception as e:

            db.rollback()

            print(
                "Participant flush failed:",
                repr(e)
            )

            return JSONResponse(
                status_code=500,
                content={
                    "received": True,
                    "processed": False,
                    "payment_type":
                        payment_type,
                    "message":
                        "Participant database update failed."
                }
            )

        # ====================================================
        # COMMIT EVERYTHING AS ONE TRANSACTION
        # ====================================================

        try:

            db.commit()

            print("=" * 80)
            print(
                "PARTICIPANT PAYMENT DATABASE UPDATE SUCCESSFUL"
            )
            print(
                "Participant Count:",
                len(
                    processed_participants
                )
            )
            print("=" * 80)

        except Exception as e:

            db.rollback()

            print(
                "Participant commit failed:",
                repr(e)
            )

            return JSONResponse(
                status_code=500,
                content={
                    "received": True,
                    "processed": False,
                    "payment_type":
                        payment_type,
                    "message":
                        "Participant database update failed."
                }
            )

        # ====================================================
        # REFRESH AND VERIFY
        # ====================================================

        final_participants = []

        for participant_payment in participant_payments:

            try:

                db.refresh(
                    participant_payment
                )

            except Exception as e:

                print(
                    "Payment refresh failed:",
                    repr(e)
                )

            participant_id = getattr(
                participant_payment,
                "participant_id",
                None
            )

            participant = None

            if participant_id:

                participant = (
                    db.query(
                        Participant
                    )
                    .filter(
                        Participant.id ==
                        participant_id
                    )
                    .first()
                )

            if not participant:
                continue

            final_lanyard_status = getattr(
                participant,
                "lanyard_status",
                None
            )

            final_tshirt_status = getattr(
                participant,
                "tshirt_status",
                None
            )

            final_registration_status = getattr(
                participant,
                "registration_status",
                None
            )

            final_lanyard_paid = (
                str(
                    final_lanyard_status
                    or ""
                ).strip().lower()
                ==
                "paid"
            )

            final_participants.append({
                "payment_id":
                    participant_payment.id,

                "participant_id":
                    participant.id,

                "registration_number":
                    getattr(
                        participant,
                        "registration_number",
                        None
                    ),

                "payment_status":
                    participant_payment.status,

                "tshirt_selected":
                    bool(
                        getattr(
                            participant_payment,
                            "tshirt_selected",
                            False
                        )
                    ),

                "tshirt_status":
                    final_tshirt_status,

                "lanyard_selected":
                    bool(
                        getattr(
                            participant_payment,
                            "lanyard_selected",
                            False
                        )
                    ),

                "lanyard_status":
                    final_lanyard_status,

                "lanyard_paid":
                    final_lanyard_paid,

                "registration_status":
                    final_registration_status
            })

            print("=" * 80)
            print(
                "FINAL PARTICIPANT STATUS"
            )
            print(
                "Payment ID:",
                participant_payment.id
            )
            print(
                "Participant ID:",
                participant.id
            )
            print(
                "Payment Status:",
                participant_payment.status
            )
            print(
                "T-Shirt Status:",
                final_tshirt_status
            )
            print(
                "Lanyard Status:",
                final_lanyard_status
            )
            print(
                "Registration Status:",
                final_registration_status
            )
            print("=" * 80)

        # ====================================================
        # PARTICIPANT EMAIL
        #
        # Send confirmation for each participant.
        # A failed email must NOT undo the successful payment.
        # ====================================================

        email_results = []

        for participant_payment in participant_payments:

            participant_id = getattr(
                participant_payment,
                "participant_id",
                None
            )

            if not participant_id:
                continue

            participant = (
                db.query(
                    Participant
                )
                .filter(
                    Participant.id ==
                    participant_id
                )
                .first()
            )

            if not participant:
                continue

            participant_email = getattr(
                participant,
                "email",
                None
            )

            if not participant_email:

                print(
                    "Participant Gmail skipped: no email.",
                    participant.id
                )

                email_results.append({
                    "participant_id":
                        participant.id,
                    "sent":
                        False
                })

                continue

            gmail_success = False

            try:

                gmail_success = bool(
                    await send_participant_payment_confirmation_email(
                        participant,
                        participant_payment
                    )
                )

                print(
                    "Participant Gmail Result:",
                    participant.id,
                    gmail_success
                )

            except Exception as e:

                print(
                    "Participant Gmail failed:",
                    participant.id,
                    repr(e)
                )

            email_results.append({
                "participant_id":
                    participant.id,
                "sent":
                    gmail_success
            })

        # ====================================================
        # FINAL RESULT
        # ====================================================

        all_payment_rows_paid = all(
            str(
                getattr(
                    p,
                    "status",
                    ""
                )
                or ""
            ).strip().lower()
            ==
            "paid"
            for p in participant_payments
        )

        all_lanyards_paid = all(
            item.get(
                "lanyard_paid",
                False
            )
            for item in final_participants
        )

        is_bulk = (
            len(
                participant_payments
            ) > 1
            or
            payment_type == "bulk"
        )

        print("=" * 80)
        print(
            "PARTICIPANT PAYMENT COMPLETED"
        )
        print(
            "Bulk:",
            is_bulk
        )
        print(
            "Payment Rows:",
            len(
                participant_payments
            )
        )
        print(
            "All Payment Rows Paid:",
            all_payment_rows_paid
        )
        print(
            "All Lanyards Paid:",
            all_lanyards_paid
        )
        print("=" * 80)

        return {
            "received": True,
            "processed": True,

            "payment_type":
                "bulk"
                if is_bulk
                else "participant",

            "event_id":
                event_id,

            "payment_id":
                payment.id,

            "payment_ids":
                [
                    p.id
                    for p in participant_payments
                ],

            "participant_ids":
                [
                    p.participant_id
                    for p in participant_payments
                ],

            "participant_count":
                len(
                    participant_payments
                ),

            "participants":
                final_participants,

            "payment_status":
                "Paid"
                if all_payment_rows_paid
                else "Pending",

            "payment_success":
                all_payment_rows_paid,

            "all_lanyards_paid":
                all_lanyards_paid,

            "paymongo_amount":
                paymongo_amount,

            "expected_amount":
                expected_participant_amount,

            "paymongo_reference":
                paymongo_reference,

            "paymongo_payment_id":
                paymongo_payment_id,

            "paymongo_link_id":
                paymongo_link_id,

            "email_results":
                email_results
        }

    # ========================================================
    # ========================================================
    # STORE PAYMENT
    # ========================================================
    # ========================================================

    elif payment_type == "store":

        print("=" * 80)
        print(
            "PROCESSING STORE PAYMENT"
        )
        print("=" * 80)

        # ----------------------------------------------------
        # RESOLVE STORE ORDER ID
        # ----------------------------------------------------

        if not store_order_id:

            store_order_id = getattr(
                payment,
                "store_order_id",
                None
            )

            if store_order_id:

                store_order_id = str(
                    store_order_id
                ).strip()

        if not store_order_id:

            db.rollback()

            return {
                "received": True,
                "processed": False,
                "payment_type": "store",
                "payment_id":
                    payment.id,
                "message":
                    "Store order ID is missing."
            }

        # ----------------------------------------------------
        # FIND ALL STORE PAYMENT ROWS
        # ----------------------------------------------------

        store_payments = (
            db.query(
                Payment
            )
            .filter(
                Payment.store_order_id ==
                store_order_id,
                Payment.payment_type.ilike(
                    "Store"
                )
            )
            .order_by(
                Payment.id.asc()
            )
            .with_for_update()
            .all()
        )

        # ----------------------------------------------------
        # FALLBACK LINK ID
        # ----------------------------------------------------

        if (
            not store_payments
            and paymongo_link_id
        ):

            store_payments = (
                db.query(
                    Payment
                )
                .filter(
                    Payment.paymongo_link_id ==
                    paymongo_link_id,
                    Payment.payment_type.ilike(
                        "Store"
                    )
                )
                .order_by(
                    Payment.id.asc()
                )
                .with_for_update()
                .all()
            )

        if not store_payments:

            db.rollback()

            return {
                "received": True,
                "processed": False,
                "payment_type": "store",
                "store_order_id":
                    store_order_id,
                "message":
                    "No store payment rows found for this order."
            }

        print(
            "Store payment rows:",
            len(
                store_payments
            )
        )

        # ----------------------------------------------------
        # SAVE PAYMONGO INFORMATION
        # ----------------------------------------------------

        for store_payment in store_payments:

            if (
                paymongo_link_id
                and hasattr(
                    store_payment,
                    "paymongo_link_id"
                )
            ):

                store_payment.paymongo_link_id = (
                    paymongo_link_id
                )

            if (
                paymongo_payment_id
                and hasattr(
                    store_payment,
                    "paymongo_payment_id"
                )
            ):

                store_payment.paymongo_payment_id = (
                    paymongo_payment_id
                )

            if (
                paymongo_reference
                and hasattr(
                    store_payment,
                    "paymongo_reference"
                )
            ):

                store_payment.paymongo_reference = (
                    paymongo_reference
                )

        # ----------------------------------------------------
        # CALCULATE CART TOTAL
        # ----------------------------------------------------

        expected_cart_amount = 0

        for store_payment in store_payments:

            try:

                row_amount = int(
                    getattr(
                        store_payment,
                        "amount",
                        0
                    )
                    or 0
                )

            except (
                ValueError,
                TypeError
            ):

                row_amount = 0

            if row_amount <= 0:

                db.rollback()

                return {
                    "received": True,
                    "processed": False,
                    "payment_type":
                        "store",
                    "store_order_id":
                        store_order_id,
                    "payment_id":
                        store_payment.id,
                    "message":
                        "Invalid store payment row amount."
                }

            expected_cart_amount += (
                row_amount
            )

        # ----------------------------------------------------
        # VERIFY AMOUNT
        # ----------------------------------------------------

        if (
            paymongo_amount > 0
            and
            paymongo_amount !=
            expected_cart_amount
        ):

            print(
                "STORE CART AMOUNT MISMATCH"
            )

            db.rollback()

            return {
                "received": True,
                "processed": False,
                "payment_type":
                    "store",
                "store_order_id":
                    store_order_id,
                "paymongo_amount":
                    paymongo_amount,
                "expected_amount":
                    expected_cart_amount,
                "message":
                    "Payment amount does not match the store cart total."
            }

        # ----------------------------------------------------
        # CHECK ALREADY PAID
        # ----------------------------------------------------

        all_already_paid = all(
            str(
                getattr(
                    p,
                    "status",
                    ""
                )
                or ""
            ).strip().lower()
            ==
            "paid"
            for p in store_payments
        )

        if all_already_paid:

            try:
                db.commit()
            except Exception:
                db.rollback()

            store_receipt_sent = False
            try:
                store_receipt_sent = bool(
                    await send_store_payment_receipt_email(
                        store_payments,
                        store_order_id
                    )
                )
            except Exception as e:
                print("STORE RECEIPT EMAIL FAILED:", repr(e))

            return {
                "received": True,
                "processed": True,
                "already_processed": True,
                "payment_type":
                    "store",
                "store_order_id":
                    store_order_id,
                "payment_id":
                    payment.id,
                "payment_ids":
                    [
                        p.id
                        for p in store_payments
                    ],
                "payment_status":
                    "Paid",
                "payment_success":
                    True,
                "store_receipt_email_sent":
                    store_receipt_sent
            }

        # ----------------------------------------------------
        # PROCESS UNPAID STORE ROWS
        # ----------------------------------------------------

        unpaid_payments = [
            p
            for p in store_payments
            if str(
                getattr(
                    p,
                    "status",
                    ""
                )
                or ""
            ).strip().lower()
            != "paid"
        ]

        store_items_to_update = []

        # ----------------------------------------------------
        # VALIDATE ALL INVENTORY FIRST
        # ----------------------------------------------------

        for store_payment in unpaid_payments:

            store_item_id = getattr(
                store_payment,
                "store_item_id",
                None
            )

            if not store_item_id:

                db.rollback()

                return {
                    "received": True,
                    "processed": False,
                    "payment_type":
                        "store",
                    "store_order_id":
                        store_order_id,
                    "payment_id":
                        store_payment.id,
                    "message":
                        "Store item ID is missing."
                }

            try:

                store_quantity = int(
                    getattr(
                        store_payment,
                        "store_quantity",
                        1
                    )
                    or 1
                )

            except (
                ValueError,
                TypeError
            ):

                store_quantity = 0

            if store_quantity <= 0:

                db.rollback()

                return {
                    "received": True,
                    "processed": False,
                    "payment_type":
                        "store",
                    "store_order_id":
                        store_order_id,
                    "payment_id":
                        store_payment.id,
                    "message":
                        "Invalid store quantity."
                }

            store_item = (
                db.query(
                    StoreItem
                )
                .filter(
                    StoreItem.id ==
                    store_item_id
                )
                .with_for_update()
                .first()
            )

            if not store_item:

                db.rollback()

                return {
                    "received": True,
                    "processed": False,
                    "payment_type":
                        "store",
                    "store_order_id":
                        store_order_id,
                    "payment_id":
                        store_payment.id,
                    "store_item_id":
                        store_item_id,
                    "message":
                        "Store item not found."
                }

            try:

                current_inventory = int(
                    store_item.quantity
                    or 0
                )

            except (
                ValueError,
                TypeError
            ):

                current_inventory = 0

            if current_inventory < store_quantity:

                db.rollback()

                return {
                    "received": True,
                    "processed": False,
                    "payment_type":
                        "store",
                    "store_order_id":
                        store_order_id,
                    "payment_id":
                        store_payment.id,
                    "store_item_id":
                        store_item.id,
                    "item_name":
                        store_item.item_name,
                    "requested_quantity":
                        store_quantity,
                    "available_quantity":
                        current_inventory,
                    "message":
                        "Insufficient inventory."
                }

            store_items_to_update.append({
                "payment":
                    store_payment,
                "store_item":
                    store_item,
                "quantity":
                    store_quantity
            })

        # ----------------------------------------------------
        # PROCESS ALL VALIDATED STORE ITEMS
        # ----------------------------------------------------

        processed_items = []

        now = datetime.datetime.now()

        for entry in store_items_to_update:

            store_payment = entry[
                "payment"
            ]

            store_item = entry[
                "store_item"
            ]

            store_quantity = entry[
                "quantity"
            ]

            # ------------------------------------------------
            # MARK PAID
            # ------------------------------------------------

            store_payment.status = (
                "Paid"
            )

            if hasattr(
                store_payment,
                "paid_at"
            ):

                store_payment.paid_at = (
                    now
                )

            # ------------------------------------------------
            # PAYMONGO IDS
            # ------------------------------------------------

            if (
                paymongo_link_id
                and hasattr(
                    store_payment,
                    "paymongo_link_id"
                )
            ):

                store_payment.paymongo_link_id = (
                    paymongo_link_id
                )

            if (
                paymongo_payment_id
                and hasattr(
                    store_payment,
                    "paymongo_payment_id"
                )
            ):

                store_payment.paymongo_payment_id = (
                    paymongo_payment_id
                )

            if (
                paymongo_reference
                and hasattr(
                    store_payment,
                    "paymongo_reference"
                )
            ):

                store_payment.paymongo_reference = (
                    paymongo_reference
                )

            # ------------------------------------------------
            # REDUCE INVENTORY
            # ------------------------------------------------

            old_inventory = int(
                store_item.quantity
                or 0
            )

            store_item.quantity = (
                old_inventory -
                store_quantity
            )

            if hasattr(
                store_item,
                "updated_at"
            ):

                store_item.updated_at = (
                    now
                )

            processed_items.append({
                "payment_id":
                    store_payment.id,

                "store_item_id":
                    store_item.id,

                "item_name":
                    store_item.item_name,

                "quantity":
                    store_quantity,

                "remaining_inventory":
                    store_item.quantity,

                "payment_status":
                    store_payment.status
            })

        # ----------------------------------------------------
        # COMMIT STORE TRANSACTION
        # ----------------------------------------------------

        try:

            db.commit()

        except Exception as e:

            db.rollback()

            print(
                "Store commit failed:",
                repr(e)
            )

            return JSONResponse(
                status_code=500,
                content={
                    "received": True,
                    "processed": False,
                    "payment_type":
                        "store",
                    "store_order_id":
                        store_order_id,
                    "message":
                        "Store cart database update failed."
                }
            )

        # ----------------------------------------------------
        # FINAL STATUS
        # ----------------------------------------------------

        final_order_status = (
            "Paid"
            if all(
                str(
                    getattr(
                        p,
                        "status",
                        ""
                    )
                    or ""
                ).strip().lower()
                ==
                "paid"
                for p in store_payments
            )
            else
            "Pending"
        )

        # ----------------------------------------------------
        # STORE RECEIPT EMAIL
        # ----------------------------------------------------
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

        print("=" * 80)
        print(
            "STORE PAYMENT COMPLETED"
        )
        print(
            "Store Order ID:",
            store_order_id
        )
        print(
            "Payment Rows:",
            len(
                store_payments
            )
        )
        print(
            "Order Status:",
            final_order_status
        )
        print("=" * 80)

        return {
            "received": True,
            "processed": True,
            "payment_type":
                "store",
            "event_id":
                event_id,
            "store_order_id":
                store_order_id,
            "payment_id":
                payment.id,
            "payment_ids":
                [
                    p.id
                    for p in store_payments
                ],
            "item_count":
                len(
                    store_payments
                ),
            "items":
                processed_items,
            "paymongo_amount":
                paymongo_amount,
            "expected_cart_amount":
                expected_cart_amount,
            "total_amount":
                expected_cart_amount / 100,
            "payment_status":
                final_order_status,
            "payment_success":
                final_order_status == "Paid",
            "store_receipt_email_sent":
                store_receipt_sent,
            "paymongo_reference":
                paymongo_reference,
            "paymongo_payment_id":
                paymongo_payment_id,
            "paymongo_link_id":
                paymongo_link_id
        }

    # ========================================================
    # UNKNOWN PAYMENT TYPE
    # ========================================================

    db.rollback()

    print("=" * 80)
    print(
        "UNSUPPORTED PAYMENT TYPE"
    )
    print(
        "Payment Type:",
        payment_type
    )
    print("=" * 80)

    return {
        "received": True,
        "processed": False,
        "payment_id":
            payment.id,
        "payment_type":
            payment_type,
        "message":
            "Payment type is not supported."
    }
