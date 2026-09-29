"""Routes: dashboards."""

from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from sqlalchemy.orm import Session
import datetime
from sqlalchemy import func
from fastapi import APIRouter

from app.database import (
    get_db,
)
from app.models import (
    CashDonationTotal,
    CashSponsorship,
    Chaperone,
    Event,
    ItemSponsorship,
    Participant,
    ParticipantEvaluation,
    Payment,
    SponsorshipItem,
    Staff,
    StoreItem,
    User,
)

router = APIRouter()

    
# ======================================================
# REGISTRATION SUMMARY DASHBOARD
# ======================================================  

@router.get("/dashboard_registration_summary")
def dashboard_registration_summary(

    db: Session = Depends(get_db)

):

    total_participants = db.query(Participant).filter(

        Participant.is_archived == 0

    ).count()

    pending = db.query(Participant).filter(

        Participant.registration_status == "Pending",

        Participant.is_archived == 0

    ).count()

    completed = db.query(Participant).filter(

        Participant.registration_status == "Completed",

        Participant.is_archived == 0

    ).count()

    early_bird = db.query(Participant).filter(

        Participant.registration_phase == "Early-bird",

        Participant.is_archived == 0

    ).count()

    walk_in = db.query(Participant).filter(

        Participant.registration_phase == "Walk-in",

        Participant.is_archived == 0

    ).count()

    archived = db.query(Participant).filter(

        Participant.is_archived == 1

    ).count()

    return {

        "total_participants": total_participants,

        "pending_registration": pending,

        "completed_registration": completed,

        "early_bird": early_bird,

        "walk_in": walk_in,

        "archived_participants": archived

    }


# ======================================================
# EVENT SUMMARY DASHBOARD
# ======================================================  

@router.get("/dashboard_event_summary")
def dashboard_event_summary(

    db: Session = Depends(get_db)

):

    total_events = db.query(Event).filter(

        Event.is_archived == 0

    ).count()

    archived_events = db.query(Event).filter(

        Event.is_archived == 1

    ).count()

    today = datetime.date.today()

    active_events = db.query(Event).filter(

        Event.is_archived == 0,

        Event.registration_start <= today,

        Event.wrapup_date >= today

    ).count()

    upcoming_events = db.query(Event).filter(

        Event.is_archived == 0,

        Event.registration_start > today

    ).count()

    finished_events = db.query(Event).filter(

        Event.is_archived == 0,

        Event.wrapup_date < today

    ).count()

    return {

        "total_events": total_events,

        "active_events": active_events,

        "upcoming_events": upcoming_events,

        "finished_events": finished_events,

        "archived_events": archived_events

    }
    

# ======================================================
# DASHBOARD TOTALS
# ======================================================

@router.get("/dashboard_totals")
def dashboard_totals(
    db: Session = Depends(get_db)
):
    """
    Return live totals used by the Admin and Registration Team dashboards.
    Only non-archived records are included.
    """

    total_participants = db.query(Participant).filter(
        Participant.is_archived == 0
    ).count()

    total_staff = db.query(Staff).filter(
        Staff.is_archived == 0
    ).count()

    total_chaperones = db.query(Chaperone).filter(
        Chaperone.is_archived == 0
    ).count()

    total_events = db.query(Event).filter(
        Event.is_archived == 0
    ).count()

    return {
        "participants": total_participants,
        "staff": total_staff,
        "chaperones": total_chaperones,
        "events": total_events
    }


# ======================================================
# DASHBOARD OVERVIEW
# Everything the redesigned Admin / Registration Team
# dashboards show, in one request. Requires a login.
# ======================================================

def _full_name(*parts):
    return " ".join(
        str(part).strip()
        for part in parts
        if part and str(part).strip()
    )


def _month_start(value: datetime.date, months_back: int = 0):
    index = value.year * 12 + (value.month - 1) - months_back
    return datetime.date(index // 12, index % 12 + 1, 1)


@router.get("/dashboard_overview")
def dashboard_overview(
    request: Request,
    period: str = Query("6m", alias="range"),
    db: Session = Depends(get_db)
):
    session_user = request.session.get("user") or {}
    role = session_user.get("role")

    if role not in ("Admin", "Registration Team"):
        raise HTTPException(
            status_code=401,
            detail="Please log in to view the dashboard."
        )

    include_staff = role == "Admin"
    now = datetime.datetime.now()
    today = now.date()
    week_ago = now - datetime.timedelta(days=7)

    user = db.query(User).filter(
        User.id == session_user.get("user_id")
    ).first()

    events = db.query(Event).filter(
        Event.is_archived == 0
    ).all()

    event_names = {
        event.id: event.event_name
        for event in events
    }

    participants = db.query(Participant).filter(
        Participant.is_archived == 0
    ).all()

    chaperones = db.query(Chaperone).filter(
        Chaperone.is_archived == 0
    ).all()

    staff = db.query(Staff).filter(
        Staff.is_archived == 0
    ).all() if include_staff else []

    groups = {
        "participants": participants,
        "chaperones": chaperones,
    }

    if include_staff:
        groups["staff"] = staff

    # --------------------------------------------------
    # CARDS
    # --------------------------------------------------

    def created_since(rows, since):
        return sum(
            1 for row in rows
            if row.created_at and row.created_at >= since
        )

    cards = {
        key: {
            "total": len(rows),
            "this_week": created_since(rows, week_ago),
        }
        for key, rows in groups.items()
    }

    cards["events"] = {
        "total": len(events),
        "this_week": created_since(events, week_ago),
        "upcoming": sum(
            1 for event in events
            if event.kickoff_date and event.kickoff_date > today
        ),
    }

    # --------------------------------------------------
    # SERIES
    # --------------------------------------------------

    if period == "month":
        start = today.replace(day=1)
        days = (_month_start(today, -1) - start).days
        buckets = [
            start + datetime.timedelta(days=offset)
            for offset in range(days)
        ]
        labels = [str(day.day) for day in buckets]

        def bucket_of(value):
            day = value.date()
            return day if day >= start and day.month == start.month else None

    else:
        if period == "year":
            buckets = [
                datetime.date(today.year, month, 1)
                for month in range(1, 13)
            ]
        else:
            period = "6m"
            buckets = [
                _month_start(today, back)
                for back in reversed(range(6))
            ]

        labels = [day.strftime("%b") for day in buckets]

        def bucket_of(value):
            month = value.date().replace(day=1)
            return month if month in bucket_set else None

    bucket_set = set(buckets)

    series = {}

    for key, rows in groups.items():
        counts = dict.fromkeys(buckets, 0)
        for row in rows:
            if row.created_at:
                bucket = bucket_of(row.created_at)
                if bucket in counts:
                    counts[bucket] += 1
        series[key] = [counts[bucket] for bucket in buckets]

    # --------------------------------------------------
    # TOTALS
    # --------------------------------------------------

    total_registrations = sum(len(rows) for rows in groups.values())

    this_month = today.replace(day=1)
    last_month = _month_start(today, 1)

    registered_this_month = sum(
        1 for rows in groups.values() for row in rows
        if row.created_at and row.created_at.date() >= this_month
    )

    registered_last_month = sum(
        1 for rows in groups.values() for row in rows
        if row.created_at
        and last_month <= row.created_at.date() < this_month
    )

    change = (
        round(
            (registered_this_month - registered_last_month)
            / registered_last_month * 100
        )
        if registered_last_month
        else None
    )

    totals = {
        "total": total_registrations,
        "this_month": registered_this_month,
        "last_month": registered_last_month,
        "change_percent": change,
        "breakdown": {
            key: {
                "count": len(rows),
                "percent": (
                    round(len(rows) / total_registrations * 100)
                    if total_registrations else 0
                ),
            }
            for key, rows in groups.items()
        },
    }

    # --------------------------------------------------
    # RECENT REGISTRATIONS
    # --------------------------------------------------

    registrations = []

    for row in participants:
        registrations.append({
            "type": "participant",
            "id": row.id,
            "reference": row.registration_number,
            "name": _full_name(row.fname, row.mname, row.lname),
            "event_name": row.event_name or event_names.get(row.event_id),
            "status": row.registration_status or "Pending",
            "created_at": row.created_at,
        })

    for row in staff:
        registrations.append({
            "type": "staff",
            "id": row.id,
            "reference": None,
            "name": _full_name(row.fname, row.mname, row.lname),
            "event_name": event_names.get(row.event_id),
            "status": "Active",
            "created_at": row.created_at,
        })

    for row in chaperones:
        registrations.append({
            "type": "chaperone",
            "id": row.id,
            "reference": None,
            "name": _full_name(row.fname, row.mname, row.lname),
            "event_name": event_names.get(row.event_id),
            "status": "Active",
            "created_at": row.created_at,
        })

    oldest = datetime.datetime.min

    registrations.sort(
        key=lambda item: item["created_at"] or oldest,
        reverse=True
    )

    # --------------------------------------------------
    # RECENT ACTIVITY
    # --------------------------------------------------

    activity = [
        {
            "kind": item["type"],
            "title": {
                "participant": "New participant registered",
                "staff": "Staff member added",
                "chaperone": "Chaperone registered",
            }[item["type"]],
            "detail": _full_name(item["name"])
            + (" • " + item["event_name"] if item["event_name"] else ""),
            "at": item["created_at"],
        }
        for item in registrations[:10]
        if item["created_at"]
    ]

    for event in events:
        if event.created_at:
            activity.append({
                "kind": "event",
                "title": "Event created",
                "detail": event.event_name,
                "at": event.created_at,
            })

    payments = db.query(Payment).filter(
        Payment.status == "Paid",
        Payment.paid_at.isnot(None)
    ).order_by(
        Payment.paid_at.desc()
    ).limit(10).all()

    for payment in payments:
        amount = float(payment.amount or 0) / 100  # stored in centavos
        activity.append({
            "kind": "payment",
            "title": (
                "Store order paid"
                if payment.payment_type == "Store"
                else "Registration payment received"
            ),
            "detail": f"₱{amount:,.2f}"
            + (" • " + payment.paymongo_reference if payment.paymongo_reference else ""),
            "at": payment.paid_at,
        })

    donations = db.query(CashSponsorship).filter(
        CashSponsorship.payment_status == "Paid",
        CashSponsorship.paid_at.isnot(None)
    ).order_by(
        CashSponsorship.paid_at.desc()
    ).limit(10).all()

    for donation in donations:
        amount = float(donation.donation_amount or 0) / 100  # stored in centavos
        activity.append({
            "kind": "sponsor",
            "title": "Cash sponsorship received",
            "detail": f"₱{amount:,.2f}"
            + (" • " + donation.sponsor_name if donation.sponsor_name else ""),
            "at": donation.paid_at,
        })

    activity.sort(key=lambda item: item["at"], reverse=True)

    return {
        "now": now,
        "role": role,
        "user": {
            "username": session_user.get("username"),
            "fullname": (
                _full_name(user.fname, user.lname) if user else None
            ) or session_user.get("username"),
            "role": role,
        },
        "range": period,
        "cards": cards,
        "series": {
            "labels": labels,
            **series,
        },
        "totals": totals,
        "recent_registrations": registrations[:8],
        "activity": activity[:8],
        "events": [
            {
                "event_id": event.id,
                "event_name": event.event_name,
                "kickoff_date": event.kickoff_date,
            }
            for event in events
        ],
    }


# ======================================================
# ACTIVE EVENT PARTICIPANT COUNT
# ======================================================

@router.get("/event_participant_count")
def event_participant_count(

    db: Session = Depends(get_db)

):

    events = db.query(Event).filter(

        Event.is_archived == 0

    ).all()

    result = []

    for event in events:

        participant_count = db.query(Participant).filter(

            Participant.event_id == event.id,

            Participant.is_archived == 0

        ).count()

        result.append({

            "event_id": event.id,

            "event_name": event.event_name,

            "participant_count": participant_count

        })

    return {

        "events": result

    }    





























# ============================================================
# REPORT DASHBOARD DATA
# Add this endpoint to main(6).py
#
# Uses the existing models:
# Participant
# ParticipantEvaluation
# Staff
# Chaperone
# User
# StoreItem
# Payment
# CashSponsorship
# ItemSponsorship
# SponsorshipItem
# CashDonationTotal
# Event
# ============================================================

@router.get("/report_dashboard_data")
def report_dashboard_data(
    db: Session = Depends(get_db)
):

    today = datetime.date.today()

    # ========================================================
    # PARTICIPANTS
    # ========================================================

    participants_db = (
        db.query(Participant)
        .filter(
            Participant.is_archived == 0
        )
        .order_by(
            Participant.id.asc()
        )
        .all()
    )

    evaluations = (
        db.query(
            ParticipantEvaluation
        )
        .all()
    )

    evaluation_tier = {
        evaluation.participant_id:
            evaluation.participant_tier
        for evaluation in evaluations
    }

    participants = []

    for participant in participants_db:

        fullname = " ".join(
            part
            for part in [
                participant.fname,
                participant.mname,
                participant.lname
            ]
            if part
        ).strip()

        participants.append({
            "id": participant.id,
            "registration_number":
                participant.registration_number,
            "fullname": fullname,
            "sex": participant.sex,
            "age": participant.registration_age,
            "age_group": (
                "Under 13"
                if participant.registration_age < 13
                else "13-15"
                if participant.registration_age <= 15
                else "16-18"
                if participant.registration_age <= 18
                else "19-21"
                if participant.registration_age <= 21
                else "22-25"
                if participant.registration_age <= 25
                else "26+"
            ),
            "tier":
                evaluation_tier.get(
                    participant.id
                ),
            "sector":
                participant.sector,
            "participant_type":
                participant.participant_type,
            "registration_status":
                participant.registration_status,
            "event_id":
                participant.event_id,
            "event_name":
                participant.event_name
        })


    # ========================================================
    # STAFF
    # ========================================================

    staff_db = (
        db.query(Staff)
        .filter(
            Staff.is_archived == 0
        )
        .order_by(
            Staff.id.asc()
        )
        .all()
    )

    staff = []

    for member in staff_db:

        fullname = " ".join(
            part
            for part in [
                member.fname,
                member.mname,
                member.lname
            ]
            if part
        ).strip()

        profile_completed = bool(
            member.sex
            and member.birthday
            and member.contact
            and member.local_church
            and member.sector
        )

        event = (
            db.query(Event)
            .filter(
                Event.id == member.event_id
            )
            .first()
        )

        staff.append({
            "id": member.id,
            "event_id": member.event_id,
            "event_name":
                event.event_name
                if event
                else None,
            "fullname": fullname,
            "position": member.position,
            "sex": member.sex,
            "sector": member.sector,
            "local_church": member.local_church,
            "profile_completed":
                profile_completed
        })


    # ========================================================
    # CHAPERONES
    # ========================================================

    chaperones_db = (
        db.query(Chaperone)
        .filter(
            Chaperone.is_archived == 0
        )
        .order_by(
            Chaperone.id.asc()
        )
        .all()
    )

    chaperones = []

    for chaperone in chaperones_db:

        fullname = " ".join(
            part
            for part in [
                chaperone.fname,
                chaperone.mname,
                chaperone.lname
            ]
            if part
        ).strip()

        event = (
            db.query(Event)
            .filter(
                Event.id == chaperone.event_id
            )
            .first()
        )

        chaperones.append({
            "id": chaperone.id,
            "event_id": chaperone.event_id,
            "event_name":
                event.event_name
                if event
                else None,
            "fullname": fullname,
            "sex": chaperone.sex,
            "sector": chaperone.sector,
            "local_church":
                chaperone.local_church
        })


    # ========================================================
    # REGISTRATION TEAM ACCOUNTS
    # ========================================================

    users_db = (
        db.query(User)
        .filter(
            User.role == "Registration Team"
        )
        .order_by(
            User.id.asc()
        )
        .all()
    )

    team_accounts = []

    for user in users_db:

        fullname = " ".join(
            part
            for part in [
                user.fname,
                user.mname,
                user.lname
            ]
            if part
        ).strip()

        team_accounts.append({
            "id": user.id,
            "fullname": fullname,
            "username": user.username,
            "email": user.email,
            "sector": user.sector,
            "local_church":
                user.local_church
        })


    # ========================================================
    # STORE INVENTORY
    #
    # StoreItem.price is already PHP.
    # ========================================================

    store_items_db = (
        db.query(StoreItem)
        .filter(
            StoreItem.is_archived == 0
        )
        .order_by(
            StoreItem.id.asc()
        )
        .all()
    )

    store_items = [
        {
            "id": item.id,
            "item_name": item.item_name,
            "category": item.category,
            "quantity": item.quantity,
            "price": item.price
        }
        for item in store_items_db
    ]


    # ========================================================
    # STORE PURCHASES
    #
    # Payment.amount is stored in CENTAVOS.
    # Convert to PHP once.
    # ========================================================

    store_payments = (
        db.query(Payment)
        .filter(
            func.lower(
                Payment.payment_type
            ) == "store"
        )
        .order_by(
            Payment.id.desc()
        )
        .all()
    )

    store_item_map = {
        item.id: item
        for item in store_items_db
    }

    store_purchases = []

    for payment in store_payments:

        store_item = store_item_map.get(
            payment.store_item_id
        )

        quantity = int(
            payment.store_quantity or 1
        )

        amount_php = (
            float(payment.amount or 0)
            / 100
        )

        store_purchases.append({
            "id": payment.id,
            "store_item_id":
                payment.store_item_id,
            "item_name":
                store_item.item_name
                if store_item
                else "Unknown Item",
            "quantity": quantity,
            "amount": amount_php,
            "status":
                payment.status or "Pending",
            "customer_name":
                payment.customer_name,
            "customer_contact":
                payment.customer_contact,
            "customer_email":
                payment.customer_email,
            "created_at":
                payment.created_at,
            "paid_at":
                payment.paid_at
        })


    # ========================================================
    # CASH SPONSORS
    #
    # donation_amount is CENTAVOS.
    # ========================================================

    cash_sponsors_db = (
        db.query(CashSponsorship)
        .order_by(
            CashSponsorship.id.desc()
        )
        .all()
    )

    sponsors = []

    for sponsor in cash_sponsors_db:

        sponsors.append({
            "type": "Cash",
            "id": sponsor.id,
            "sponsor_name":
                sponsor.sponsor_name,
            "tier":
                sponsor.selected_tier,
            "item_name": None,
            "quantity": None,
            "amount":
                float(
                    sponsor.donation_amount or 0
                ) / 100,
            "status":
                sponsor.payment_status
                or "Pending",
            "sector":
                sponsor.sector,
            "created_at":
                sponsor.created_at,
            "paid_at":
                sponsor.paid_at
        })


    # ========================================================
    # ITEM SPONSORS
    # ========================================================

    item_sponsors_db = (
        db.query(ItemSponsorship)
        .order_by(
            ItemSponsorship.id.desc()
        )
        .all()
    )

    for sponsor in item_sponsors_db:

        sponsors.append({
            "type": "Item",
            "id": sponsor.id,
            "sponsor_name":
                sponsor.sponsor_name,
            "tier": None,
            "item_name":
                sponsor.item_name,
            "quantity":
                sponsor.quantity,
            "amount": None,
            "status":
                sponsor.status or "Confirmed",
            "sector":
                sponsor.sector,
            "created_at":
                sponsor.created_at,
            "paid_at": None
        })


    # ========================================================
    # SPONSORSHIP INVENTORY
    # ========================================================

    inventory_db = (
        db.query(SponsorshipItem)
        .filter(
            SponsorshipItem.is_active == True
        )
        .order_by(
            SponsorshipItem.id.asc()
        )
        .all()
    )

    sponsor_inventory = []

    for item in inventory_db:

        remaining = int(
            item.remaining_quantity or 0
        )

        sponsor_inventory.append({
            "id": item.id,
            "item_name":
                item.item_name,
            "description":
                item.description,
            "total_quantity":
                int(item.total_quantity or 0),
            "remaining_quantity":
                remaining,
            "unit":
                item.unit or "piece",
            "available":
                remaining > 0
        })


    # ========================================================
    # CASH DONATION FUND
    #
    # CashDonationTotal.total_amount is the CURRENT
    # REMAINING DONATION FUND and is already stored in PHP.
    #
    # IMPORTANT:
    # Do NOT calculate this from CashSponsorship.
    # Do NOT divide by 100.
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

    cash_donation_total = float(
        donation_total.total_amount
        if donation_total
        else 0
    )

    # The Sponsor Report's "Remaining Donation Fund"
    # must come directly from cash_donation_total.
    remaining_donation_fund = cash_donation_total


    # ========================================================
    # TOTAL CASH DONATIONS RECEIVED
    #
    # cash_total_added is already PESOS.
    #
    # Only positive values represent donations added to the
    # donation pool.
    # ========================================================

    total_cash_received = (
        db.query(
            func.coalesce(
                func.sum(
                    CashSponsorship.cash_total_added
                ),
                0
            )
        )
        .scalar()
        or 0
    )

    total_cash_received = float(
        total_cash_received
    )


    # ========================================================
    # FINDING SPONSOR PARTICIPANTS
    # ========================================================

    finding_sponsor_query = (
        db.query(Participant)
        .filter(
            Participant.is_archived == 0,
            func.lower(
                Participant.participant_type
            ) == "finding sponsor"
        )
    )

    finding_sponsor_participants = (
        finding_sponsor_query.count()
    )


    # ========================================================
    # SUCCESSFULLY SPONSORED PARTICIPANTS
    #
    # Finding Sponsor + T-shirt Paid + Lanyard Paid
    # ========================================================

    total_sponsored_participants = (
        db.query(Participant)
        .filter(
            Participant.is_archived == 0,

            func.lower(
                Participant.participant_type
            ) == "finding sponsor",

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
    # USED DONATION FUND
    #
    # This is the amount used from the donation pool based
    # on the difference between the total cash received and
    # the current remaining donation fund.
    # ========================================================

    total_used_donation_fund = max(
        0,
        total_cash_received -
        remaining_donation_fund
    )


    # ========================================================
    # SPONSOR COUNTS
    # ========================================================

    cash_sponsor_total = len(
        cash_sponsors_db
    )

    item_sponsor_total = len(
        item_sponsors_db
    )


    # ========================================================
    # EVENT REPORT
    # ========================================================

    events_db = (
        db.query(Event)
        .filter(
            Event.is_archived == 0
        )
        .order_by(
            Event.id.asc()
        )
        .all()
    )

    events = []

    for event in events_db:

        participant_count = (
            db.query(Participant)
            .filter(
                Participant.event_id == event.id,
                Participant.is_archived == 0
            )
            .count()
        )

        staff_count = (
            db.query(Staff)
            .filter(
                Staff.event_id == event.id,
                Staff.is_archived == 0
            )
            .count()
        )

        chaperone_count = (
            db.query(Chaperone)
            .filter(
                Chaperone.event_id == event.id,
                Chaperone.is_archived == 0
            )
            .count()
        )

        if today < event.registration_start:
            event_status = "Upcoming"

        elif (
            event.registration_start <= today
            and today <= event.registration_end
        ):
            event_status = "Registration Open"

        elif (
            event.kickoff_date <= today
            and today <= event.wrapup_date
        ):
            event_status = "Ongoing"

        elif today > event.wrapup_date:
            event_status = "Completed"

        else:
            event_status = "Upcoming"

        total_attendees = (
            participant_count
            + staff_count
            + chaperone_count
        )

        events.append({
            "id": event.id,
            "event_name":
                event.event_name,
            "registration_start":
                event.registration_start,
            "registration_end":
                event.registration_end,
            "kickoff_date":
                event.kickoff_date,
            "wrapup_date":
                event.wrapup_date,
            "status":
                event_status,
            "participants":
                participant_count,
            "staff":
                staff_count,
            "chaperones":
                chaperone_count,
            "total_attendees":
                total_attendees
        })


    # ========================================================
    # RESPONSE
    # ========================================================

    return {
        "success": True,

        "participants":
            participants,

        "staff":
            staff,

        "chaperones":
            chaperones,

        "team_accounts":
            team_accounts,

        "store_items":
            store_items,

        "store_purchases":
            store_purchases,

        "sponsors":
            sponsors,

        "sponsor_inventory":
            sponsor_inventory,

        "sponsor_stats": {

            # Directly from cash_donation_total
            "cash_donation_total":
                round(
                    cash_donation_total,
                    2
                ),

            "total_sponsored_participants":
                total_sponsored_participants,

            "total_used_donation_fund":
                round(
                    total_used_donation_fund,
                    2
                ),

            # IMPORTANT:
            # Remaining Donation Fund = CashDonationTotal.total_amount
            "remaining_donation_fund":
                round(
                    cash_donation_total,
                    2
                ),

            "finding_sponsor_participants":
                finding_sponsor_participants,

            "item_sponsor_total":
                item_sponsor_total,

            "cash_sponsor_total":
                cash_sponsor_total,

            "sponsor_inventory_total":
                len(
                    sponsor_inventory
                )
        },

        "events":
            events
    }
