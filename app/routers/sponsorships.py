"""Routes: sponsorships."""

from decimal import Decimal
from fastapi import Depends
from fastapi import HTTPException
from typing import List
from sqlalchemy.orm import Session
import datetime
from sqlalchemy import func
import httpx
from sqlalchemy import or_
import os
from sqlalchemy import text
import uuid
from fastapi import APIRouter

from app.database import (
    get_db,
)
from app.models import (
    CashDonationTotal,
    CashSponsorship,
    ItemSponsorship,
    Participant,
    RegistrationItem,
    SponsorshipItem,
)
from app.schemas import (
    CashSponsorshipCreate,
    CashSponsorshipResponse,
    ItemSponsorshipCreate,
    ItemSponsorshipResponse,
    SponsorshipItemCreate,
)
from app.services.email import (
    send_item_sponsorship_confirmation_email,
)
from app.services.sponsorship import (
    determine_sponsorship_tier,
)

router = APIRouter()

@router.post("/sponsorship/items")
def create_sponsorship_item(
    data: SponsorshipItemCreate,
    db: Session = Depends(get_db)
):

    item = SponsorshipItem(

        item_name=
            data.item_name.strip(),

        description=
            data.description,

        total_quantity=
            data.quantity,

        remaining_quantity=
            data.quantity,

        unit=
            data.unit.strip(),

        is_active=True

    )

    db.add(item)

    db.commit()

    db.refresh(item)

    return {

        "success": True,

        "message":
            "Sponsorship item created.",

        "item": {

            "id": item.id,

            "item_name":
                item.item_name,

            "total_quantity":
                item.total_quantity,

            "remaining_quantity":
                item.remaining_quantity,

            "unit":
                item.unit

        }

    }



































    
    
# ============================================================
# CREATE CASH SPONSORSHIP
# ============================================================
#
# IMPORTANT:
#
# This endpoint ONLY creates the sponsorship/payment.
#
# The donation is NOT added to CashDonationTotal yet because
# the PayMongo payment is still Pending.
#
# cash_total_added:
#
#     0 = donation has NOT yet been added to CashDonationTotal
#
#     donation_amount = donation has already been added
#
# The payment-success/webhook endpoint is responsible for:
#
#     1. Marking payment as Paid
#     2. Adding donation_amount to CashDonationTotal
#     3. Setting cash_total_added = donation_amount
#
# This prevents the same PayMongo payment from being added
# to CashDonationTotal multiple times.
#
# ============================================================

@router.post("/sponsorship/create_cash")
def create_cash_sponsorship(
    data: CashSponsorshipCreate,
    db: Session = Depends(get_db)
):

    # ========================================================
    # CLEAN INPUT
    # ========================================================

    selected_tier = (
        data.selected_tier.strip()
    )

    sponsor_name = (
        data.sponsor_name.strip()
    )

    local_church = (
        data.local_church.strip()
    )

    sector = (
        data.sector.strip()
    )

    amount = Decimal(
        str(data.donation_amount)
    ).quantize(
        Decimal("0.01")
    )

    # ========================================================
    # VALIDATE AMOUNT
    # ========================================================

    if amount <= 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "Donation amount must be "
                "greater than ₱0.00."
            )
        )

    # ========================================================
    # DETERMINE CORRECT TIER
    # ========================================================

    correct_tier = (
        determine_sponsorship_tier(
            amount
        )
    )

    # ========================================================
    # CHECK SELECTED TIER
    # ========================================================

    if (
        selected_tier.lower()
        !=
        correct_tier.lower()
    ):

        if (
            correct_tier
            ==
            "1st (Bronze) Tier"
        ):

            message = (
                f"Your donation of "
                f"₱{amount:,.2f} belongs to "
                f"the 1st (Bronze) Tier, "
                f"which is below ₱1,000. "
                f"Please reselect the "
                f"1st (Bronze) Tier package."
            )

        elif (
            correct_tier
            ==
            "2nd (Silver) Tier"
        ):

            message = (
                f"Your donation of "
                f"₱{amount:,.2f} belongs to "
                f"the 2nd (Silver) Tier, "
                f"which is ₱1,000 to below "
                f"₱2,000. Please reselect "
                f"the 2nd (Silver) Tier package."
            )

        elif (
            correct_tier
            ==
            "3rd (Gold) Tier"
        ):

            message = (
                f"Your donation of "
                f"₱{amount:,.2f} belongs to "
                f"the 3rd (Gold) Tier, "
                f"which is ₱2,000 to below "
                f"₱3,000. Please reselect "
                f"the 3rd (Gold) Tier package."
            )

        else:

            message = (
                f"Your donation of "
                f"₱{amount:,.2f} belongs to "
                f"the 4th (Diamond) Tier, "
                f"which is ₱3,000 and above. "
                f"Please reselect the "
                f"4th (Diamond) Tier package."
            )

        raise HTTPException(
            status_code=400,
            detail=message
        )

    # ========================================================
    # CREATE LOCAL SPONSORSHIP RECORD
    # ========================================================
    #
    # IMPORTANT:
    #
    # cash_total_added = 0
    #
    # The donation is NOT yet available for Finding Sponsor
    # participants.
    #
    # It becomes available only after PayMongo confirms
    # successful payment.
    #
    # ========================================================

    sponsorship = CashSponsorship(

        sponsor_name=sponsor_name,

        local_church=local_church,

        contact=(
            data.contact.strip()
            if data.contact
            else None
        ),

        sector=sector,

        email=(
            str(data.email)
            if data.email
            else None
        ),

        selected_tier=correct_tier,

        donation_amount=int(
            amount * 100
        ),

        payment_status="Pending",

        # ----------------------------------------------------
        # IMPORTANT
        # ----------------------------------------------------
        # Nothing has been added to CashDonationTotal yet.
        #
        # This value will be updated by the payment-success
        # / webhook logic.
        #
        cash_total_added=0

    )

    db.add(
        sponsorship
    )

    db.commit()

    db.refresh(
        sponsorship
    )

    # ========================================================
    # PAYMONGO AMOUNT
    # ========================================================

    paymongo_amount = int(
        amount * 100
    )

    # ========================================================
    # DESCRIPTION
    # ========================================================

    description = (
        f"Sponsorship - "
        f"{correct_tier} - "
        f"{sponsor_name}"
    )

    # ========================================================
    # REMARKS
    # ========================================================

    remarks = (
        f"Sponsorship ID: "
        f"{sponsorship.id}"
    )

    # ========================================================
    # PAYMONGO SECRET KEY
    # ========================================================

    secret_key = os.getenv(
        "PAYMONGO_SECRET_KEY"
    )

    if not secret_key:

        sponsorship.payment_status = (
            "Failed"
        )

        db.commit()

        raise HTTPException(
            status_code=500,
            detail=(
                "PAYMONGO_SECRET_KEY "
                "is not configured."
            )
        )

    # ========================================================
    # PAYMONGO PAYLOAD
    # ========================================================

    payload = {

        "amount":
            paymongo_amount,

        "currency":
            "PHP",

        "description":
            description,

        "remarks":
            remarks,

        "metadata": {

            "type":
                "cash_sponsorship",

            "sponsorship_id":
                str(sponsorship.id),

            "sponsor_name":
                sponsor_name,

            "tier":
                correct_tier,

            "email":
                (
                    str(data.email)
                    if data.email
                    else ""
                )

        }

    }

    # ========================================================
    # CREATE PAYMONGO PAYMENT LINK
    # ========================================================

    try:

        response = httpx.post(

            "https://api.paymongo.com/v1/payment_links",

            auth=(
                secret_key,
                ""
            ),

            headers={

                "Content-Type":
                    "application/json",

                "Accept":
                    "application/json",

                "Idempotency-Key":
                    (
                        f"sponsorship-"
                        f"{sponsorship.id}-"
                        f"{uuid.uuid4()}"
                    )

            },

            json=payload,

            timeout=30

        )

    except Exception as e:

        sponsorship.payment_status = (
            "Failed"
        )

        db.commit()

        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to connect to PayMongo: "
                f"{str(e)}"
            )
        )

    # ========================================================
    # PAYMONGO ERROR
    # ========================================================

    if response.status_code not in [
        200,
        201
    ]:

        try:

            error_data = (
                response.json()
            )

        except Exception:

            error_data = {
                "detail":
                    response.text
            }

        sponsorship.payment_status = (
            "Failed"
        )

        db.commit()

        raise HTTPException(
            status_code=502,
            detail={

                "message":
                    "PayMongo rejected "
                    "the payment link.",

                "paymongo":
                    error_data

            }
        )

    # ========================================================
    # PARSE PAYMONGO RESPONSE
    # ========================================================

    try:

        result = (
            response.json()
        )

        payment_data = (
            result.get(
                "data",
                {}
            )
        )

        payment_link_id = (
            payment_data.get(
                "id"
            )
        )

        payment_attributes = (
            payment_data.get(
                "attributes",
                {}
            )
        )

        payment_url = (

            payment_attributes.get(
                "checkout_url"
            )

            or

            payment_attributes.get(
                "url"
            )

            or

            payment_data.get(
                "url"
            )

        )

        reference_number = (

            payment_attributes.get(
                "reference_number"
            )

            or

            payment_data.get(
                "reference_number"
            )

        )

    except Exception:

        sponsorship.payment_status = (
            "Failed"
        )

        db.commit()

        raise HTTPException(
            status_code=502,
            detail=(
                "Invalid response received "
                "from PayMongo."
            )
        )

    # ========================================================
    # VALIDATE PAYMENT LINK ID
    # ========================================================

    if not payment_link_id:

        sponsorship.payment_status = (
            "Failed"
        )

        db.commit()

        raise HTTPException(
            status_code=502,
            detail=(
                "PayMongo did not return "
                "a payment link ID."
            )
        )

    # ========================================================
    # VALIDATE PAYMENT URL
    # ========================================================

    if not payment_url:

        sponsorship.payment_status = (
            "Failed"
        )

        db.commit()

        raise HTTPException(
            status_code=502,
            detail=(
                "PayMongo did not return "
                "a payment URL."
            )
        )

    # ========================================================
    # SAVE PAYMONGO DETAILS
    # ========================================================

    sponsorship.paymongo_link_id = (
        payment_link_id
    )

    sponsorship.paymongo_reference = (
        reference_number
    )

    sponsorship.payment_url = (
        payment_url
    )

    # --------------------------------------------------------
    # REMAIN PENDING
    # --------------------------------------------------------

    sponsorship.payment_status = (
        "Pending"
    )

    # --------------------------------------------------------
    # STILL NOT ADDED TO CASH DONATION TOTAL
    # --------------------------------------------------------

    sponsorship.cash_total_added = 0

    db.commit()

    db.refresh(
        sponsorship
    )

    # ========================================================
    # RESPONSE
    # ========================================================

    return {

        "success":
            True,

        "message":
            "Sponsorship created successfully. "
            "Payment is currently pending.",

        "sponsorship_id":
            sponsorship.id,

        "sponsor_name":
            sponsorship.sponsor_name,

        "tier":
            correct_tier,

        "donation_amount":
            float(amount),

        "payment_status":
            sponsorship.payment_status,

        # ----------------------------------------------------
        # IMPORTANT
        # ----------------------------------------------------
        # This confirms to the frontend that the money has
        # NOT yet entered the available sponsorship balance.
        #
        "cash_total_added":
            sponsorship.cash_total_added,

        "cash_total_added_display":
            "₱0.00",

        "cash_donation_total_updated":
            False,

        "payment_id":
            payment_link_id,

        "paymongo_link_id":
            payment_link_id,

        "reference_number":
            reference_number,

        "payment_url":
            payment_url

    }
    
    
    
    
    
    
    
    
    


# ============================================================
# GET AVAILABLE SPONSORSHIP ITEMS
# ============================================================

@router.get("/sponsorship/items")
def get_sponsorship_items(
    db: Session = Depends(get_db)
):

    items = db.query(
        SponsorshipItem
    ).filter(
        SponsorshipItem.is_active == True
    ).order_by(
        SponsorshipItem.item_name.asc()
    ).all()

    result = []

    for item in items:

        result.append({

            "id":
                item.id,

            "item_name":
                item.item_name,

            "description":
                item.description,

            "total_quantity":
                item.total_quantity,

            "remaining_quantity":
                item.remaining_quantity,

            "unit":
                item.unit,

            "available":
                item.remaining_quantity > 0

        })

    return result       





















# ============================================================
# SPONSORSHIP PAYMENT STATUS
# ============================================================
#
# Used by the cash sponsorship payment page to continuously
# check whether the sponsorship payment has been completed.
#
# The frontend sends the PayMongo Link ID:
#
#     /sponsorship/payment/status/{payment_id}
#
# The endpoint first finds the CashSponsorship by the stored
# PayMongo Link ID.
#
# After the webhook receives payment.paid, the webhook updates:
#
#     payment_status = "Paid"
#
# Therefore this endpoint will automatically return:
#
#     paid = True
#
# ============================================================

@router.get("/sponsorship/payment/status/{payment_id}")
def sponsorship_payment_status(
    payment_id: str,
    db: Session = Depends(get_db)
):

    # ======================================================
    # FIND SPONSORSHIP BY PAYMONGO LINK ID
    # ======================================================

    sponsorship = (
        db.query(CashSponsorship)
        .filter(
            CashSponsorship.paymongo_link_id == payment_id
        )
        .first()
    )

    # ======================================================
    # SPONSORSHIP NOT FOUND
    # ======================================================

    if not sponsorship:

        print("=" * 70)
        print("SPONSORSHIP PAYMENT STATUS")
        print("=" * 70)
        print("Requested Payment ID:", payment_id)
        print("SPONSORSHIP NOT FOUND")
        print("=" * 70)

        return {
            "success": False,
            "found": False,
            "payment_status": "Not Found",
            "paid": False
        }

    # ======================================================
    # GET PAYMENT STATUS
    # ======================================================

    payment_status = str(
        sponsorship.payment_status or "Pending"
    ).strip().lower()

    # ======================================================
    # DETERMINE IF PAID
    # ======================================================

    paid = payment_status in [
        "paid",
        "succeeded",
        "successful",
        "completed"
    ]

    # ======================================================
    # DEBUG LOG
    # ======================================================

    print("=" * 70)
    print("SPONSORSHIP PAYMENT STATUS")
    print("=" * 70)

    print(
        "Requested Payment ID:",
        payment_id
    )

    print(
        "Sponsorship ID:",
        sponsorship.id
    )

    print(
        "PayMongo Link ID:",
        sponsorship.paymongo_link_id
    )

    print(
        "PayMongo Reference:",
        sponsorship.paymongo_reference
    )

    print(
        "Payment Status:",
        sponsorship.payment_status
    )

    print(
        "Paid:",
        paid
    )

    print("=" * 70)

    # ======================================================
    # RESPONSE
    # ======================================================

    return {

        "success":
            True,

        "found":
            True,

        "sponsorship_id":
            sponsorship.id,

        "payment_status":
            sponsorship.payment_status or "Pending",

        "paid":
            paid,

        "paymongo_link_id":
            sponsorship.paymongo_link_id,

        "paymongo_reference":
            sponsorship.paymongo_reference
    }










# ============================================================
# CREATE ITEM SPONSORSHIP
# ============================================================

@router.post("/sponsorship/create_item")
async def create_item_sponsorship(
    data: ItemSponsorshipCreate,
    db: Session = Depends(get_db)
):

    print()
    print("============================================================")
    print("ITEM SPONSORSHIP REQUEST")
    print("============================================================")

    print("Sponsor:", data.sponsor_name)
    print("Local Church:", data.local_church)
    print("Visiting Church:", getattr(data, "visiting_church", None))
    print("Sector:", data.sector)
    print("Contact:", data.contact)
    print("Email:", data.email)
    print("Items:", data.items)

    # ========================================================
    # NORMALIZE CONTACT / EMAIL
    # ========================================================

    contact = (
        str(data.contact).strip()
        if data.contact
        else "0910101010"
    )

    email = (
        str(data.email).strip()
        if data.email
        else "optional@mail.com"
    )

    sponsor_name = (
        data.sponsor_name.strip()
    )

    local_church = (
        data.local_church.strip()
    )

    sector = (
        data.sector.strip()
    )

    visiting_church = getattr(
        data,
        "visiting_church",
        None
    )

    if visiting_church:
        visiting_church = (
            visiting_church.strip()
        )

    # ========================================================
    # VALIDATE BASIC INFORMATION
    # ========================================================

    if not sponsor_name:

        raise HTTPException(
            status_code=400,
            detail="Sponsor name is required."
        )

    if not local_church:

        raise HTTPException(
            status_code=400,
            detail="Local church is required."
        )

    if not sector:

        raise HTTPException(
            status_code=400,
            detail="Sector is required."
        )

    # ========================================================
    # VALIDATE ITEMS
    # ========================================================

    if not data.items:

        raise HTTPException(
            status_code=400,
            detail="Please select at least one item."
        )

    # ========================================================
    # PREVENT DUPLICATE ITEM IDS
    # ========================================================

    item_ids = []

    for selected_item in data.items:

        try:

            item_id = int(
                selected_item.item_id
            )

        except (
            ValueError,
            TypeError
        ):

            raise HTTPException(
                status_code=400,
                detail="Invalid sponsorship item ID."
            )

        if item_id in item_ids:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Item {item_id} was selected "
                    f"more than once."
                )
            )

        item_ids.append(item_id)

    # ========================================================
    # START TRANSACTION
    # ========================================================

    created_donations = []

    try:

        # ====================================================
        # PROCESS EVERY SELECTED ITEM
        # ====================================================

        for selected_item in data.items:

            item = db.query(
                SponsorshipItem
            ).filter(
                SponsorshipItem.id ==
                selected_item.item_id,

                SponsorshipItem.is_active ==
                True
            ).first()

            # ------------------------------------------------
            # ITEM NOT FOUND
            # ------------------------------------------------

            if not item:

                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Sponsorship item "
                        f"{selected_item.item_id} "
                        f"was not found."
                    )
                )

            # ------------------------------------------------
            # QUANTITY
            # ------------------------------------------------

            try:

                quantity = int(
                    selected_item.quantity
                )

            except (
                ValueError,
                TypeError
            ):

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid quantity for "
                        f"{item.item_name}."
                    )
                )

            # ------------------------------------------------
            # VALIDATE QUANTITY
            # ------------------------------------------------

            if quantity <= 0:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Quantity for "
                        f"{item.item_name} "
                        f"must be greater than 0."
                    )
                )

            # ------------------------------------------------
            # INVENTORY
            # ------------------------------------------------

            if item.remaining_quantity <= 0:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"{item.item_name} "
                        f"is already fully sponsored."
                    )
                )

            if quantity > item.remaining_quantity:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Only "
                        f"{item.remaining_quantity} "
                        f"{item.unit} remaining for "
                        f"{item.item_name}."
                    )
                )

            # ------------------------------------------------
            # SAVE ORIGINAL INFORMATION
            # ------------------------------------------------

            item_name = item.item_name

            unit = item.unit

            # ------------------------------------------------
            # REDUCE INVENTORY
            # ------------------------------------------------

            item.remaining_quantity -= quantity

            # ------------------------------------------------
            # CREATE DONATION
            #
            # IMPORTANT:
            #
            # visiting_church is NOT passed here because
            # your current ItemSponsorship SQLAlchemy model
            # does not have that column.
            # ------------------------------------------------

            donation = ItemSponsorship(

                sponsor_name=
                    sponsor_name,

                local_church=
                    local_church,

                contact=
                    contact,

                sector=
                    sector,

                email=
                    email,

                item_id=
                    item.id,

                item_name=
                    item_name,

                quantity=
                    quantity,

                status=
                    "Confirmed"
            )

            db.add(donation)

            created_donations.append({

                "donation":
                    donation,

                "item":
                    item,

                "item_name":
                    item_name,

                "unit":
                    unit,

                "quantity":
                    quantity

            })

        # ====================================================
        # COMMIT ALL ITEMS TOGETHER
        # ====================================================

        db.commit()

        # ====================================================
        # REFRESH DONATIONS
        # ====================================================

        for record in created_donations:

            db.refresh(
                record["donation"]
            )

            db.refresh(
                record["item"]
            )

        print()
        print(
            "ITEM SPONSORSHIP DATABASE SAVE SUCCESSFUL"
        )

        # ====================================================
        # SEND ONE CONFIRMATION EMAIL
        # ====================================================

        email_sent = False

        try:

            # ------------------------------------------------
            # If your current email function accepts ONE
            # donation object, send one email per donation.
            # ------------------------------------------------

            for record in created_donations:

                try:

                    await send_item_sponsorship_confirmation_email(
                        record["donation"]
                    )

                    email_sent = True

                except Exception as email_error:

                    print(
                        "Item sponsorship email failed:",
                        repr(email_error)
                    )

        except Exception as e:

            print(
                "Item sponsorship email error:",
                repr(e)
            )

        # ====================================================
        # BUILD ITEM SUMMARY
        # ====================================================

        item_summary = []

        for record in created_donations:

            donation = record["donation"]

            item_summary.append({

                "donation_id":
                    donation.id,

                "item_id":
                    donation.item_id,

                "item":
                    donation.item_name,

                "quantity":
                    donation.quantity,

                "unit":
                    record["unit"],

                "remaining_quantity":
                    record["item"].remaining_quantity,

                "status":
                    donation.status

            })

        # ====================================================
        # THANK YOU MESSAGE
        # ====================================================

        item_text = ", ".join(

            f'{record["quantity"]} '
            f'{record["unit"]} '
            f'{record["item_name"]}'

            for record
            in created_donations

        )

        thank_you_message = (

            f"Thank you {sponsor_name} "
            f"for your item donation: "
            f"{item_text}. "
            f"Please deliver the donation to the "
            f"donation designation area at "
            f"Butuan Grace Baptist Church "
            f"or contact Pastor Edward Deligero "
            f"at 0911 252 3584."

        )

        # ====================================================
        # RESPONSE
        # ====================================================

        return {

            "success":
                True,

            "message":
                "Item donation recorded successfully.",

            "donation_count":
                len(created_donations),

            "sponsor_name":
                sponsor_name,

            "local_church":
                local_church,

            "visiting_church":
                visiting_church,

            "sector":
                sector,

            "contact":
                contact,

            "email":
                email,

            "items":
                item_summary,

            "email_sent":
                email_sent,

            "thank_you_message":
                thank_you_message

        }

    except HTTPException:

        # ====================================================
        # ROLLBACK
        # ====================================================

        db.rollback()

        raise

    except Exception as e:

        # ====================================================
        # ROLLBACK
        # ====================================================

        db.rollback()

        print()
        print(
            "ITEM SPONSORSHIP DATABASE ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to record item donation."
            )
        )
    

# ============================================================
# VIEW ALL ITEM SPONSORSHIPS
# ============================================================

@router.get(
    "/sponsor_items",
    response_model=List[ItemSponsorshipResponse]
)
def view_all_sponsor_items(
    db: Session = Depends(get_db)
):

    items = (
        db.query(ItemSponsorship)
        .order_by(
            ItemSponsorship.created_at.desc()
        )
        .all()
    )

    return items


# ============================================================
# VIEW SINGLE ITEM SPONSORSHIP
# ============================================================

@router.get(
    "/sponsor_items/{sponsor_id}",
    response_model=ItemSponsorshipResponse
)
def view_single_sponsor_item(
    sponsor_id: int,
    db: Session = Depends(get_db)
):

    item = (
        db.query(ItemSponsorship)
        .filter(
            ItemSponsorship.id == sponsor_id
        )
        .first()
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail="Item sponsorship not found."
        )

    return item


# ============================================================
# VIEW ALL CASH SPONSORSHIPS
# ============================================================

@router.get(
    "/sponsor_cash",
    response_model=List[CashSponsorshipResponse]
)
def view_all_sponsor_cash(
    db: Session = Depends(get_db)
):

    sponsorships = (
        db.query(CashSponsorship)
        .order_by(
            CashSponsorship.created_at.desc()
        )
        .all()
    )

    return sponsorships


# ============================================================
# VIEW SINGLE CASH SPONSORSHIP
# ============================================================

@router.get(
    "/sponsor_cash/{sponsor_id}",
    response_model=CashSponsorshipResponse
)
def view_single_sponsor_cash(
    sponsor_id: int,
    db: Session = Depends(get_db)
):

    sponsorship = (
        db.query(CashSponsorship)
        .filter(
            CashSponsorship.id == sponsor_id
        )
        .first()
    )

    if not sponsorship:

        raise HTTPException(
            status_code=404,
            detail="Cash sponsorship not found."
        )

    return sponsorship




# ============================================================
# MANUAL FIND SPONSOR / PROCESS SPONSOR QUEUE
# ============================================================
#
# POST /process_finding_sponsor_queue
#
# CashDonationTotal.total_amount:
#     STORED IN PESOS
#
# RegistrationItem.price:
#     STORED IN CENTAVOS
#
# Example:
#
# T-shirt:
#     35000 centavos = ₱350.00
#
# Lanyard:
#     9000 centavos = ₱90.00
#
# Required per participant:
#     ₱350 + ₱90 = ₱440
#
# If sponsorship fund = ₱1,250:
#
# Participant 1 = ₱440
# Participant 2 = ₱440
# Remaining     = ₱370
#
# After sponsorship:
#
# - T-shirt = Paid
# - Lanyard = Paid
# - Registration = Confirmed
# - Sponsor review = Approved (if field exists)
# - Participant receives confirmation email
#
# IMPORTANT:
#
# This endpoint does NOT add money to the sponsorship fund.
# It only uses the existing CashDonationTotal balance.
#
# ============================================================










@router.post("/process_finding_sponsor_queue")
async def process_finding_sponsor_queue(
    db: Session = Depends(get_db)
):

    # ========================================================
    # CHECK MANUAL FINDING SPONSOR SETTING
    #
    # IMPORTANT:
    # This setting ONLY controls queue processing.
    #
    # It does NOT block:
    # - /sponsorship/create_cash
    # - PayMongo payments
    # - PayMongo webhook payment recording
    #
    # When OFF, this endpoint cannot process the queue.
    # ========================================================

    manual_sponsor_setting = db.execute(text("""
        SELECT enabled
        FROM manual_sponsor_settings
        WHERE id = 1
    """)).fetchone()

    if (
        not manual_sponsor_setting
        or not bool(manual_sponsor_setting[0])
    ):

        print("\n")
        print("=" * 70)
        print("MANUAL FIND SPONSOR PROCESSING BLOCKED")
        print("=" * 70)
        print(
            "Manual Finding Sponsor function is currently OFF."
        )
        print("=" * 70)

        raise HTTPException(
            status_code=403,
            detail=(
                "Manual Finding Sponsor function is "
                "currently turned OFF by the administrator."
            )
        )


    print("\n")
    print("=" * 70)
    print("MANUAL FIND SPONSOR PROCESSING")
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

        raise HTTPException(
            status_code=404,
            detail="T-shirt registration item was not found."
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

        raise HTTPException(
            status_code=404,
            detail="Lanyard registration item was not found."
        )

    # ========================================================
    # GET PRICES
    #
    # RegistrationItem.price = CENTAVOS
    #
    # 35000 = ₱350.00
    # 9000  = ₱90.00
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
    # REQUIRED AMOUNT PER PARTICIPANT
    # ========================================================

    required_amount = (
        tshirt_price +
        lanyard_price
    )

    if required_amount <= 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "T-shirt and lanyard prices must be "
                "greater than zero."
            )
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
    # GET CURRENT CASH DONATION TOTAL
    #
    # CashDonationTotal.total_amount = PESOS
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

        return {

            "success": True,

            "message":
                "No CashDonationTotal record exists.",

            "status":
                "Queued",

            "cash_donation_total":
                0,

            "cash_donation_total_display":
                "₱0.00",

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

            "sponsored_count":
                0,

            "remaining_queue_count":
                0,

            "participants":
                []

        }

    # ========================================================
    # CURRENT BALANCE
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
    # Oldest participant is processed first.
    #
    # IMPORTANT:
    #
    # func and or_ must come from SQLAlchemy:
    #
    # from sqlalchemy import func, or_
    #
    # Do NOT use:
    #
    # db.func
    # db.or_
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
    # NO PARTICIPANTS
    # ========================================================

    if initial_queue_count == 0:

        print(
            "No Finding Sponsor participants waiting."
        )

        return {

            "success": True,

            "message":
                "No Finding Sponsor participants are waiting for sponsorship.",

            "status":
                "Completed",

            "cash_donation_total":
                current_balance,

            "cash_donation_total_display":
                f"₱{current_balance:,.2f}",

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
    # NOT ENOUGH FOR EVEN ONE PARTICIPANT
    # ========================================================

    if current_balance < required_amount:

        amount_needed = (
            required_amount -
            current_balance
        )

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
            f"₱{amount_needed:,.2f}"
        )

        return {

            "success": True,

            "message":
                "Cash donation balance is insufficient to sponsor the next participant.",

            "status":
                "Queued",

            "cash_donation_total":
                current_balance,

            "cash_donation_total_display":
                f"₱{current_balance:,.2f}",

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

            "amount_still_needed":
                amount_needed,

            "amount_still_needed_display":
                f"₱{amount_needed:,.2f}",

            "initial_queue_count":
                initial_queue_count,

            "sponsored_count":
                0,

            "remaining_queue_count":
                initial_queue_count,

            "participant_emails_sent":
                0,

            "participant_email_errors":
                [],

            "participants":
                []

        }

    # ========================================================
    # PROCESS PARTICIPANTS
    # ========================================================

    sponsored_participants = []

    try:

        for participant in finding_sponsors:

            # =================================================
            # STOP WHEN BALANCE IS NOT ENOUGH
            # =================================================

            if current_balance < required_amount:

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

            # Prevent floating-point negative values
            if abs(current_balance) < 0.000001:

                current_balance = 0.0

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
            # Supports either possible field name.
            # =================================================

            sponsor_review_field = None

            if hasattr(
                participant,
                "sponsor_review_status"
            ):

                participant.sponsor_review_status = (
                    "Approved"
                )

                sponsor_review_field = (
                    "sponsor_review_status"
                )

            elif hasattr(
                participant,
                "sponsorship_review_status"
            ):

                participant.sponsorship_review_status = (
                    "Approved"
                )

                sponsor_review_field = (
                    "sponsorship_review_status"
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
            # RECORD PARTICIPANT
            # =================================================

            sponsor_review_status = (
                getattr(
                    participant,
                    "sponsor_review_status",
                    None
                )
            )

            if sponsor_review_status is None:

                sponsor_review_status = (
                    getattr(
                        participant,
                        "sponsorship_review_status",
                        "Approved"
                    )
                )

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

                "email":
                    getattr(
                        participant,
                        "email",
                        None
                    ),

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
                    sponsor_review_status,

                "sponsor_review_field":
                    sponsor_review_field,

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
                sponsor_review_status
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

        print(
            "=" * 70
        )

        print(
            "MANUAL FIND SPONSOR ERROR:"
        )

        print(
            repr(e)
        )

        print(
            "=" * 70
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to process Finding Sponsor "
                "participants."
            )
        )

    # ========================================================
    # GET REMAINING QUEUE
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

    # ========================================================
    # DETERMINE QUEUE STATUS
    # ========================================================

    if len(remaining_queue) == 0:

        queue_status = "Completed"

    elif current_balance >= required_amount:

        queue_status = "Ready"

    else:

        queue_status = "Queued"

    # ========================================================
    # SEND SPONSORED PARTICIPANT EMAILS
    # ========================================================
    #
    # The email function must exist somewhere above/before
    # this endpoint:
    #
    # async def send_sponsored_participant_confirmation_email(
    #     participant
    # ):
    #
    # This endpoint uses:
    #
    # await email_function(participant)
    #
    # ========================================================

    participant_emails_sent = 0

    participant_email_errors = []

    email_function = globals().get(
        "send_sponsored_participant_confirmation_email"
    )

    if not email_function:

        print(
            "WARNING: "
            "send_sponsored_participant_confirmation_email "
            "is not defined."
        )

        print(
            "Participants were sponsored successfully, "
            "but confirmation emails were not sent."
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
                        sponsored["participant_id"]
                    )
                    .first()
                )

                if not sponsored_participant:

                    print(
                        "Sponsored participant not found:",
                        sponsored["participant_id"]
                    )

                    participant_email_errors.append({

                        "participant_id":
                            sponsored["participant_id"],

                        "error":
                            "Participant not found after sponsorship."

                    })

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
                        sponsored["participant_id"]
                    )

                    participant_email_errors.append({

                        "participant_id":
                            sponsored["participant_id"],

                        "error":
                            "Participant has no email address."

                    })

                    continue

                # ==========================================
                # SEND EMAIL
                # ==========================================

                print(
                    "Sending sponsored participant email to:",
                    participant_email
                )

                await email_function(
                sponsored_participant,
                sponsored["sponsored_amount"]
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
                    sponsored["participant_id"]
                )

                print(
                    "Error:",
                    repr(e)
                )

                participant_email_errors.append({

                    "participant_id":
                        sponsored["participant_id"],

                    "error":
                        str(e)

                })

    # ========================================================
    # TOTAL SPONSORED AMOUNT
    # ========================================================

    total_sponsored_amount = (
        len(sponsored_participants) *
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
        len(
            remaining_queue
        )
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
    # RETURN
    # ========================================================

    return {

        "success": True,

        "message":
            "Finding Sponsor queue processed successfully.",

        "status":
            queue_status,

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
        # QUEUE
        # ====================================================

        "initial_queue_count":
            initial_queue_count,

        "sponsored_count":
            len(
                sponsored_participants
            ),

        "remaining_queue_count":
            len(
                remaining_queue
            ),

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











    





# ============================================================
# SPONSOR DASHBOARD STATISTICS
# ============================================================

@router.get("/sponsor_dashboard_stats")
def sponsor_dashboard_stats(
    db: Session = Depends(get_db)
):
    # ========================================================
    # GET CURRENT CASH DONATION FUND
    #
    # CashDonationTotal.total_amount is already stored in PESOS.
    #
    # Example:
    # 1500 = ₱1,500.00
    #
    # DO NOT divide this value by 100.
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

    if donation_total:
        try:
            cash_donation_total = float(
                donation_total.total_amount or 0
            )
        except (
            ValueError,
            TypeError
        ):
            cash_donation_total = 0.0
    else:
        cash_donation_total = 0.0


    # ========================================================
    # GET FINDING SPONSOR PARTICIPANTS
    #
    # A participant is considered a completed sponsored
    # participant when:
    #
    # - participant_type = Finding Sponsor
    # - T-Shirt is Paid
    # - Lanyard is Paid
    # - participant is NOT archived
    #
    # These participants are the ones whose sponsorship cost
    # is deducted from the donation fund.
    # ========================================================

    finding_sponsor_participants = (
        db.query(
            Participant
        )
        .filter(
            Participant.is_archived == 0,

            Participant.participant_type.ilike(
                "Finding Sponsor"
            ),

            func.lower(
                func.coalesce(
                    Participant.tshirt_status,
                    "Unpaid"
                )
            ) == "paid",

            func.lower(
                func.coalesce(
                    Participant.lanyard_status,
                    "Unpaid"
                )
            ) == "paid"
        )
        .count()
    )


    # ========================================================
    # TOTAL SPONSORED PARTICIPANTS
    #
    # Keep this field for compatibility with the existing
    # frontend.
    #
    # It represents the same completed Finding Sponsor
    # participants.
    # ========================================================

    total_sponsored_participants = (
        finding_sponsor_participants
    )


    # ========================================================
    # GET CURRENT T-SHIRT PRICE
    #
    # RegistrationItem.price is stored in CENTAVOS.
    #
    # Example:
    # 35000 = ₱350.00
    # ========================================================

    tshirt_item = (
        db.query(
            RegistrationItem
        )
        .filter(
            RegistrationItem.item_name.ilike(
                "T-Shirt"
            ),
            RegistrationItem.is_active == True
        )
        .first()
    )

    tshirt_price = 0.0

    if tshirt_item:
        try:
            tshirt_price = (
                int(
                    tshirt_item.price or 0
                ) / 100
            )
        except (
            ValueError,
            TypeError
        ):
            tshirt_price = 0.0


    # ========================================================
    # GET CURRENT LANYARD PRICE
    #
    # RegistrationItem.price is stored in CENTAVOS.
    #
    # Example:
    # 9000 = ₱90.00
    # ========================================================

    lanyard_item = (
        db.query(
            RegistrationItem
        )
        .filter(
            RegistrationItem.item_name.ilike(
                "Lanyard"
            ),
            RegistrationItem.is_active == True
        )
        .first()
    )

    lanyard_price = 0.0

    if lanyard_item:
        try:
            lanyard_price = (
                int(
                    lanyard_item.price or 0
                ) / 100
            )
        except (
            ValueError,
            TypeError
        ):
            lanyard_price = 0.0


    # ========================================================
    # SPONSORSHIP COST PER PARTICIPANT
    #
    # Every Finding Sponsor participant receives:
    #
    # T-Shirt + Lanyard
    #
    # Example:
    # T-Shirt = ₱350
    # Lanyard = ₱90
    #
    # Sponsorship cost = ₱440 per participant
    # ========================================================

    sponsorship_amount_per_participant = (
        tshirt_price +
        lanyard_price
    )


    # ========================================================
    # TOTAL USED DONATION FUND
    #
    # Example:
    #
    # Finding Sponsor participants = 10
    # Sponsorship cost per participant = ₱440
    #
    # Used Donation Fund:
    #
    # 10 × ₱440 = ₱4,400
    # ========================================================

    total_used_donation_fund = (
        finding_sponsor_participants *
        sponsorship_amount_per_participant
    )


    # ========================================================
    # TOTAL DONATION FUND EVER RECEIVED
    #
    # Current remaining cash balance
    # +
    # amount already used for Finding Sponsor participants
    # ========================================================

    total_donation_fund_received = (
        cash_donation_total +
        total_used_donation_fund
    )


    # ========================================================
    # RETURN DASHBOARD STATISTICS
    #
    # IMPORTANT:
    #
    # CashDonationTotal.total_amount is already PESOS.
    #
    # RegistrationItem.price is CENTAVOS, therefore the item
    # prices were converted to PESOS above.
    # ========================================================

    return {
        "success": True,

        # ----------------------------------------------------
        # CURRENT REMAINING CASH DONATION FUND
        # ----------------------------------------------------

        "cash_donation_total":
            round(
                cash_donation_total,
                2
            ),

        "cash_donation_total_display":
            f"₱{cash_donation_total:,.2f}",

        "remaining_donation_fund":
            round(
                cash_donation_total,
                2
            ),

        "remaining_donation_fund_display":
            f"₱{cash_donation_total:,.2f}",


        # ----------------------------------------------------
        # FINDING SPONSOR PARTICIPANTS
        # ----------------------------------------------------

        "finding_sponsor_participants":
            finding_sponsor_participants,

        "total_sponsored_participants":
            total_sponsored_participants,


        # ----------------------------------------------------
        # INDIVIDUAL SPONSORSHIP ITEM PRICES
        #
        # These are returned explicitly so report.html can
        # calculate the sponsorship cost even if the combined
        # value is missing.
        # ----------------------------------------------------

        "tshirt_price":
            round(
                tshirt_price,
                2
            ),

        "tshirt_price_display":
            f"₱{tshirt_price:,.2f}",

        "lanyard_price":
            round(
                lanyard_price,
                2
            ),

        "lanyard_price_display":
            f"₱{lanyard_price:,.2f}",


        # ----------------------------------------------------
        # SPONSORSHIP COST PER PARTICIPANT
        # ----------------------------------------------------

        "sponsorship_amount_per_participant":
            round(
                sponsorship_amount_per_participant,
                2
            ),

        "sponsorship_amount_per_participant_display":
            f"₱{sponsorship_amount_per_participant:,.2f}",


        # ----------------------------------------------------
        # TOTAL USED DONATION FUND
        # ----------------------------------------------------

        "total_used_donation_fund":
            round(
                total_used_donation_fund,
                2
            ),

        "total_used_donation_fund_display":
            f"₱{total_used_donation_fund:,.2f}",


        # ----------------------------------------------------
        # TOTAL DONATION FUND EVER RECEIVED
        # ----------------------------------------------------

        "total_donation_fund_received":
            round(
                total_donation_fund_received,
                2
            ),

        "total_donation_fund_received_display":
            f"₱{total_donation_fund_received:,.2f}"
    }
