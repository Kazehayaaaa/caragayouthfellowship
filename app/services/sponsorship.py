"""Sponsorship tiers, finding-sponsor queue and cash donation totals."""

from decimal import Decimal
from sqlalchemy.orm import Session
import datetime
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import text

from app.database import (
    SessionLocal,
)
from app.models import (
    CashDonationTotal,
    CashSponsorship,
    Participant,
    RegistrationItem,
    SponsorshipPackage,
)

def is_manual_finding_sponsor_enabled(db: Session) -> bool:
    row = db.execute(text("""
        SELECT enabled
        FROM manual_sponsor_settings
        WHERE id = 1
    """)).first()
    return bool(row and int(row[0]) == 1)
















# ============================================================
# INITIALIZE SPONSORSHIP TIERS
# ============================================================

def initialize_sponsorship_tiers():

    db = SessionLocal()

    try:

        existing = db.query(
            SponsorshipPackage
        ).count()

        if existing > 0:
            return

        tiers = [

            SponsorshipPackage(
                tier="1st (Bronze) Tier",
                minimum_amount=0,
                maximum_amount=999,
                description="Donation below ₱1,000"
            ),

            SponsorshipPackage(
                tier="2nd (Silver) Tier",
                minimum_amount=1000,
                maximum_amount=1999,
                description="Donation from ₱1,000 to below ₱2,000"
            ),

            SponsorshipPackage(
                tier="3rd (Gold) Tier",
                minimum_amount=2000,
                maximum_amount=2999,
                description="Donation from ₱2,000 to below ₱3,000"
            ),

            SponsorshipPackage(
                tier="4th (Diamond) Tier",
                minimum_amount=3000,
                maximum_amount=None,
                description="Donation of ₱3,000 and above"
            )

        ]

        db.add_all(tiers)

        db.commit()

    finally:

        db.close()






# ============================================================
# DETERMINE TIER
# ============================================================

def determine_sponsorship_tier(
    amount: Decimal
):

    if amount < Decimal("1000"):
        return "1st (Bronze) Tier"

    elif amount < Decimal("2000"):
        return "2nd (Silver) Tier"

    elif amount < Decimal("3000"):
        return "3rd (Gold) Tier"

    else:
        return "4th (Diamond) Tier"







# ============================================================
# ADD SUCCESSFUL DONATION TO CASH DONATION TOTAL
# ============================================================

def add_cash_donation_to_total(
    db: Session,
    sponsorship: CashSponsorship
):

    # --------------------------------------------------------
    # ALREADY ADDED
    # --------------------------------------------------------

    if sponsorship.cash_total_added:

        return False

    # --------------------------------------------------------
    # CHECK PAYMENT STATUS
    # --------------------------------------------------------

    status = str(
        sponsorship.payment_status or ""
    ).strip().lower()

    if status not in [
        "paid",
        "success",
        "succeeded",
        "completed"
    ]:

        return False

    # --------------------------------------------------------
    # GET TOTAL RECORD
    # --------------------------------------------------------

    total_record = (
        db.query(
            CashDonationTotal
        )
        .first()
    )

    # --------------------------------------------------------
    # CREATE IF NEEDED
    # --------------------------------------------------------

    if not total_record:

        total_record = (
            CashDonationTotal(
                amount=0
            )
        )

        db.add(
            total_record
        )

        db.flush()

    # --------------------------------------------------------
    # ADD DONATION
    # --------------------------------------------------------

    total_record.amount = (
        int(
            total_record.amount or 0
        )
        +
        int(
            sponsorship.donation_amount or 0
        )
    )

    # --------------------------------------------------------
    # MARK AS ALREADY ADDED
    # --------------------------------------------------------

    sponsorship.cash_total_added = True

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    db.commit()

    db.refresh(
        total_record
    )

    return True

















    
    

    
# ============================================================
# FINDING SPONSOR QUEUE PROCESSING LOGIC
# ============================================================
#
# This is the REAL sponsorship-processing logic.
#
# It can be called from:
#
# 1. POST /process_finding_sponsor_queue
# 2. PayMongo webhook
#
# DO NOT call the FastAPI endpoint internally.
#
# IMPORTANT:
#
# RegistrationItem.price
#     = STORED IN CENTAVOS
#
# CashDonationTotal.total_amount
#     = STORED IN PESOS
#
# Example:
#
# T-shirt:
#     35000 = ₱350.00
#
# Lanyard:
#     9000 = ₱90.00
#
# Required:
#     ₱350 + ₱90 = ₱440
#
# ============================================================


async def process_finding_sponsor_queue_logic(
    db: Session
):

    print("\n")
    print("=" * 70)
    print("FINDING SPONSOR QUEUE PROCESSING")
    print("=" * 70)

    # ========================================================
    # GET T-SHIRT PRICE
    # ========================================================

    tshirt_item = (
        db.query(
            RegistrationItem
        )
        .filter(
            RegistrationItem.item_name.ilike("T-Shirt"),
            RegistrationItem.is_active == True
        )
        .first()
    )

    if not tshirt_item:

        raise Exception(
            "T-shirt registration item was not found."
        )

    # ========================================================
    # GET LANYARD PRICE
    # ========================================================

    lanyard_item = (
        db.query(
            RegistrationItem
        )
        .filter(
            RegistrationItem.item_name.ilike("Lanyard"),
            RegistrationItem.is_active == True
        )
        .first()
    )

    if not lanyard_item:

        raise Exception(
            "Lanyard registration item was not found."
        )

    # ========================================================
    # GET PRICES
    #
    # RegistrationItem.price = CENTAVOS
    #
    # Example:
    #
    # 35000 = ₱350.00
    # 9000  = ₱90.00
    #
    # ========================================================

    try:

        tshirt_price_centavos = int(
            tshirt_item.price or 0
        )

    except (
        ValueError,
        TypeError
    ):

        tshirt_price_centavos = 0

    try:

        lanyard_price_centavos = int(
            lanyard_item.price or 0
        )

    except (
        ValueError,
        TypeError
    ):

        lanyard_price_centavos = 0

    # ========================================================
    # CONVERT CENTAVOS TO PESOS
    # ========================================================

    tshirt_price = (
        tshirt_price_centavos / 100
    )

    lanyard_price = (
        lanyard_price_centavos / 100
    )

    # ========================================================
    # REQUIRED SPONSORSHIP AMOUNT
    #
    # Stored/compared in PESOS because
    # CashDonationTotal.total_amount is in PESOS.
    # ========================================================

    required_amount = (
        tshirt_price +
        lanyard_price
    )

    if required_amount <= 0:

        raise Exception(
            "Merchandise prices must be greater than zero."
        )

    print(
        "T-shirt Price:",
        f"₱{tshirt_price:,.2f}"
    )

    print(
        "Lanyard Price:",
        f"₱{lanyard_price:,.2f}"
    )

    print(
        "Required Per Participant:",
        f"₱{required_amount:,.2f}"
    )

    # ========================================================
    # GET CASH DONATION TOTAL
    # ========================================================

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

        print(
            "No CashDonationTotal record exists."
        )

        return {

            "success":
                True,

            "status":
                "Queued",

            "message":
                "No cash donation total is available.",

            "tshirt_price":
                tshirt_price,

            "tshirt_price_display":
                f"₱{tshirt_price:,.2f}",

            "lanyard_price":
                lanyard_price,

            "lanyard_price_display":
                f"₱{lanyard_price:,.2f}",

            "required_amount_per_participant":
                required_amount,

            "required_amount_display":
                f"₱{required_amount:,.2f}",

            "cash_donation_total":
                0,

            "cash_donation_total_display":
                "₱0.00",

            "initial_queue_count":
                0,

            "sponsored_count":
                0,

            "remaining_queue_count":
                0,

            "participant_emails_sent":
                0,

            "participant_email_errors":
                [],

            "participants":
                []

        }

    # ========================================================
    # CURRENT BALANCE
    #
    # CashDonationTotal.total_amount = PESOS
    # ========================================================

    try:

        current_balance = float(
            donation_total.total_amount or 0
        )

    except (
        ValueError,
        TypeError
    ):

        current_balance = 0.0

    initial_balance = current_balance

    print(
        "Current Sponsorship Fund:",
        f"₱{current_balance:,.2f}"
    )

    # ========================================================
    # FIND FINDING SPONSOR PARTICIPANTS
    #
    # FIFO:
    #
    # Oldest Finding Sponsor participant
    # gets sponsored first.
    #
    # IMPORTANT:
    #
    # Use:
    #
    #     func.lower()
    #     func.coalesce()
    #     or_()
    #
    # NOT:
    #
    #     db.func
    #     db.or_
    #
    # ========================================================

    finding_sponsors = (
        db.query(
            Participant
        )
        .filter(

            Participant.is_archived == 0,

            Participant.participant_type.ilike(
                "Finding Sponsor"
            ),

            or_(

                func.lower(
                    func.coalesce(
                        Participant.tshirt_status,
                        "Unpaid"
                    )
                ) != "paid",

                func.lower(
                    func.coalesce(
                        Participant.lanyard_status,
                        "Unpaid"
                    )
                ) != "paid"

            )

        )
        .order_by(

            Participant.created_at.asc(),

            Participant.id.asc()

        )
        .all()
    )

    # ========================================================
    # QUEUE COUNT
    # ========================================================

    initial_queue_count = len(
        finding_sponsors
    )

    print(
        "Finding Sponsor Queue:",
        initial_queue_count
    )

    # ========================================================
    # NOTHING TO SPONSOR
    # ========================================================

    if initial_queue_count == 0:

        print(
            "No Finding Sponsor participants waiting."
        )

        return {

            "success":
                True,

            "status":
                "Completed",

            "message":
                "No Finding Sponsor participants are waiting for sponsorship.",

            "tshirt_price":
                tshirt_price,

            "tshirt_price_display":
                f"₱{tshirt_price:,.2f}",

            "lanyard_price":
                lanyard_price,

            "lanyard_price_display":
                f"₱{lanyard_price:,.2f}",

            "required_amount_per_participant":
                required_amount,

            "required_amount_display":
                f"₱{required_amount:,.2f}",

            "cash_donation_total":
                current_balance,

            "cash_donation_total_display":
                f"₱{current_balance:,.2f}",

            "initial_queue_count":
                0,

            "sponsored_count":
                0,

            "remaining_queue_count":
                0,

            "participant_emails_sent":
                0,

            "participant_email_errors":
                [],

            "participants":
                []

        }

    # ========================================================
    # PROCESS FIFO
    # ========================================================

    sponsored_participants = []

    try:

        for participant in finding_sponsors:

            # =================================================
            # STOP IF NOT ENOUGH MONEY
            # =================================================

            if current_balance < required_amount:

                print(
                    "Insufficient sponsorship fund."
                )

                print(
                    "Current:",
                    f"₱{current_balance:,.2f}"
                )

                print(
                    "Needed:",
                    f"₱{required_amount:,.2f}"
                )

                print(
                    "Still Needed:",
                    f"₱{required_amount - current_balance:,.2f}"
                )

                break

            # =================================================
            # FULL NAME
            # =================================================

            fullname = " ".join(

                part

                for part in [

                    getattr(
                        participant,
                        "fname",
                        None
                    ),

                    getattr(
                        participant,
                        "mname",
                        None
                    ),

                    getattr(
                        participant,
                        "lname",
                        None
                    )

                ]

                if part

            ).strip()

            # =================================================
            # DEDUCT SPONSORSHIP COST
            # =================================================

            current_balance -= (
                required_amount
            )

            # =================================================
            # MARK T-SHIRT PAID
            # =================================================

            if hasattr(
                participant,
                "tshirt_status"
            ):

                participant.tshirt_status = (
                    "Paid"
                )

            # =================================================
            # MARK LANYARD PAID
            # =================================================

            if hasattr(
                participant,
                "lanyard_status"
            ):

                participant.lanyard_status = (
                    "Paid"
                )

            # =================================================
            # COMPLETE REGISTRATION
            # =================================================

            if hasattr(
                participant,
                "registration_status"
            ):

                participant.registration_status = (
                    "Confirmed"
                )

            # =================================================
            # SPONSOR REVIEW APPROVED
            #
            # Supports either:
            #
            # sponsor_review_status
            #
            # OR:
            #
            # sponsorship_review_status
            # =================================================

            sponsor_review_status = "Approved"

            if hasattr(
                participant,
                "sponsor_review_status"
            ):

                participant.sponsor_review_status = (
                    "Approved"
                )

            elif hasattr(
                participant,
                "sponsorship_review_status"
            ):

                participant.sponsorship_review_status = (
                    "Approved"
                )

            # =================================================
            # UPDATE TIMESTAMP
            # =================================================

            if hasattr(
                participant,
                "updated_at"
            ):

                participant.updated_at = (
                    datetime.datetime.now()
                )

            # =================================================
            # RECORD RESULT
            # =================================================

            sponsored_participants.append({

                "participant_id":
                    participant.id,

                "registration_number":
                    getattr(
                        participant,
                        "registration_number",
                        None
                    ),

                "fullname":
                    fullname,

                "participant_type":
                    getattr(
                        participant,
                        "participant_type",
                        None
                    ),

                "tshirt_status":
                    getattr(
                        participant,
                        "tshirt_status",
                        "Paid"
                    ),

                "lanyard_status":
                    getattr(
                        participant,
                        "lanyard_status",
                        "Paid"
                    ),

                "registration_status":
                    getattr(
                        participant,
                        "registration_status",
                        None
                    ),

                "sponsor_review_status":
                    getattr(
                        participant,
                        "sponsor_review_status",
                        getattr(
                            participant,
                            "sponsorship_review_status",
                            sponsor_review_status
                        )
                    ),

                "sponsored_amount":
                    required_amount,

                "sponsored_amount_display":
                    f"₱{required_amount:,.2f}"

            })

            # =================================================
            # LOG
            # =================================================

            print("=" * 50)

            print(
                "PARTICIPANT SPONSORED"
            )

            print(
                "Participant ID:",
                participant.id
            )

            print(
                "Registration:",
                getattr(
                    participant,
                    "registration_number",
                    None
                )
            )

            print(
                "Name:",
                fullname
            )

            print(
                "Sponsored:",
                f"₱{required_amount:,.2f}"
            )

            print(
                "T-shirt:",
                getattr(
                    participant,
                    "tshirt_status",
                    None
                )
            )

            print(
                "Lanyard:",
                getattr(
                    participant,
                    "lanyard_status",
                    None
                )
            )

            print(
                "Registration:",
                getattr(
                    participant,
                    "registration_status",
                    None
                )
            )

            print(
                "Sponsor Review:",
                getattr(
                    participant,
                    "sponsor_review_status",
                    getattr(
                        participant,
                        "sponsorship_review_status",
                        "Approved"
                    )
                )
            )

            print(
                "Remaining Fund:",
                f"₱{current_balance:,.2f}"
            )

            print("=" * 50)

        # ====================================================
        # SAVE REMAINING BALANCE
        # ====================================================

        donation_total.total_amount = (
            current_balance
        )

        if hasattr(
            donation_total,
            "updated_at"
        ):

            donation_total.updated_at = (
                datetime.datetime.now()
            )

        # ====================================================
        # COMMIT DATABASE CHANGES
        # ====================================================

        db.commit()

        db.refresh(
            donation_total
        )

    except Exception as e:

        db.rollback()

        print("=" * 70)

        print(
            "FINDING SPONSOR PROCESSING ERROR"
        )

        print(
            "Error:",
            repr(e)
        )

        print("=" * 70)

        raise

    # ========================================================
    # GET REMAINING QUEUE
    #
    # Re-query AFTER commit so participants that were
    # marked Paid are no longer counted.
    # ========================================================

    remaining_queue = (
        db.query(
            Participant
        )
        .filter(

            Participant.is_archived == 0,

            Participant.participant_type.ilike(
                "Finding Sponsor"
            ),

            or_(

                func.lower(
                    func.coalesce(
                        Participant.tshirt_status,
                        "Unpaid"
                    )
                ) != "paid",

                func.lower(
                    func.coalesce(
                        Participant.lanyard_status,
                        "Unpaid"
                    )
                ) != "paid"

            )

        )
        .order_by(

            Participant.created_at.asc(),

            Participant.id.asc()

        )
        .all()
    )

    remaining_queue_count = len(
        remaining_queue
    )

    # ========================================================
    # DETERMINE QUEUE STATUS
    # ========================================================

    if remaining_queue_count == 0:

        queue_status = "Completed"

    elif current_balance >= required_amount:

        queue_status = "Ready"

    else:

        queue_status = "Queued"

    # ========================================================
    # SEND PARTICIPANT SPONSORSHIP EMAILS
    #
    # Email function signature:
    #
    # send_sponsored_participant_confirmation_email(
    #     participant,
    #     sponsored_amount
    # )
    #
    # IMPORTANT:
    #
    # The function is async.
    # Therefore we MUST use await.
    # ========================================================

    participant_emails_sent = 0

    participant_email_errors = []

    email_function = globals().get(
        "send_sponsored_participant_confirmation_email"
    )

    if not email_function:

        print(
            "WARNING:"
        )

        print(
            "send_sponsored_participant_confirmation_email "
            "is not defined."
        )

    else:

        for sponsored in sponsored_participants:

            try:

                sponsored_participant = (
                    db.query(
                        Participant
                    )
                    .filter(
                        Participant.id ==
                        sponsored[
                            "participant_id"
                        ]
                    )
                    .first()
                )

                if not sponsored_participant:

                    print(
                        "Sponsored participant not found:",
                        sponsored[
                            "participant_id"
                        ]
                    )

                    continue

                participant_email = getattr(
                    sponsored_participant,
                    "email",
                    None
                )

                if participant_email:

                    participant_email = str(
                        participant_email
                    ).strip()

                if not participant_email:

                    print(
                        "Sponsored participant has no email:",
                        sponsored[
                            "participant_id"
                        ]
                    )

                    continue

                # ==========================================
                # SEND EMAIL
                #
                # PASS BOTH:
                #
                # participant
                # sponsored_amount
                # ==========================================

                print(
                    "Sending sponsored participant email to:",
                    participant_email
                )

                await email_function(

                    sponsored_participant,

                    sponsored[
                        "sponsored_amount"
                    ]

                )

                participant_emails_sent += 1

                print(
                    "Sponsored participant email sent:",
                    participant_email
                )

            except Exception as e:

                print(
                    "Sponsored participant email failed:"
                )

                print(
                    "Participant ID:",
                    sponsored[
                        "participant_id"
                    ]
                )

                print(
                    "Error:",
                    repr(e)
                )

                participant_email_errors.append({

                    "participant_id":
                        sponsored[
                            "participant_id"
                        ],

                    "email":
                        getattr(
                            sponsored_participant,
                            "email",
                            None
                        ),

                    "error":
                        str(e)

                })

    # ========================================================
    # TOTAL SPONSORED AMOUNT
    # ========================================================

    total_sponsored_amount = (
        len(
            sponsored_participants
        ) *
        required_amount
    )

    # ========================================================
    # FINAL LOG
    # ========================================================

    print("=" * 70)

    print(
        "FINDING SPONSOR PROCESSING COMPLETE"
    )

    print("=" * 70)

    print(
        "Initial Fund:",
        f"₱{initial_balance:,.2f}"
    )

    print(
        "Total Sponsored:",
        f"₱{total_sponsored_amount:,.2f}"
    )

    print(
        "Remaining Fund:",
        f"₱{current_balance:,.2f}"
    )

    print(
        "Sponsored Participants:",
        len(
            sponsored_participants
        )
    )

    print(
        "Remaining Queue:",
        remaining_queue_count
    )

    print(
        "Emails Sent:",
        participant_emails_sent
    )

    print(
        "Email Errors:",
        len(
            participant_email_errors
        )
    )

    print("=" * 70)

    # ========================================================
    # RETURN RESULT
    # ========================================================

    return {

        "success":
            True,

        "status":
            queue_status,

        "message":
            "Finding Sponsor queue processed successfully.",

        # ====================================================
        # PRICES
        # ====================================================

        "tshirt_price":
            tshirt_price,

        "tshirt_price_display":
            f"₱{tshirt_price:,.2f}",

        "tshirt_price_centavos":
            tshirt_price_centavos,

        "lanyard_price":
            lanyard_price,

        "lanyard_price_display":
            f"₱{lanyard_price:,.2f}",

        "lanyard_price_centavos":
            lanyard_price_centavos,

        "required_amount_per_participant":
            required_amount,

        "required_amount_display":
            f"₱{required_amount:,.2f}",

        # ====================================================
        # FUND
        # ====================================================

        "initial_cash_donation_total":
            initial_balance,

        "initial_cash_donation_total_display":
            f"₱{initial_balance:,.2f}",

        "total_sponsored_amount":
            total_sponsored_amount,

        "total_sponsored_amount_display":
            f"₱{total_sponsored_amount:,.2f}",

        "cash_donation_total":
            current_balance,

        "cash_donation_total_display":
            f"₱{current_balance:,.2f}",

        # ====================================================
        # QUEUE
        # ====================================================

        "initial_queue_count":
            initial_queue_count,

        "sponsored_count":
            len(
                sponsored_participants
            ),

        "remaining_queue_count":
            remaining_queue_count,

        # ====================================================
        # EMAIL
        # ====================================================

        "participant_emails_sent":
            participant_emails_sent,

        "participant_email_errors":
            participant_email_errors,

        # ====================================================
        # PARTICIPANTS
        # ====================================================

        "participants":
            sponsored_participants

    }
