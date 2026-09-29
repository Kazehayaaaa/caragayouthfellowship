"""Routes: staff."""

from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session
import datetime
from sqlalchemy import func
from fastapi import APIRouter

from app.database import (
    get_db,
)
from app.models import (
    Event,
    Staff,
)
from app.schemas import (
    StaffCreateSchema,
    StaffUpdateSchema,
)

router = APIRouter()

# ======================================================
# REGISTER STAFF
# ======================================================

@router.post("/register_staff")
def register_staff(
    data: StaffCreateSchema,
    db: Session = Depends(get_db)
):

    event = db.query(Event).filter(
        Event.id == data.event_id,
        Event.is_archived == 0
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    duplicate = db.query(Staff).filter(
        Staff.event_id == data.event_id,
        func.lower(Staff.fname) == data.fname.strip().lower(),
        func.lower(Staff.lname) == data.lname.strip().lower(),
        Staff.is_archived == 0
    ).first()

    if duplicate:
        raise HTTPException(status_code=400, detail="A staff member with the same name is already registered for this event.")

    staff = Staff(
        event_id=event.id,
        fname=data.fname.strip(),
        mname=(data.mname or "").strip(),
        lname=data.lname.strip(),
        position=data.position.strip(),
        sex=data.sex,
        birthday=data.birthday,
        contact=data.contact_number,
        local_church=data.local_church,
        sector=data.sector,
        is_archived=0
    )

    db.add(staff)
    db.commit()
    db.refresh(staff)

    return {
        "message": "Staff placeholder created successfully. The staff member can complete their profile later.",
        "staff": {
            "staff_id": staff.id,
            "event_id": staff.event_id,
            "event_name": event.event_name,
            "name": f"{staff.fname} {staff.mname} {staff.lname}".strip(),
            "position": staff.position,
            "profile_completed": bool(staff.sex and staff.birthday and staff.contact and staff.local_church and staff.sector)
        }
    }


@router.get("/register_view_all_staff")
def register_view_all_staff(
    event_id: int,
    db: Session = Depends(get_db)
):

    staff_members = db.query(Staff).filter(
        Staff.event_id == event_id,
        Staff.is_archived == 0
    ).all()

    event = db.query(Event).filter(
        Event.id == event_id,
        Event.is_archived == 0
    ).first()

    event_name = event.event_name if event else None

    return [
        {
            "staff_id": staff.id,
            "event_id": staff.event_id,
            "event_name": event_name,
            "fname": staff.fname,
            "mname": staff.mname,
            "lname": staff.lname,
            "position": staff.position,
            "sex": staff.sex,
            "birthday": staff.birthday,
            "contact": staff.contact,
            "local_church": staff.local_church,
            "sector": staff.sector
        }
        for staff in staff_members
    ]


@router.get("/register_view_staff/{staff_id}")
def register_view_staff(
    staff_id: int,
    db: Session = Depends(get_db)
):

    staff = db.query(Staff).filter(
        Staff.id == staff_id,
        Staff.is_archived == 0
    ).first()

    if not staff:
        raise HTTPException(
            status_code=404,
            detail="Staff member not found."
        )

    event = db.query(Event).filter(
        Event.id == staff.event_id,
        Event.is_archived == 0
    ).first()

    return {
        "staff_id": staff.id,
        "event_id": staff.event_id,
        "event_name": event.event_name if event else None,
        "fname": staff.fname,
        "mname": staff.mname,
        "lname": staff.lname,
        "position": staff.position,
        "sex": staff.sex,
        "birthday": staff.birthday,
        "contact": staff.contact,
        "local_church": staff.local_church,
        "sector": staff.sector
    }


# ======================================================
# UPDATE STAFF
# ======================================================

@router.put("/register_update_staff/{staff_id}")
def register_update_staff(
    staff_id: int,
    data: StaffUpdateSchema,
    db: Session = Depends(get_db)
):

    staff = db.query(Staff).filter(
        Staff.id == staff_id,
        Staff.is_archived == 0
    ).first()

    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found.")

    duplicate = db.query(Staff).filter(
        Staff.event_id == staff.event_id,
        func.lower(Staff.fname) == data.fname.strip().lower(),
        func.lower(Staff.lname) == data.lname.strip().lower(),
        Staff.id != staff_id,
        Staff.is_archived == 0
    ).first()

    if duplicate:
        raise HTTPException(status_code=400, detail="Another staff member with the same name already exists for this event.")

    staff.fname = data.fname.strip()
    staff.mname = (data.mname or "").strip()
    staff.lname = data.lname.strip()
    staff.position = data.position.strip()
    staff.sex = data.sex
    staff.birthday = data.birthday
    # IMPORTANT
    staff.contact = data.contact_number

    staff.local_church = data.local_church
    staff.sector = data.sector
    staff.updated_at = datetime.datetime.now()

    db.commit()
    db.refresh(staff)

    event = db.query(Event).filter(Event.id == staff.event_id).first()

    return {
        "message": "Staff member updated successfully.",
        "staff_id": staff.id,
        "event_id": staff.event_id,
        "event_name": event.event_name if event else None,
        "position": staff.position,
        "profile_completed": bool(staff.sex and staff.birthday and staff.contact and staff.local_church and staff.sector)
    }


# ======================================================
# FIND STAFF BY FULL NAME
# ======================================================

@router.get("/register_find_staff")
def register_find_staff(
    event_id: int,
    name: str,
    db: Session = Depends(get_db)
):
    """Find an active staff placeholder by exact full name for profile completion."""
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.is_archived == 0
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    target = " ".join(name.split()).casefold()
    staff_members = db.query(Staff).filter(
        Staff.event_id == event_id,
        Staff.is_archived == 0
    ).all()

    matches = []
    for staff in staff_members:
        fullname = " ".join(f"{staff.fname} {staff.mname or ''} {staff.lname}".split())
        if fullname.casefold() == target:
            matches.append({
                "staff_id": staff.id,
                "event_id": staff.event_id,
                "event_name": event.event_name,
                "fname": staff.fname,
                "mname": staff.mname,
                "lname": staff.lname,
                "fullname": fullname,
                "position": staff.position,
                "sex": staff.sex,
                "birthday": staff.birthday,
                "contact": staff.contact,
                "local_church": staff.local_church,
                "sector": staff.sector,
                "profile_completed": bool(staff.sex and staff.birthday and staff.contact and staff.local_church and staff.sector)
            })

    if not matches:
        raise HTTPException(status_code=404, detail="No staff record matches that full name.")

    return matches


# ======================================================
# ARCHIVE STAFF
# ======================================================

@router.put("/register_archive_staff/{staff_id}")
def register_archive_staff(

    staff_id: int,

    db: Session = Depends(get_db)

):

    staff = db.query(Staff).filter(

        Staff.id == staff_id,

        Staff.is_archived == 0

    ).first()

    if not staff:

        raise HTTPException(

            status_code=404,

            detail="Staff member not found."

        )

    staff.is_archived = 1

    staff.updated_at = datetime.datetime.now()

    db.commit()

    return {

        "message": "Staff member archived successfully.",

        "staff_id": staff.id

    }


# ======================================================
# VIEW ARCHIVED STAFF
# ======================================================

@router.get("/register_view_archived_staff")
def register_view_archived_staff(

    event_id: int,

    db: Session = Depends(get_db)

):

    staff_members = db.query(Staff).filter(
        Staff.event_id == event_id,
        Staff.is_archived == 1
    ).all()

    event = db.query(Event).filter(Event.id == event_id).first()

    return [

        {

            "staff_id": staff.id,

            "event_id": staff.event_id,

            "event_name": event.event_name if event else None,

            "name": f"{staff.fname} {staff.mname} {staff.lname}".strip(),

            "position": staff.position,

            "sex": staff.sex,

            "birthday": staff.birthday,

            "contact": staff.contact,

            "local_church": staff.local_church,

            "sector": staff.sector

        }

        for staff in staff_members

    ]
