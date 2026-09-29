"""Routes: manual sponsor."""

from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from sqlalchemy.orm import Session
import datetime
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import text
from fastapi import APIRouter

from app.database import (
    get_db,
)
from app.models import (
    CashDonationTotal,
    Participant,
    RegistrationItem,
    SponsorshipItem,
)
from app.schemas import (
    ManualFindingSponsorToggleSchema,
    ManualFindingSponsorTriggerSchema,
)
from app.security import (
    require_admin_session,
)
from app.services.sponsorship import (
    is_manual_finding_sponsor_enabled,
)

router = APIRouter()

    

















# ============================================================
# MANUAL FINDING SPONSOR ADMIN APIs
# ============================================================
#
# Manual sponsorship is deliberately separate from the automatic
# Finding Sponsor queue.  The admin can disable the manual feature,
# and every manual endpoint checks the same switch server-side.
#
# A manual sponsorship:
#   - searches a Finding Sponsor participant
#   - requires enough current cash donation fund
#   - marks T-shirt and Lanyard Paid
#   - deducts the current T-shirt + Lanyard cost
#   - creates an allocation record
#   - can later be cancelled/retrieved, restoring the fund and
#     the participant's previous merchandise status.
#
# ============================================================


@router.get("/admin/manual-sponsor/status")
def get_manual_finding_sponsor_status(
    request: Request,
    db: Session = Depends(get_db)
):
    require_admin_session(request)

    enabled = is_manual_finding_sponsor_enabled(db)

    return {
        "success": True,
        "enabled": enabled,
        "message": (
            "Manual Finding Sponsor is ON."
            if enabled
            else
            "Manual Finding Sponsor is OFF."
        )
    }


@router.put("/admin/manual-sponsor/toggle")
def toggle_manual_finding_sponsor(
    data: ManualFindingSponsorToggleSchema,
    request: Request,
    db: Session = Depends(get_db)
):
    session_user = require_admin_session(request)

    db.execute(text("""
        UPDATE manual_sponsor_settings
        SET enabled = :enabled,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """), {
        "enabled": 1 if data.enabled else 0
    })
    db.commit()

    return {
        "success": True,
        "enabled": bool(data.enabled),
        "message": (
            "Manual Finding Sponsor function turned ON."
            if data.enabled
            else
            "Manual Finding Sponsor function turned OFF."
        ),
        "admin_username": session_user.get("username")
    }


@router.get("/admin/manual-sponsor/search")
def search_manual_finding_sponsor_participants(
    q: str,
    request: Request,
    db: Session = Depends(get_db)
):
    require_admin_session(request)

    if not is_manual_finding_sponsor_enabled(db):
        raise HTTPException(
            status_code=403,
            detail=(
                "Manual Finding Sponsor function is OFF. "
                "Please turn it ON to use this function again."
            )
        )

    search = q.strip()

    if len(search) < 2:
        raise HTTPException(
            status_code=400,
            detail="Enter at least 2 characters to search for a participant."
        )

    pattern = f"%{search}%"

    participants = (
        db.query(Participant)
        .filter(
            Participant.is_archived == 0,
            Participant.participant_type.ilike("Finding Sponsor"),
            or_(
                Participant.fname.ilike(pattern),
                Participant.mname.ilike(pattern),
                Participant.lname.ilike(pattern),
                func.concat(
                    func.coalesce(Participant.fname, ""),
                    " ",
                    func.coalesce(Participant.lname, "")
                ).ilike(pattern)
            )
        )
        .order_by(
            Participant.fname.asc(),
            Participant.lname.asc()
        )
        .limit(20)
        .all()
    )

    results = []

    for participant in participants:
        active_allocation = db.execute(text("""
            SELECT id, amount, created_at
            FROM manual_sponsor_allocations
            WHERE participant_id = :participant_id
              AND status = 'Active'
            ORDER BY id DESC
            LIMIT 1
        """), {
            "participant_id": participant.id
        }).mappings().first()

        tshirt_status = participant.tshirt_status or "Unpaid"
        lanyard_status = participant.lanyard_status or "Unpaid"

        tshirt_paid = (
            str(tshirt_status).strip().lower() == "paid"
        )
        lanyard_paid = (
            str(lanyard_status).strip().lower() == "paid"
        )

        if active_allocation:
            availability_status = "Sponsored"
        elif tshirt_paid and lanyard_paid:
            availability_status = "Already Paid"
        elif tshirt_paid or lanyard_paid:
            availability_status = "Partially Paid"
        else:
            availability_status = "Available"

        results.append({
            "participant_id": participant.id,
            "registration_number": participant.registration_number,
            "fullname": " ".join(
                x for x in [
                    participant.fname,
                    participant.mname,
                    participant.lname
                ] if x
            ).strip(),
            "email": participant.email,
            "participant_type": participant.participant_type,
            "tshirt_status": tshirt_status,
            "lanyard_status": lanyard_status,
            "registration_status": participant.registration_status,
            "already_manual_sponsored": bool(active_allocation),
            "manual_sponsorship_id": (
                active_allocation["id"]
                if active_allocation
                else None
            ),
            "manual_sponsored_amount": (
                float(active_allocation["amount"] or 0)
                if active_allocation
                else 0
            ),
            "availability_status": availability_status,
            "can_manual_sponsor": (
                not active_allocation
                and not tshirt_paid
                and not lanyard_paid
            )
        })

    return {
        "success": True,
        "exists": len(results) > 0,
        "count": len(results),
        "participants": results
    }


@router.post("/admin/manual-sponsor/trigger")
async def manual_finding_sponsor_trigger(
    data: ManualFindingSponsorTriggerSchema,
    request: Request,
    db: Session = Depends(get_db)
):
    session_user = require_admin_session(request)

    if not is_manual_finding_sponsor_enabled(db):
        raise HTTPException(
            status_code=403,
            detail=(
                "Manual Finding Sponsor function is OFF. "
                "Please turn it ON to use this function again."
            )
        )

    participant = (
        db.query(Participant)
        .filter(
            Participant.id == data.participant_id,
            Participant.is_archived == 0
        )
        .first()
    )

    if not participant:
        raise HTTPException(
            status_code=404,
            detail="Participant not found."
        )

    if (
        str(participant.participant_type or "")
        .strip()
        .lower()
        != "finding sponsor"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Only Finding Sponsor participants can be manually sponsored."
            )
        )

    # ------------------------------------------------------------
    # DO NOT SPONSOR A PARTICIPANT WHO ALREADY HAS A PAID ITEM
    # ------------------------------------------------------------
    previous_tshirt_status = participant.tshirt_status or "Unpaid"
    previous_lanyard_status = participant.lanyard_status or "Unpaid"

    tshirt_paid = (
        str(previous_tshirt_status).strip().lower() == "paid"
    )
    lanyard_paid = (
        str(previous_lanyard_status).strip().lower() == "paid"
    )

    if tshirt_paid and lanyard_paid:
        raise HTTPException(
            status_code=409,
            detail=(
                "This participant already paid for the T-shirt and Lanyard. "
                "No sponsorship is required."
            )
        )

    if tshirt_paid or lanyard_paid:
        raise HTTPException(
            status_code=409,
            detail=(
                "This participant already has one paid merchandise item. "
                "Manual sponsorship requires both T-shirt and Lanyard to be unpaid."
            )
        )

    # ------------------------------------------------------------
    # PREVENT DUPLICATE ACTIVE MANUAL SPONSORSHIP
    # ------------------------------------------------------------
    active = db.execute(text("""
        SELECT id
        FROM manual_sponsor_allocations
        WHERE participant_id = :participant_id
          AND status = 'Active'
        ORDER BY id DESC
        LIMIT 1
    """), {
        "participant_id": participant.id
    }).first()

    if active:
        raise HTTPException(
            status_code=409,
            detail="This participant already has an active manual sponsorship."
        )

    # ------------------------------------------------------------
    # GET CURRENT REGISTRATION PRICES
    # RegistrationItem.price is stored in centavos.
    # ------------------------------------------------------------
    tshirt_item = (
        db.query(RegistrationItem)
        .filter(
            RegistrationItem.item_name.ilike("T-Shirt"),
            RegistrationItem.is_active == True
        )
        .first()
    )

    lanyard_item = (
        db.query(RegistrationItem)
        .filter(
            RegistrationItem.item_name.ilike("Lanyard"),
            RegistrationItem.is_active == True
        )
        .first()
    )

    if not tshirt_item or not lanyard_item:
        raise HTTPException(
            status_code=404,
            detail=(
                "T-shirt and Lanyard registration items must both be "
                "configured and active."
            )
        )

    tshirt_price_centavos = int(tshirt_item.price or 0)
    lanyard_price_centavos = int(lanyard_item.price or 0)

    tshirt_amount = tshirt_price_centavos / 100
    lanyard_amount = lanyard_price_centavos / 100
    sponsorship_amount = tshirt_amount + lanyard_amount

    if sponsorship_amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="T-shirt and Lanyard prices must be greater than zero."
        )

    # ------------------------------------------------------------
    # GET SPONSORSHIP INVENTORY
    # The manual sponsorship consumes exactly one of each item.
    # ------------------------------------------------------------
    tshirt_stock = (
        db.query(SponsorshipItem)
        .filter(
            SponsorshipItem.item_name.ilike("T-Shirt"),
            SponsorshipItem.is_active == True
        )
        .first()
    )

    lanyard_stock = (
        db.query(SponsorshipItem)
        .filter(
            SponsorshipItem.item_name.ilike("Lanyard"),
            SponsorshipItem.is_active == True
        )
        .first()
    )

    if not tshirt_stock or not lanyard_stock:
        raise HTTPException(
            status_code=404,
            detail=(
                "T-Shirt and Lanyard sponsorship inventory items must both "
                "be configured and active."
            )
        )

    tshirt_remaining = int(tshirt_stock.remaining_quantity or 0)
    lanyard_remaining = int(lanyard_stock.remaining_quantity or 0)

    if tshirt_remaining < 1 or lanyard_remaining < 1:
        missing = []

        if tshirt_remaining < 1:
            missing.append("T-Shirt")

        if lanyard_remaining < 1:
            missing.append("Lanyard")

        raise HTTPException(
            status_code=400,
            detail=(
                "Not enough sponsorship inventory. Out of stock: "
                + ", ".join(missing)
                + "."
            )
        )

    # ------------------------------------------------------------
    # GET CASH DONATION FUND
    # CashDonationTotal.total_amount is stored in pesos.
    # ------------------------------------------------------------
    donation_total = (
        db.query(CashDonationTotal)
        .order_by(CashDonationTotal.id.asc())
        .first()
    )

    if not donation_total:
        raise HTTPException(
            status_code=400,
            detail="No cash donation fund is available."
        )

    current_balance = float(donation_total.total_amount or 0)

    if current_balance < sponsorship_amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Not enough cash donation fund. Required: "
                f"₱{sponsorship_amount:,.2f}. "
                f"Available: ₱{current_balance:,.2f}."
            )
        )

    previous_registration_status = participant.registration_status

    sponsor_review_field = None
    previous_sponsor_review_status = None

    if hasattr(participant, "sponsor_review_status"):
        sponsor_review_field = "sponsor_review_status"
        previous_sponsor_review_status = getattr(
            participant,
            "sponsor_review_status",
            None
        )
    elif hasattr(participant, "sponsorship_review_status"):
        sponsor_review_field = "sponsorship_review_status"
        previous_sponsor_review_status = getattr(
            participant,
            "sponsorship_review_status",
            None
        )

    try:
        # --------------------------------------------------------
        # DEDUCT CASH FUND
        # --------------------------------------------------------
        donation_total.total_amount = round(
            current_balance - sponsorship_amount,
            2
        )

        # --------------------------------------------------------
        # DEDUCT INVENTORY
        # --------------------------------------------------------
        tshirt_stock.remaining_quantity = max(
            0,
            tshirt_remaining - 1
        )

        lanyard_stock.remaining_quantity = max(
            0,
            lanyard_remaining - 1
        )

        # --------------------------------------------------------
        # UPDATE PARTICIPANT
        # --------------------------------------------------------
        participant.tshirt_status = "Paid"
        participant.lanyard_status = "Paid"
        participant.registration_status = "Confirmed"

        if sponsor_review_field:
            setattr(
                participant,
                sponsor_review_field,
                "Approved"
            )

        if hasattr(participant, "updated_at"):
            participant.updated_at = datetime.datetime.now()

        if hasattr(tshirt_stock, "updated_at"):
            tshirt_stock.updated_at = datetime.datetime.now()

        if hasattr(lanyard_stock, "updated_at"):
            lanyard_stock.updated_at = datetime.datetime.now()

        # --------------------------------------------------------
        # SAVE ALLOCATION
        # --------------------------------------------------------
        allocation = {
            "participant_id": participant.id,
            "amount": sponsorship_amount,
            "tshirt_amount": tshirt_amount,
            "lanyard_amount": lanyard_amount,
            "previous_tshirt_status": previous_tshirt_status,
            "previous_lanyard_status": previous_lanyard_status,
            "previous_registration_status": previous_registration_status,
            "previous_sponsor_review_status": previous_sponsor_review_status,
            "sponsor_review_field": sponsor_review_field,
            "admin_username": session_user.get("username"),
        }

        db.execute(text("""
            INSERT INTO manual_sponsor_allocations (
                participant_id,
                amount,
                tshirt_amount,
                lanyard_amount,
                previous_tshirt_status,
                previous_lanyard_status,
                previous_registration_status,
                previous_sponsor_review_status,
                sponsor_review_field,
                admin_username,
                status,
                created_at
            ) VALUES (
                :participant_id,
                :amount,
                :tshirt_amount,
                :lanyard_amount,
                :previous_tshirt_status,
                :previous_lanyard_status,
                :previous_registration_status,
                :previous_sponsor_review_status,
                :sponsor_review_field,
                :admin_username,
                'Active',
                CURRENT_TIMESTAMP
            )
        """), allocation)

        db.commit()

    except Exception as exc:
        db.rollback()

        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(
                status_code=409,
                detail="This participant already has an active manual sponsorship."
            )

        print(
            "MANUAL SPONSOR TRANSACTION FAILED:",
            repr(exc)
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to create the manual sponsorship."
        )

    db.refresh(participant)
    db.refresh(donation_total)
    db.refresh(tshirt_stock)
    db.refresh(lanyard_stock)

    name = " ".join(
        x for x in [
            participant.fname,
            participant.mname,
            participant.lname
        ] if x
    ).strip()

    # ------------------------------------------------------------
    # SEND CONFIRMATION EMAIL
    # Email failure does NOT undo a successful sponsorship.
    # ------------------------------------------------------------
    email_sent = False

    try:
        email_function = globals().get(
            "send_sponsored_participant_confirmation_email"
        )

        if email_function:
            email_sent = bool(
                await email_function(
                    participant,
                    sponsorship_amount
                )
            )

    except Exception as exc:
        print(
            "MANUAL SPONSOR CONFIRMATION EMAIL FAILED:",
            repr(exc)
        )

    manual_sponsorship_id = db.execute(text("""
        SELECT id
        FROM manual_sponsor_allocations
        WHERE participant_id = :participant_id
          AND status = 'Active'
        ORDER BY id DESC
        LIMIT 1
    """), {
        "participant_id": participant.id
    }).scalar()

    return {
        "success": True,
        "message": (
            f"Manual sponsor trigger completed for {name}. "
            "T-shirt and Lanyard stock were deducted."
        ),
        "manual_sponsorship_id": manual_sponsorship_id,
        "participant_id": participant.id,
        "fullname": name,
        "tshirt_status": participant.tshirt_status,
        "lanyard_status": participant.lanyard_status,
        "registration_status": participant.registration_status,
        "sponsored_amount": sponsorship_amount,
        "sponsored_amount_display": f"₱{sponsorship_amount:,.2f}",
        "remaining_cash_donation": float(
            donation_total.total_amount or 0
        ),
        "remaining_cash_donation_display": (
            f"₱{float(donation_total.total_amount or 0):,.2f}"
        ),
        "tshirt_stock_remaining": int(
            tshirt_stock.remaining_quantity or 0
        ),
        "lanyard_stock_remaining": int(
            lanyard_stock.remaining_quantity or 0
        ),
        "participant_email_sent": email_sent
    }


@router.get("/admin/manual-sponsor/allocations")
def get_manual_sponsor_allocations(
    request: Request,
    db: Session = Depends(get_db)
):
    require_admin_session(request)

    rows = db.execute(text("""
        SELECT
            a.id,
            a.participant_id,
            a.amount,
            a.tshirt_amount,
            a.lanyard_amount,
            a.status,
            a.admin_username,
            a.created_at,
            a.cancelled_at,
            p.registration_number,
            p.fname,
            p.mname,
            p.lname,
            p.tshirt_status,
            p.lanyard_status
        FROM manual_sponsor_allocations a
        JOIN participants p
          ON p.id = a.participant_id
        ORDER BY a.id DESC
    """)).mappings().all()

    return {
        "success": True,
        "allocations": [
            {
                "id": row["id"],
                "participant_id": row["participant_id"],
                "registration_number": row["registration_number"],
                "fullname": " ".join(
                    x for x in [
                        row["fname"],
                        row["mname"],
                        row["lname"]
                    ] if x
                ).strip(),
                "amount": float(row["amount"] or 0),
                "amount_display": (
                    f"₱{float(row['amount'] or 0):,.2f}"
                ),
                "tshirt_amount": float(
                    row["tshirt_amount"] or 0
                ),
                "lanyard_amount": float(
                    row["lanyard_amount"] or 0
                ),
                "status": row["status"],
                "admin_username": row["admin_username"],
                "created_at": row["created_at"],
                "cancelled_at": row["cancelled_at"],
                "current_tshirt_status": row["tshirt_status"],
                "current_lanyard_status": row["lanyard_status"]
            }
            for row in rows
        ]
    }


@router.post("/admin/manual-sponsor/{allocation_id}/cancel")
def cancel_manual_finding_sponsor(
    allocation_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    session_user = require_admin_session(request)

    if not is_manual_finding_sponsor_enabled(db):
        raise HTTPException(
            status_code=403,
            detail=(
                "Manual Finding Sponsor function is OFF. "
                "Please turn it ON to manage manual sponsorships."
            )
        )

    row = db.execute(text("""
        SELECT *
        FROM manual_sponsor_allocations
        WHERE id = :id
        LIMIT 1
    """), {
        "id": allocation_id
    }).mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Manual sponsorship record not found."
        )

    if str(row["status"] or "").strip().lower() != "active":
        raise HTTPException(
            status_code=409,
            detail=(
                "This manual sponsorship has already been cancelled "
                "or retrieved."
            )
        )

    participant = (
        db.query(Participant)
        .filter(Participant.id == row["participant_id"])
        .first()
    )

    donation_total = (
        db.query(CashDonationTotal)
        .order_by(CashDonationTotal.id.asc())
        .first()
    )

    tshirt_stock = (
        db.query(SponsorshipItem)
        .filter(
            SponsorshipItem.item_name.ilike("T-Shirt"),
            SponsorshipItem.is_active == True
        )
        .first()
    )

    lanyard_stock = (
        db.query(SponsorshipItem)
        .filter(
            SponsorshipItem.item_name.ilike("Lanyard"),
            SponsorshipItem.is_active == True
        )
        .first()
    )

    if not participant or not donation_total:
        raise HTTPException(
            status_code=404,
            detail="Required sponsorship records were not found."
        )

    if not tshirt_stock or not lanyard_stock:
        raise HTTPException(
            status_code=404,
            detail=(
                "T-Shirt and Lanyard sponsorship inventory items must both "
                "be available to retrieve this sponsorship."
            )
        )

    try:
        # --------------------------------------------------------
        # RETURN EXACT CASH AMOUNT
        # --------------------------------------------------------
        donation_total.total_amount = round(
            float(donation_total.total_amount or 0)
            + float(row["amount"] or 0),
            2
        )

        # --------------------------------------------------------
        # RETURN EXACTLY ONE OF EACH INVENTORY ITEM
        # --------------------------------------------------------
        tshirt_stock.remaining_quantity = min(
            int(tshirt_stock.total_quantity or 0),
            int(tshirt_stock.remaining_quantity or 0) + 1
        )

        lanyard_stock.remaining_quantity = min(
            int(lanyard_stock.total_quantity or 0),
            int(lanyard_stock.remaining_quantity or 0) + 1
        )

        # --------------------------------------------------------
        # RESTORE PARTICIPANT'S PREVIOUS STATE
        # --------------------------------------------------------
        participant.tshirt_status = (
            row["previous_tshirt_status"] or "Unpaid"
        )

        participant.lanyard_status = (
            row["previous_lanyard_status"] or "Unpaid"
        )

        participant.registration_status = (
            row["previous_registration_status"]
        )

        review_field = row["sponsor_review_field"]

        if (
            review_field in (
                "sponsor_review_status",
                "sponsorship_review_status"
            )
            and hasattr(participant, review_field)
        ):
            setattr(
                participant,
                review_field,
                row["previous_sponsor_review_status"]
            )

        if hasattr(participant, "updated_at"):
            participant.updated_at = datetime.datetime.now()

        if hasattr(tshirt_stock, "updated_at"):
            tshirt_stock.updated_at = datetime.datetime.now()

        if hasattr(lanyard_stock, "updated_at"):
            lanyard_stock.updated_at = datetime.datetime.now()

        # --------------------------------------------------------
        # CLOSE ALLOCATION
        # --------------------------------------------------------
        db.execute(text("""
            UPDATE manual_sponsor_allocations
            SET status = 'Cancelled',
                cancelled_at = CURRENT_TIMESTAMP
            WHERE id = :id
              AND status = 'Active'
        """), {
            "id": allocation_id
        })

        db.commit()

    except Exception as exc:
        db.rollback()

        print(
            "MANUAL SPONSOR CANCEL/RETRIEVE FAILED:",
            repr(exc)
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to cancel/retrieve the manual sponsorship."
        )

    db.refresh(participant)
    db.refresh(donation_total)
    db.refresh(tshirt_stock)
    db.refresh(lanyard_stock)

    return {
        "success": True,
        "message": (
            "Manual sponsorship cancelled/retrieved. "
            "The T-shirt and Lanyard were returned to sponsorship stock "
            "and the participant's previous status was restored."
        ),
        "allocation_id": allocation_id,
        "participant_id": participant.id,
        "tshirt_status": participant.tshirt_status,
        "lanyard_status": participant.lanyard_status,
        "registration_status": participant.registration_status,
        "returned_amount": float(row["amount"] or 0),
        "returned_amount_display": (
            f"₱{float(row['amount'] or 0):,.2f}"
        ),
        "remaining_cash_donation": float(
            donation_total.total_amount or 0
        ),
        "remaining_cash_donation_display": (
            f"₱{float(donation_total.total_amount or 0):,.2f}"
        ),
        "tshirt_stock_remaining": int(
            tshirt_stock.remaining_quantity or 0
        ),
        "lanyard_stock_remaining": int(
            lanyard_stock.remaining_quantity or 0
        ),
        "cancelled_by": session_user.get("username")
    }
