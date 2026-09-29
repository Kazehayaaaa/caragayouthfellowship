"""Routes: payments."""

from fastapi import Depends
from fastapi import HTTPException
from typing import List
from sqlalchemy.orm import Session
import datetime
import requests
import uuid
from fastapi import APIRouter

from app.config import (
    PAYMONGO_API_URL,
    PAYMONGO_SECRET_KEY,
)
from app.database import (
    get_db,
)
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

# ======================================================
# VIEW PARTICIPANT PAYMENT STATUS
# ======================================================

@router.get("/payment_status/{participant_id}")
def payment_status(
    participant_id: int,
    db: Session = Depends(get_db)
):

    print("=" * 70)
    print("PAYMENT STATUS CHECK")
    print("Participant ID:", participant_id)
    print("=" * 70)

    # ==================================================
    # 1. FIND PARTICIPANT
    # ==================================================

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

    # ==================================================
    # 2. FULL NAME
    # ==================================================

    fullname = " ".join(
        part
        for part in [
            participant.fname,
            participant.mname,
            participant.lname
        ]
        if part and str(part).strip()
    ).strip()

    # ==================================================
    # 3. ACTIVE REGISTRATION ITEMS
    # ==================================================

    registration_items = (
        db.query(RegistrationItem)
        .filter(
            RegistrationItem.is_active == True
        )
        .all()
    )

    # ==================================================
    # 4. FIND T-SHIRT
    # ==================================================

    tshirt_item = next(
        (
            item
            for item in registration_items
            if item.item_name
            and item.item_name.strip().lower() == "t-shirt"
        ),
        None
    )

    # ==================================================
    # 5. FIND LANYARD
    # ==================================================

    lanyard_item = next(
        (
            item
            for item in registration_items
            if item.item_name
            and item.item_name.strip().lower() == "lanyard"
        ),
        None
    )

    # ==================================================
    # 6. PRICES
    # ==================================================

    tshirt_price = (
        int(tshirt_item.price or 0)
        if tshirt_item
        else 0
    )

    lanyard_price = (
        int(lanyard_item.price or 0)
        if lanyard_item
        else 0
    )

    # ==================================================
    # 7. GET ALL PAYMENTS
    # ==================================================

    payments = (
        db.query(Payment)
        .filter(
            Payment.participant_id == participant.id
        )
        .order_by(
            Payment.created_at.desc(),
            Payment.id.desc()
        )
        .all()
    )

    # ==================================================
    # 8. SUCCESSFUL PAYMENT STATUSES
    # ==================================================

    successful_statuses = {
        "paid",
        "success",
        "succeeded",
        "completed"
    }

    # ==================================================
    # 9. CHECK T-SHIRT PAYMENT
    # ==================================================

    tshirt_paid = any(
        bool(
            getattr(
                p,
                "tshirt_selected",
                False
            )
        )
        and
        str(
            getattr(
                p,
                "status",
                ""
            )
            or ""
        ).strip().lower() in successful_statuses
        for p in payments
    )

    # ==================================================
    # 10. CHECK LANYARD PAYMENT
    # ==================================================

    lanyard_paid = any(
        bool(
            getattr(
                p,
                "lanyard_selected",
                False
            )
        )
        and
        str(
            getattr(
                p,
                "status",
                ""
            )
            or ""
        ).strip().lower() in successful_statuses
        for p in payments
    )

    # ==================================================
    # 11. FALLBACK TO PARTICIPANT ITEM STATUS
    # ==================================================

    participant_tshirt_status = str(
        getattr(
            participant,
            "tshirt_status",
            ""
        )
        or ""
    ).strip().lower()

    participant_lanyard_status = str(
        getattr(
            participant,
            "lanyard_status",
            ""
        )
        or ""
    ).strip().lower()

    if participant_tshirt_status == "paid":
        tshirt_paid = True

    if participant_lanyard_status == "paid":
        lanyard_paid = True

    # ==================================================
    # 12. UPDATE PARTICIPANT ITEM STATUS
    # ==================================================

    if hasattr(participant, "tshirt_status"):
        participant.tshirt_status = (
            "Paid"
            if tshirt_paid
            else "Unpaid"
        )

    if hasattr(participant, "lanyard_status"):
        participant.lanyard_status = (
            "Paid"
            if lanyard_paid
            else "Unpaid"
        )

    # ==================================================
    # 13. MANDATORY PAYMENT STATUS
    #
    # Lanyard is mandatory.
    # T-shirt is optional.
    # ==================================================

    mandatory_payment_complete = (
        lanyard_paid
        if lanyard_item
        else True
    )

    # ==================================================
    # 14. REGISTRATION STATUS
    # ==================================================

    if mandatory_payment_complete:

        if hasattr(
            participant,
            "registration_status"
        ):
            participant.registration_status = "Confirmed"

    # ==================================================
    # 15. UPDATED TIMESTAMP
    # ==================================================

    if hasattr(
        participant,
        "updated_at"
    ):
        participant.updated_at = datetime.datetime.now()

    db.commit()

    # ==================================================
    # 16. PAID ITEMS
    # ==================================================

    paid_items = []

    if tshirt_item and tshirt_paid:
        paid_items.append("T-Shirt")

    if lanyard_item and lanyard_paid:
        paid_items.append("Lanyard")

    # ==================================================
    # 17. ALL ACTUAL REGISTRATION ITEMS
    #
    # IMPORTANT:
    #
    # DO NOT build this from previous Payment rows.
    #
    # We need to know what items are actually available
    # for this registration.
    # ==================================================

    registration_item_names = []

    if tshirt_item:
        registration_item_names.append("T-Shirt")

    if lanyard_item:
        registration_item_names.append("Lanyard")

    # ==================================================
    # 18. REMAINING ITEMS
    #
    # This is the critical fix.
    # ==================================================

    remaining_items = []

    if tshirt_item and not tshirt_paid:
        remaining_items.append("T-Shirt")

    if lanyard_item and not lanyard_paid:
        remaining_items.append("Lanyard")

    # ==================================================
    # 19. REMAINING AMOUNT
    # ==================================================

    remaining_amount = 0

    if tshirt_item and not tshirt_paid:
        remaining_amount += tshirt_price

    if lanyard_item and not lanyard_paid:
        remaining_amount += lanyard_price

    # ==================================================
    # 20. ALL ITEMS PAID
    #
    # This now checks the ACTUAL registration items.
    #
    # Example:
    #
    # T-Shirt = Unpaid
    # Lanyard = Paid
    #
    # all_items_paid = False
    # ==================================================

    all_items_paid = (
        len(registration_item_names) > 0
        and
        len(remaining_items) == 0
    )

    # ==================================================
    # 21. CAN PROCEED TO PAYMENT
    #
    # The participant can proceed whenever there is
    # something remaining to pay.
    # ==================================================

    can_proceed_to_payment = (
        len(remaining_items) > 0
        and remaining_amount > 0
    )

    # ==================================================
    # 22. PAYMENT SUCCESS
    #
    # Registration success is based on mandatory
    # Lanyard payment.
    # ==================================================

    payment_success = (
        mandatory_payment_complete
    )

    # ==================================================
    # 23. REGISTRATION STATUS
    # ==================================================

    registration_status = getattr(
        participant,
        "registration_status",
        None
    )

    # ==================================================
    # 24. DEDUPLICATE PAYMENT HISTORY
    #
    # Keep the newest payment record for the same
    # payment-item combination.
    #
    # This prevents old duplicate lanyard rows from
    # being displayed repeatedly.
    # ==================================================

    history_payments = []

    seen_payment_combinations = set()

    for p in payments:

        tshirt_selected = bool(
            getattr(
                p,
                "tshirt_selected",
                False
            )
        )

        lanyard_selected = bool(
            getattr(
                p,
                "lanyard_selected",
                False
            )
        )

        # Normalize the payment combination.
        payment_combination = (
            tshirt_selected,
            lanyard_selected
        )

        status_normalized = str(
            getattr(
                p,
                "status",
                ""
            )
            or ""
        ).strip().lower()

        # --------------------------------------------------
        # For successful payments:
        #
        # Only show the newest successful payment for the
        # same combination of items.
        # --------------------------------------------------

        if status_normalized in successful_statuses:

            if payment_combination in seen_payment_combinations:
                continue

            seen_payment_combinations.add(
                payment_combination
            )

        history_payments.append(p)

    # ==================================================
    # 25. DEBUG LOGGING
    # ==================================================

    print(
        "Participant T-Shirt Status:",
        getattr(
            participant,
            "tshirt_status",
            None
        )
    )

    print(
        "Participant Lanyard Status:",
        getattr(
            participant,
            "lanyard_status",
            None
        )
    )

    print(
        "T-Shirt Paid:",
        tshirt_paid
    )

    print(
        "Lanyard Paid:",
        lanyard_paid
    )

    print(
        "Mandatory Payment Complete:",
        mandatory_payment_complete
    )

    print(
        "Payment Success:",
        payment_success
    )

    print(
        "Registration Items:",
        registration_item_names
    )

    print(
        "Paid Items:",
        paid_items
    )

    print(
        "Remaining Items:",
        remaining_items
    )

    print(
        "Remaining Amount:",
        remaining_amount
    )

    print(
        "All Items Paid:",
        all_items_paid
    )

    print(
        "Can Proceed To Payment:",
        can_proceed_to_payment
    )

    print(
        "Registration Status:",
        registration_status
    )

    print("=" * 70)

    # ==================================================
    # 26. RETURN RESPONSE
    # ==================================================

    return {

        # ==================================================
        # PARTICIPANT
        # ==================================================

        "participant_id":
            participant.id,

        "registration_number":
            participant.registration_number,

        "fullname":
            fullname,

        "participant_type":
            participant.participant_type,

        # ==================================================
        # MAIN PAYMENT FLAGS
        # ==================================================

        "mandatory_payment_complete":
            mandatory_payment_complete,

        "payment_success":
            payment_success,

        "all_items_paid":
            all_items_paid,

        "can_proceed_to_payment":
            can_proceed_to_payment,

        # ==================================================
        # ITEM LISTS
        # ==================================================

        "paid_items":
            paid_items,

        "requested_items":
            registration_item_names,

        "remaining_items":
            remaining_items,

        # ==================================================
        # REMAINING PAYMENT
        # ==================================================

        "remaining_amount":
            remaining_amount,

        "remaining_amount_display":
            f"₱{remaining_amount / 100:,.2f}",

        # ==================================================
        # EXPLICIT LANYARD FLAG
        # ==================================================

        "lanyard_paid":
            lanyard_paid,

        # ==================================================
        # EXPLICIT T-SHIRT FLAG
        # ==================================================

        "tshirt_paid":
            tshirt_paid,

        # ==================================================
        # T-SHIRT
        # ==================================================

        "tshirt": {

            "item_id":
                tshirt_item.id
                if tshirt_item
                else None,

            "item_name":
                tshirt_item.item_name
                if tshirt_item
                else "T-Shirt",

            "price":
                tshirt_price,

            "price_display":
                f"₱{tshirt_price / 100:,.2f}",

            "status":
                "Paid"
                if tshirt_paid
                else "Unpaid",

            "paid":
                tshirt_paid,

            "remaining":
                not tshirt_paid

        },

        # ==================================================
        # LANYARD
        # ==================================================

        "lanyard": {

            "item_id":
                lanyard_item.id
                if lanyard_item
                else None,

            "item_name":
                lanyard_item.item_name
                if lanyard_item
                else "Lanyard",

            "price":
                lanyard_price,

            "price_display":
                f"₱{lanyard_price / 100:,.2f}",

            "status":
                "Paid"
                if lanyard_paid
                else "Unpaid",

            "paid":
                lanyard_paid,

            "remaining":
                not lanyard_paid

        },

        # ==================================================
        # PARTICIPANT ITEM STATUS
        # ==================================================

        "tshirt_status":
            getattr(
                participant,
                "tshirt_status",
                None
            ),

        "lanyard_status":
            getattr(
                participant,
                "lanyard_status",
                None
            ),

        # ==================================================
        # REGISTRATION STATUS
        # ==================================================

        "registration_status":
            registration_status,

        # ==================================================
        # PAYMENT HISTORY
        # ==================================================

        "payments": [

            {

                "payment_id":
                    p.id,

                "amount":
                    p.amount,

                "amount_display":
                    f"₱{p.amount / 100:,.2f}",

                "status":
                    p.status,

                "tshirt_selected":
                    bool(
                        getattr(
                            p,
                            "tshirt_selected",
                            False
                        )
                    ),

                "lanyard_selected":
                    bool(
                        getattr(
                            p,
                            "lanyard_selected",
                            False
                        )
                    ),

                "tshirt_size":
                    getattr(
                        p,
                        "tshirt_size",
                        None
                    ),

                "checkout_url":
                    getattr(
                        p,
                        "checkout_url",
                        None
                    ),

                "paymongo_reference":
                    getattr(
                        p,
                        "paymongo_reference",
                        None
                    ),

                "paymongo_payment_id":
                    getattr(
                        p,
                        "paymongo_payment_id",
                        None
                    ),

                "paymongo_link_id":
                    getattr(
                        p,
                        "paymongo_link_id",
                        None
                    ),

                "created_at":
                    p.created_at,

                "paid_at":
                    getattr(
                        p,
                        "paid_at",
                        None
                    )

            }

            for p in history_payments

        ]
    }
    
    






# ======================================================
# CREATE PAYMONGO PAYMENT
# SUPPORTS SINGLE + BULK PARTICIPANTS
# ======================================================

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
    print("CREATE PAYMENT REQUEST")
    print("=" * 70)

    # ==================================================
    # DETERMINE PARTICIPANT IDS
    # ==================================================

    participant_ids = []

    if data.participant_ids:

        for pid in data.participant_ids:

            try:

                participant_id = int(pid)

                if participant_id > 0:
                    participant_ids.append(
                        participant_id
                    )

            except (ValueError, TypeError):

                continue

    elif data.participant_id is not None:

        try:

            participant_id = int(
                data.participant_id
            )

            if participant_id > 0:

                participant_ids = [
                    participant_id
                ]

        except (ValueError, TypeError):

            participant_ids = []

    # ==================================================
    # VALIDATE PARTICIPANTS
    # ==================================================

    if not participant_ids:

        raise HTTPException(
            status_code=400,
            detail=(
                "At least one participant "
                "is required for payment."
            )
        )

    # --------------------------------------------------
    # REMOVE DUPLICATES
    # PRESERVE ORDER
    # --------------------------------------------------

    participant_ids = list(
        dict.fromkeys(
            participant_ids
        )
    )

    # ==================================================
    # DETERMINE PAYMENT TYPE
    # ==================================================

    is_bulk_payment = (
        len(participant_ids) > 1
        or bool(
            getattr(
                data,
                "bulk",
                False
            )
        )
    )

    # ==================================================
    # LOAD PARTICIPANTS
    # ==================================================

    participants = (
        db.query(Participant)
        .filter(
            Participant.id.in_(
                participant_ids
            ),
            Participant.is_archived == 0
        )
        .all()
    )

    # ==================================================
    # CHECK MISSING PARTICIPANTS
    # ==================================================

    found_ids = {
        participant.id
        for participant in participants
    }

    missing_ids = [
        pid
        for pid in participant_ids
        if pid not in found_ids
    ]

    if missing_ids:

        db.rollback()

        raise HTTPException(
            status_code=404,
            detail={
                "message":
                    "One or more participants "
                    "were not found.",

                "missing_participant_ids":
                    missing_ids
            }
        )

    # ==================================================
    # PRESERVE FRONTEND ORDER
    # ==================================================

    participant_map = {
        participant.id:
            participant
        for participant in participants
    }

    participants = [
        participant_map[pid]
        for pid in participant_ids
    ]

    # ==================================================
    # BOOLEAN NORMALIZER
    # ==================================================

    def normalize_bool(value):

        if isinstance(value, bool):
            return value

        if value is None:
            return False

        if isinstance(value, int):
            return value != 0

        if isinstance(value, str):

            return (
                value.strip().lower()
                in {
                    "true",
                    "1",
                    "yes",
                    "on",
                    "selected",
                    "checked"
                }
            )

        return bool(value)

    # ==================================================
    # GLOBAL ITEM VALUES
    #
    # Used for:
    #
    # - Single participant
    # - Backward compatibility
    #
    # Bulk participant-specific T-shirts are handled
    # separately below.
    # ==================================================

    tshirt_value = getattr(
        data,
        "tshirt",
        None
    )

    if tshirt_value is None:

        tshirt_value = getattr(
            data,
            "tshirt_selected",
            False
        )

    lanyard_value = getattr(
        data,
        "lanyard",
        None
    )

    if lanyard_value is None:

        lanyard_value = getattr(
            data,
            "lanyard_selected",
            False
        )

    tshirt_requested = normalize_bool(
        tshirt_value
    )

    lanyard_requested = normalize_bool(
        lanyard_value
    )

    # ==================================================
    # BUILD PARTICIPANT T-SHIRT MAP
    #
    # Example:
    #
    # {
    #     51: "S",
    #     52: "2XL"
    # }
    # ==================================================

    participant_tshirt_map = {}

    raw_tshirt_selections = getattr(
        data,
        "participant_tshirt_selections",
        None
    )

    if raw_tshirt_selections:

        if not isinstance(
            raw_tshirt_selections,
            list
        ):

            db.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid participant "
                    "T-shirt selections."
                )
            )

        for selection in raw_tshirt_selections:

            if not isinstance(
                selection,
                dict
            ):

                continue

            raw_participant_id = (
                selection.get(
                    "participant_id"
                )
            )

            try:

                selection_participant_id = int(
                    raw_participant_id
                )

            except (
                ValueError,
                TypeError
            ):

                continue

            # Only allow participants included
            # in this payment request.
            if (
                selection_participant_id
                not in participant_ids
            ):

                continue

            selected = normalize_bool(
                selection.get(
                    "tshirt_selected",
                    False
                )
            )

            if not selected:
                continue

            requested_size = selection.get(
                "tshirt_size"
            )

            if not requested_size:

                db.rollback()

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Please select a "
                        "T-shirt size for "
                        f"participant "
                        f"{selection_participant_id}."
                    )
                )

            normalized_size = (
                str(requested_size)
                .strip()
                .upper()
            )

            allowed_sizes = {
                "S",
                "M",
                "L",
                "XL",
                "2XL"
            }

            if normalized_size not in allowed_sizes:

                db.rollback()

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Invalid T-shirt size "
                        f"'{normalized_size}' "
                        "for participant "
                        f"{selection_participant_id}. "
                        "Allowed sizes are "
                        "S, M, L, XL, and 2XL."
                    )
                )

            participant_tshirt_map[
                selection_participant_id
            ] = normalized_size

    # ==================================================
    # GLOBAL T-SHIRT SIZE
    #
    # Used for:
    #
    # - Single participant
    # - Older frontend requests
    # - Bulk requests where no individual
    # T-shirt map was supplied
    # ==================================================

    tshirt_size = None

    requested_global_size = getattr(
        data,
        "tshirt_size",
        None
    )

    if requested_global_size:

        tshirt_size = (
            str(requested_global_size)
            .strip()
            .upper()
        )

        allowed_sizes = {
            "S",
            "M",
            "L",
            "XL",
            "2XL"
        }

        if tshirt_size not in allowed_sizes:

            db.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid T-shirt size. "
                    "Please select S, M, L, XL, or 2XL."
                )
            )

    # ==================================================
    # DETERMINE WHETHER THERE IS ANY T-SHIRT
    # ==================================================

    has_participant_tshirts = (
        len(participant_tshirt_map) > 0
    )

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
            detail=(
                "Please select at least one "
                "registration item."
            )
        )

    # ==================================================
    # SINGLE PARTICIPANT T-SHIRT VALIDATION
    # ==================================================

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

    # ==================================================
    # BULK FALLBACK
    #
    # If bulk request does NOT provide individual
    # T-shirt selections, use the old global behavior.
    # ==================================================

    if (
        is_bulk_payment
        and tshirt_requested
        and not participant_tshirt_map
        and not tshirt_size
    ):

        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=(
                "Please select a T-shirt size "
                "for each participant."
            )
        )

    # ==================================================
    # PRICES
    # STORED IN CENTAVOS
    #
    # ₱350 = 35000
    # ₱90  = 9000
    # ==================================================

    TSHIRT_PRICE = 35000
    LANYARD_PRICE = 9000

    successful_statuses = {
        "paid",
        "success",
        "succeeded",
        "completed"
    }

    payment_rows = []

    total_amount = 0

    all_participant_items = []

    participant_payment_summary = []

    # ==================================================
    # PROCESS EACH PARTICIPANT
    # ==================================================

    for participant in participants:

        print()
        print("-" * 70)
        print(
            "PROCESSING PARTICIPANT:",
            participant.id
        )
        print(
            "Registration:",
            participant.registration_number
        )
        print("-" * 70)

        # ==================================================
        # LOAD EXISTING PAYMENTS
        # ==================================================

        payments = (
            db.query(Payment)
            .filter(
                Payment.participant_id ==
                participant.id
            )
            .order_by(
                Payment.created_at.desc()
            )
            .all()
        )

        # ==================================================
        # DETERMINE WHETHER T-SHIRT WAS ALREADY PAID
        # ==================================================

        tshirt_paid = False

        for payment in payments:

            payment_status = str(
                payment.status or ""
            ).strip().lower()

            if (
                bool(
                    getattr(
                        payment,
                        "tshirt_selected",
                        False
                    )
                )
                and
                payment_status
                in successful_statuses
            ):

                tshirt_paid = True
                break

        # ==================================================
        # DETERMINE WHETHER LANYARD WAS ALREADY PAID
        # ==================================================

        lanyard_paid = False

        for payment in payments:

            payment_status = str(
                payment.status or ""
            ).strip().lower()

            if (
                bool(
                    getattr(
                        payment,
                        "lanyard_selected",
                        False
                    )
                )
                and
                payment_status
                in successful_statuses
            ):

                lanyard_paid = True
                break

        # ==================================================
        # FALLBACK TO PARTICIPANT STATUS
        # ==================================================

        if not payments:

            existing_tshirt_status = str(
                getattr(
                    participant,
                    "tshirt_status",
                    ""
                ) or ""
            ).strip().lower()

            if existing_tshirt_status == "paid":
                tshirt_paid = True

            existing_lanyard_status = str(
                getattr(
                    participant,
                    "lanyard_status",
                    ""
                ) or ""
            ).strip().lower()

            if existing_lanyard_status == "paid":
                lanyard_paid = True

        # ==================================================
        # PARTICIPANT-SPECIFIC T-SHIRT
        # ==================================================

        if participant_tshirt_map:

            participant_tshirt_requested = (
                participant.id
                in participant_tshirt_map
            )

            participant_tshirt_size = (
                participant_tshirt_map.get(
                    participant.id
                )
            )

        else:

            # Backward-compatible behavior
            participant_tshirt_requested = (
                tshirt_requested
            )

            participant_tshirt_size = (
                tshirt_size
            )

        # ==================================================
        # LANYARD REQUEST
        # ==================================================

        participant_lanyard_requested = (
            lanyard_requested
        )

        # ==================================================
        # REMOVE ALREADY PAID T-SHIRT
        # ==================================================

        if (
            participant_tshirt_requested
            and tshirt_paid
        ):

            participant_tshirt_requested = False

            participant_tshirt_size = None

        # ==================================================
        # REMOVE ALREADY PAID LANYARD
        # ==================================================

        if (
            participant_lanyard_requested
            and lanyard_paid
        ):

            participant_lanyard_requested = False

        # ==================================================
        # VALIDATE PARTICIPANT T-SHIRT SIZE
        # ==================================================

        if participant_tshirt_requested:

            if not participant_tshirt_size:

                db.rollback()

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Please select a "
                        "T-shirt size for "
                        f"{participant.fname or ''} "
                        f"{participant.lname or ''}."
                    )
                )

            participant_tshirt_size = (
                str(
                    participant_tshirt_size
                )
                .strip()
                .upper()
            )

            if participant_tshirt_size not in {
                "S",
                "M",
                "L",
                "XL",
                "2XL"
            }:

                db.rollback()

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Invalid T-shirt size "
                        f"for participant "
                        f"{participant.id}."
                    )
                )

        # ==================================================
        # CALCULATE PARTICIPANT AMOUNT
        # ==================================================

        participant_amount = 0

        participant_items = []

        if participant_tshirt_requested:

            participant_amount += (
                TSHIRT_PRICE
            )

            participant_items.append(
                f"T-Shirt ({participant_tshirt_size})"
            )

        if participant_lanyard_requested:

            participant_amount += (
                LANYARD_PRICE
            )

            participant_items.append(
                "Lanyard"
            )

        # ==================================================
        # NOTHING LEFT TO PAY
        # ==================================================

        if participant_amount <= 0:

            db.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    "Participant "
                    f"{participant.registration_number} "
                    "has no remaining items to pay."
                )
            )

        # ==================================================
        # CHECK EXISTING PENDING PAYMENT
        # ==================================================

        existing_payment = (
            db.query(Payment)
            .filter(
                Payment.participant_id ==
                participant.id,

                Payment.status ==
                "Pending",

                Payment.tshirt_selected ==
                int(
                    participant_tshirt_requested
                ),

                Payment.lanyard_selected ==
                int(
                    participant_lanyard_requested
                )
            )
            .order_by(
                Payment.created_at.desc()
            )
            .first()
        )

        if existing_payment:

            if existing_payment.checkout_url:

                db.rollback()

                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": (
                            "A pending payment "
                            "already exists for "
                            "participant "
                            f"{participant.registration_number}."
                        ),

                        "participant_id":
                            participant.id,

                        "payment_id":
                            existing_payment.id,

                        "checkout_url":
                            existing_payment.checkout_url
                    }
                )

        # ==================================================
        # ADD TO TOTAL
        # ==================================================

        total_amount += participant_amount

        # ==================================================
        # FULL NAME
        # ==================================================

        fullname = (
            f"{participant.fname or ''} "
            f"{participant.mname or ''} "
            f"{participant.lname or ''}"
        ).strip()

        # ==================================================
        # PARTICIPANT DETAILS
        # ==================================================

        all_participant_items.append({

            "participant_id":
                participant.id,

            "registration_number":
                participant.registration_number,

            "fullname":
                fullname,

            "items":
                participant_items,

            "tshirt_selected":
                int(
                    participant_tshirt_requested
                ),

            "tshirt_size":
                participant_tshirt_size,

            "lanyard_selected":
                int(
                    participant_lanyard_requested
                ),

            "amount":
                participant_amount,

            "amount_display":
                f"₱{participant_amount / 100:,.2f}"
        })

        # ==================================================
        # PAYMENT SUMMARY
        # ==================================================

        participant_payment_summary.append({

            "participant_id":
                participant.id,

            "registration_number":
                participant.registration_number,

            "tshirt_selected":
                int(
                    participant_tshirt_requested
                ),

            "lanyard_selected":
                int(
                    participant_lanyard_requested
                ),

            "tshirt_size":
                participant_tshirt_size,

            "amount":
                participant_amount,

            "amount_display":
                f"₱{participant_amount / 100:,.2f}"
        })

        # ==================================================
        # CREATE LOCAL PAYMENT ROW
        #
        # IMPORTANT:
        #
        # Each participant receives their own
        # tshirt_size.
        # ==================================================

        payment = Payment(

            participant_id =
                participant.id,

            amount =
                participant_amount,

            currency =
                "PHP",

            status =
                "Pending",

            payment_type =
                "Participant",

            tshirt_selected =
                int(
                    participant_tshirt_requested
                ),

            lanyard_selected =
                int(
                    participant_lanyard_requested
                ),

            tshirt_size =
                participant_tshirt_size
        )

        db.add(payment)

        payment_rows.append(
            payment
        )

    # ==================================================
    # VALIDATE TOTAL
    # ==================================================

    if total_amount <= 0:

        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=(
                "There is no remaining "
                "amount to pay."
            )
        )

    # ==================================================
    # FLUSH
    # ==================================================

    try:

        db.flush()

    except Exception as e:

        db.rollback()

        print(
            "PAYMENT ROW FLUSH FAILED:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to create local "
                "payment records."
            )
        )

    # ==================================================
    # INTERNAL REFERENCE
    # ==================================================

    if is_bulk_payment:

        local_bulk_reference = (
            "CYF-BULK-"
            f"{uuid.uuid4().hex[:12].upper()}"
        )

    else:

        local_bulk_reference = (
            "CYF-SINGLE-"
            f"{uuid.uuid4().hex[:12].upper()}"
        )

    # ==================================================
    # EVENT NAME
    # ==================================================

    event_names = list(
        dict.fromkeys(
            participant.event_name
            for participant in participants
            if participant.event_name
        )
    )

    event_name = (
        event_names[0]
        if len(event_names) == 1
        else "Multiple Events"
    )

    # ==================================================
    # DESCRIPTION
    # ==================================================

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
    # ==================================================

    participant_remarks = []

    for item in all_participant_items:

        participant_remarks.append(
            (
                f"{item['registration_number']} | "
                f"{item['fullname']} | "
                f"{', '.join(item['items'])} | "
                f"₱{item['amount'] / 100:,.2f}"
            )
        )

    remarks = (
        "CYF Registration Payment | "
        f"Participants: {len(participants)} | "
        f"Bulk Reference: "
        f"{local_bulk_reference} | "
        f"{' || '.join(participant_remarks)}"
    )

    # ==================================================
    # PAYMONGO METADATA
    # ==================================================

    participant_ids_metadata = ",".join(
        str(pid)
        for pid in participant_ids
    )

    payment_ids_metadata = ",".join(
        str(payment.id)
        for payment in payment_rows
    )

    # --------------------------------------------------
    # PARTICIPANT T-SHIRT METADATA
    #
    # Example:
    #
    # 51:S,52:2XL
    # --------------------------------------------------

    participant_tshirt_metadata = ",".join(

        f"{pid}:{size}"

        for pid, size
        in participant_tshirt_map.items()
    )

    # ==================================================
    # PAYMONGO URL
    # ==================================================

    url = (
        f"{PAYMONGO_API_URL}"
        "/v1/payment_links"
    )

    # ==================================================
    # PAYMONGO PAYLOAD
    # ==================================================

    payload = {

        "amount":
            total_amount,

        "currency":
            "PHP",

        "description":
            description,

        "remarks":
            remarks,

        "metadata": {

            "payment_type":
                (
                    "bulk"
                    if is_bulk_payment
                    else "single"
                ),

            "bulk_reference":
                local_bulk_reference,

            "participant_count":
                str(len(participants)),

            "participant_ids":
                participant_ids_metadata,

            "payment_ids":
                payment_ids_metadata,

            "event_name":
                event_name,

            "tshirt":
                str(
                    int(
                        any(
                            item["tshirt_selected"]
                            for item
                            in all_participant_items
                        )
                    )
                ),

            "lanyard":
                str(
                    int(
                        any(
                            item["lanyard_selected"]
                            for item
                            in all_participant_items
                        )
                    )
                ),

            # Global size only if there is one.
            "tshirt_size":
                (
                    tshirt_size
                    or ""
                ),

            # IMPORTANT:
            # Individual participant sizes.
            "participant_tshirt_selections":
                participant_tshirt_metadata
        }
    }

    # ==================================================
    # IDEMPOTENCY KEY
    # ==================================================

    idempotency_key = (
        "cyf-payment-"
        f"{local_bulk_reference}-"
        f"{uuid.uuid4()}"
    )

    # ==================================================
    # CREATE PAYMONGO PAYMENT LINK
    # ==================================================

    try:

        response = requests.post(

            url,

            auth=(
                PAYMONGO_SECRET_KEY,
                ""
            ),

            headers={

                "Content-Type":
                    "application/json",

                "Accept":
                    "application/json",

                "Idempotency-Key":
                    idempotency_key
            },

            json=payload,

            timeout=30
        )

    except requests.RequestException as e:

        for payment in payment_rows:

            payment.status = "Failed"

        db.commit()

        print(
            "PAYMONGO CONNECTION ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "PayMongo connection failed: "
                f"{str(e)}"
            )
        )

    # ==================================================
    # PAYMONGO ERROR
    # ==================================================

    if not response.ok:

        for payment in payment_rows:

            payment.status = "Failed"

        db.commit()

        try:

            error_data = (
                response.json()
            )

        except Exception:

            error_data = {
                "error":
                    response.text
            }

        raise HTTPException(
            status_code=502,
            detail=error_data
        )

    # ==================================================
    # PARSE PAYMONGO RESPONSE
    # ==================================================

    try:

        paymongo_data = (
            response.json()
        )

    except Exception:

        for payment in payment_rows:

            payment.status = "Failed"

        db.commit()

        raise HTTPException(
            status_code=502,
            detail=(
                "PayMongo returned an "
                "invalid JSON response."
            )
        )

    # ==================================================
    # LINK DATA
    # ==================================================

    link_data = paymongo_data.get(
        "data",
        {}
    )

    if not link_data:

        for payment in payment_rows:

            payment.status = "Failed"

        db.commit()

        raise HTTPException(
            status_code=502,
            detail={
                "message":
                    "PayMongo returned an "
                    "empty data object.",

                "paymongo_response":
                    paymongo_data
            }
        )

    # ==================================================
    # LINK ID
    # ==================================================

    paymongo_link_id = (
        link_data.get("id")
    )

    # ==================================================
    # LINK ATTRIBUTES
    # ==================================================

    link_attributes = (
        link_data.get(
            "attributes",
            {}
        )
    )

    if not isinstance(
        link_attributes,
        dict
    ):

        link_attributes = {}

    # ==================================================
    # CHECKOUT URL
    # ==================================================

    checkout_url = (

        link_attributes.get(
            "checkout_url"
        )

        or

        link_attributes.get(
            "url"
        )

        or

        link_data.get(
            "checkout_url"
        )

        or

        link_data.get(
            "url"
        )
    )

    # ==================================================
    # PAYMONGO REFERENCE
    # ==================================================

    paymongo_reference = (

        link_attributes.get(
            "reference_number"
        )

        or

        link_data.get(
            "reference_number"
        )
    )

    # ==================================================
    # VALIDATE LINK ID
    # ==================================================

    if not paymongo_link_id:

        for payment in payment_rows:

            payment.status = "Failed"

        db.commit()

        raise HTTPException(
            status_code=502,
            detail={
                "message":
                    "PayMongo did not return "
                    "a payment link ID.",

                "paymongo_response":
                    paymongo_data
            }
        )

    # ==================================================
    # VALIDATE CHECKOUT URL
    # ==================================================

    if not checkout_url:

        for payment in payment_rows:

            payment.status = "Failed"

        db.commit()

        raise HTTPException(
            status_code=502,
            detail={
                "message":
                    "PayMongo did not return "
                    "a checkout URL.",

                "paymongo_response":
                    paymongo_data
            }
        )

    # ==================================================
    # SAVE PAYMONGO DATA
    # TO EVERY LOCAL PAYMENT ROW
    #
    # BULK:
    #
    # Payment 101 -> Participant 51
    # Payment 102 -> Participant 52
    #
    # Both share the SAME PayMongo checkout.
    # ==================================================

    for payment in payment_rows:

        if hasattr(
            payment,
            "paymongo_link_id"
        ):

            payment.paymongo_link_id = (
                paymongo_link_id
            )

        if hasattr(
            payment,
            "paymongo_reference"
        ):

            payment.paymongo_reference = (
                paymongo_reference
            )

        payment.checkout_url = (
            checkout_url
        )

        payment.status = "Pending"

    # ==================================================
    # COMMIT
    # ==================================================

    try:

        db.commit()

    except Exception as e:

        db.rollback()

        print(
            "PAYMENT COMMIT FAILED:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Payment was created but "
                "could not be saved locally."
            )
        )

    # ==================================================
    # REFRESH
    # ==================================================

    for payment in payment_rows:

        try:

            db.refresh(
                payment
            )

        except Exception as e:

            print(
                "Payment refresh failed:",
                repr(e)
            )

    # ==================================================
    # RETURN
    # ==================================================

    return {

        "message":
            (
                "Bulk payment link created successfully."
                if is_bulk_payment
                else
                "Payment link created successfully."
            ),

        "payment_type":
            (
                "bulk"
                if is_bulk_payment
                else "single"
            ),

        "participant_count":
            len(participants),

        "participant_ids":
            participant_ids,

        "participants":
            all_participant_items,

        "payment_ids":
            [
                payment.id
                for payment
                in payment_rows
            ],

        "participant_payment_summary":
            participant_payment_summary,

        "items":
            list(
                dict.fromkeys(
                    item
                    for participant_item
                    in all_participant_items
                    for item
                    in participant_item["items"]
                )
            ),

        "tshirt_selected":
            any(
                item["tshirt_selected"]
                for item
                in all_participant_items
            ),

        "lanyard_selected":
            any(
                item["lanyard_selected"]
                for item
                in all_participant_items
            ),

        "tshirt_size":
            tshirt_size,

        "participant_tshirt_selections":
            [
                {
                    "participant_id":
                        item["participant_id"],

                    "tshirt_selected":
                        bool(
                            item["tshirt_selected"]
                        ),

                    "tshirt_size":
                        item["tshirt_size"]
                }

                for item
                in all_participant_items
                if item["tshirt_selected"]
            ],

        "amount":
            total_amount,

        "amount_display":
            f"₱{total_amount / 100:,.2f}",

        "paymongo_link_id":
            paymongo_link_id,

        "checkout_url":
            checkout_url,

        "paymongo_reference":
            paymongo_reference,

        "bulk_reference":
            local_bulk_reference
    }


# ============================================================
# VIEW ALL STORE PAYMENTS
# ============================================================
#
# Unique name:
# Store Payments
#
# Returns payments specifically connected to StoreItem.
# ============================================================

@router.get(
    "/payments/store",
    response_model=List[PaymentResponse]
)
def view_all_store_payments(
    db: Session = Depends(get_db)
):

    payments = (
        db.query(Payment)
        .filter(
            Payment.store_item_id.isnot(None)
        )
        .order_by(
            Payment.created_at.desc()
        )
        .all()
    )

    return payments


# ============================================================
# VIEW SINGLE STORE PAYMENT
# ============================================================

@router.get(
    "/payments/store/{payment_id}",
    response_model=PaymentResponse
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
# VIEW ALL T-SHIRT PAYMENTS
# ============================================================

@router.get(
    "/payments/tshirt",
    response_model=List[PaymentResponse]
)
def view_all_tshirt_payments(
    db: Session = Depends(get_db)
):

    payments = (
        db.query(Payment)
        .filter(
            Payment.tshirt_selected > 0
        )
        .order_by(
            Payment.created_at.desc()
        )
        .all()
    )

    result = []

    for payment in payments:

        participant = None

        if payment.participant_id:

            participant = (
                db.query(Participant)
                .filter(
                    Participant.id ==
                    payment.participant_id
                )
                .first()
            )

        data = {
            "id": payment.id,
            "participant_id": payment.participant_id,
            "payment_type": payment.payment_type,

            "store_item_id": payment.store_item_id,
            "store_quantity": payment.store_quantity,
            "store_size": payment.store_size,

            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status,

            "tshirt_selected":
                payment.tshirt_selected,

            "lanyard_selected":
                payment.lanyard_selected,

            "tshirt_size":
                payment.tshirt_size,

            "sponsorship_tier":
                payment.sponsorship_tier,

            "sponsor_id":
                payment.sponsor_id,

            "paymongo_link_id":
                payment.paymongo_link_id,

            "paymongo_payment_id":
                payment.paymongo_payment_id,

            "paymongo_reference":
                payment.paymongo_reference,

            "checkout_url":
                payment.checkout_url,

            "description":
                payment.description,

            "customer_name":
                payment.customer_name,

            "customer_contact":
                payment.customer_contact,

            "customer_email":
                payment.customer_email,

            "created_at":
                payment.created_at,

            "paid_at":
                payment.paid_at,

            # ==========================================
            # FULL PARTICIPANT NAME
            # ==========================================

            "participant_name":
                (
                    f"{participant.fname} "
                    f"{participant.mname + ' ' if participant.mname else ''}"
                    f"{participant.lname}"
                )
                if participant
                else payment.customer_name
        }

        result.append(data)

    return result


# ============================================================
# VIEW SINGLE T-SHIRT PAYMENT
# ============================================================

@router.get(
    "/payments/tshirt/{payment_id}",
    response_model=PaymentResponse
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
# VIEW ALL LANYARD PAYMENTS
# ============================================================

@router.get(
    "/payments/lanyard",
    response_model=List[PaymentResponse]
)
def view_all_lanyard_payments(
    db: Session = Depends(get_db)
):

    payments = (
        db.query(Payment)
        .filter(
            Payment.lanyard_selected > 0
        )
        .order_by(
            Payment.created_at.desc()
        )
        .all()
    )

    result = []

    for payment in payments:

        participant = None

        if payment.participant_id:

            participant = (
                db.query(Participant)
                .filter(
                    Participant.id ==
                    payment.participant_id
                )
                .first()
            )

        data = {
            "id": payment.id,
            "participant_id": payment.participant_id,
            "payment_type": payment.payment_type,

            "store_item_id": payment.store_item_id,
            "store_quantity": payment.store_quantity,
            "store_size": payment.store_size,

            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status,

            "tshirt_selected":
                payment.tshirt_selected,

            "lanyard_selected":
                payment.lanyard_selected,

            "tshirt_size":
                payment.tshirt_size,

            "sponsorship_tier":
                payment.sponsorship_tier,

            "sponsor_id":
                payment.sponsor_id,

            "paymongo_link_id":
                payment.paymongo_link_id,

            "paymongo_payment_id":
                payment.paymongo_payment_id,

            "paymongo_reference":
                payment.paymongo_reference,

            "checkout_url":
                payment.checkout_url,

            "description":
                payment.description,

            "customer_name":
                payment.customer_name,

            "customer_contact":
                payment.customer_contact,

            "customer_email":
                payment.customer_email,

            "created_at":
                payment.created_at,

            "paid_at":
                payment.paid_at,

            "participant_name":
                (
                    f"{participant.fname} "
                    f"{participant.mname + ' ' if participant.mname else ''}"
                    f"{participant.lname}"
                )
                if participant
                else payment.customer_name
        }

        result.append(data)

    return result


# ============================================================
# VIEW SINGLE LANYARD PAYMENT
# ============================================================

@router.get(
    "/payments/lanyard/{payment_id}",
    response_model=PaymentResponse
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
