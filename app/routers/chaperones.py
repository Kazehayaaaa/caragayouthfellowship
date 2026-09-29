"""Routes: chaperones."""

from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session
from fastapi import APIRouter

from app.database import (
    get_db,
)
from app.models import (
    Chaperone,
    Event,
)
from app.schemas import (
    ChaperoneCreateSchema,
)

router = APIRouter()

    

# ======================================================
# REGISTER CHAPERONE
# ======================================================

@router.post("/register_chaperone")
def register_chaperone(
    data: ChaperoneCreateSchema,
    db: Session = Depends(get_db)
):

    # ======================================================
    # CHECK EVENT
    # ======================================================

    event = db.query(Event).filter(
        Event.id == data.event_id,
        Event.is_archived == 0
    ).first()

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found."
        )

    # ======================================================
    # DUPLICATE VALIDATION
    # ======================================================

    duplicate = db.query(Chaperone).filter(
        Chaperone.event_id == data.event_id,
        Chaperone.fname == data.fname,
        Chaperone.mname == data.mname,
        Chaperone.lname == data.lname,
        Chaperone.birthday == data.birthday,
        Chaperone.is_archived == 0
    ).first()

    if duplicate:
        raise HTTPException(
            status_code=400,
            detail="Chaperone is already registered for this event."
        )

    # ======================================================
    # CREATE CHAPERONE
    # ======================================================

    chaperone = Chaperone(
        event_id=event.id,

        fname=data.fname,
        mname=data.mname,
        lname=data.lname,

        sex=data.sex,
        birthday=data.birthday,
        contact=data.contact_number,
        local_church=data.local_church,
        sector=data.sector,

        is_archived=0
    )

    db.add(chaperone)
    db.commit()
    db.refresh(chaperone)

    # ======================================================
    # RESPONSE
    # ======================================================

    return {
        "message": "Chaperone registered successfully.",

        "chaperone": {
            "chaperone_id": chaperone.id,
            "event_id": chaperone.event_id,

            # Event name comes from Event table
            "event_name": event.event_name,

            "name": (
                f"{chaperone.fname} "
                f"{chaperone.mname or ''} "
                f"{chaperone.lname}"
            ).strip(),

            "sex": chaperone.sex,
            "birthday": chaperone.birthday,
            "contact": chaperone.contact,
            "local_church": chaperone.local_church,
            "sector": chaperone.sector
        }
    }


# ======================================================
# GET ALL CHAPERONES
# ======================================================

@router.get("/chaperones")
def get_all_chaperones(
    db: Session = Depends(get_db)
):

    chaperones = (
        db.query(Chaperone, Event)
        .join(
            Event,
            Chaperone.event_id == Event.id
        )
        .filter(
            Chaperone.is_archived == 0,
            Event.is_archived == 0
        )
        .order_by(
            Chaperone.id.desc()
        )
        .all()
    )

    result = []

    for chaperone, event in chaperones:

        result.append({
            "chaperone_id": chaperone.id,
            "event_id": chaperone.event_id,
            "event_name": event.event_name,

            "fname": chaperone.fname,
            "mname": chaperone.mname,
            "lname": chaperone.lname,

            "name": (
                f"{chaperone.fname} "
                f"{chaperone.mname or ''} "
                f"{chaperone.lname}"
            ).strip(),

            "sex": chaperone.sex,
            "birthday": chaperone.birthday,

            "contact": chaperone.contact,

            "local_church": chaperone.local_church,
            "sector": chaperone.sector,

            "is_archived": chaperone.is_archived,

            "created_at": chaperone.created_at,
            "updated_at": chaperone.updated_at
        })

    return {
        "message": "Chaperones retrieved successfully.",
        "count": len(result),
        "chaperones": result
    }


# ======================================================
# GET SINGLE CHAPERONE
# ======================================================

@router.get("/chaperone/{chaperone_id}")
def get_chaperone(
    chaperone_id: int,
    db: Session = Depends(get_db)
):

    result = (
        db.query(Chaperone, Event)
        .join(
            Event,
            Chaperone.event_id == Event.id
        )
        .filter(
            Chaperone.id == chaperone_id,
            Chaperone.is_archived == 0,
            Event.is_archived == 0
        )
        .first()
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Chaperone not found."
        )

    chaperone, event = result

    return {
        "message": "Chaperone retrieved successfully.",

        "chaperone": {
            "chaperone_id": chaperone.id,
            "event_id": chaperone.event_id,
            "event_name": event.event_name,

            "fname": chaperone.fname,
            "mname": chaperone.mname,
            "lname": chaperone.lname,

            "name": (
                f"{chaperone.fname} "
                f"{chaperone.mname or ''} "
                f"{chaperone.lname}"
            ).strip(),

            "sex": chaperone.sex,
            "birthday": chaperone.birthday,

            "contact": chaperone.contact,

            "local_church": chaperone.local_church,
            "sector": chaperone.sector,

            "is_archived": chaperone.is_archived,

            "created_at": chaperone.created_at,
            "updated_at": chaperone.updated_at
        }
    }


# ======================================================
# ARCHIVE CHAPERONE
# ======================================================

@router.put("/archive_chaperone/{chaperone_id}")
def archive_chaperone(
    chaperone_id: int,
    db: Session = Depends(get_db)
):

    chaperone = db.query(Chaperone).filter(
        Chaperone.id == chaperone_id,
        Chaperone.is_archived == 0
    ).first()

    if not chaperone:
        raise HTTPException(
            status_code=404,
            detail="Chaperone not found."
        )

    # ==================================================
    # ARCHIVE
    # ==================================================

    chaperone.is_archived = 1

    db.commit()
    db.refresh(chaperone)

    return {
        "message": "Chaperone archived successfully.",

        "chaperone": {
            "chaperone_id": chaperone.id,
            "event_id": chaperone.event_id,

            "name": (
                f"{chaperone.fname} "
                f"{chaperone.mname or ''} "
                f"{chaperone.lname}"
            ).strip(),

            "is_archived": chaperone.is_archived
        }
    }


@router.put("/update_chaperone/{chaperone_id}")
def update_chaperone(
    chaperone_id: int,
    data: ChaperoneCreateSchema,
    db: Session = Depends(get_db)
):

    # ==================================================
    # FIND CHAPERONE
    # ==================================================

    chaperone = db.query(Chaperone).filter(
        Chaperone.id == chaperone_id,
        Chaperone.is_archived == 0
    ).first()

    if not chaperone:
        raise HTTPException(
            status_code=404,
            detail="Chaperone not found."
        )

    # ==================================================
    # CHECK EVENT
    # ==================================================

    event = db.query(Event).filter(
        Event.id == data.event_id,
        Event.is_archived == 0
    ).first()

    if not event:
        raise HTTPException(
            status_code=404,
            detail=f"Event not found for event_id={data.event_id}."
        )

    # ==================================================
    # DUPLICATE VALIDATION
    # ==================================================

    duplicate = db.query(Chaperone).filter(
        Chaperone.id != chaperone_id,
        Chaperone.event_id == data.event_id,
        Chaperone.fname == data.fname,
        Chaperone.mname == data.mname,
        Chaperone.lname == data.lname,
        Chaperone.birthday == data.birthday,
        Chaperone.is_archived == 0
    ).first()

    if duplicate:
        raise HTTPException(
            status_code=400,
            detail=(
                "Another chaperone with the same "
                "information is already registered "
                "for this event."
            )
        )

    # ==================================================
    # UPDATE
    # ==================================================

    chaperone.event_id = data.event_id

    chaperone.fname = data.fname
    chaperone.mname = data.mname
    chaperone.lname = data.lname

    chaperone.sex = data.sex
    chaperone.birthday = data.birthday

    chaperone.contact = data.contact_number

    chaperone.local_church = data.local_church
    chaperone.sector = data.sector

    db.commit()
    db.refresh(chaperone)

    # ==================================================
    # RESPONSE
    # ==================================================

    return {
        "message": "Chaperone updated successfully.",
        "chaperone": {
            "chaperone_id": chaperone.id,
            "event_id": chaperone.event_id,
            "event_name": event.event_name,

            "fname": chaperone.fname,
            "mname": chaperone.mname,
            "lname": chaperone.lname,

            "name": (
                f"{chaperone.fname} "
                f"{chaperone.mname or ''} "
                f"{chaperone.lname}"
            ).strip(),

            "sex": chaperone.sex,
            "birthday": chaperone.birthday,
            "contact": chaperone.contact,
            "local_church": chaperone.local_church,
            "sector": chaperone.sector,

            "is_archived": chaperone.is_archived,
            "created_at": chaperone.created_at,
            "updated_at": chaperone.updated_at
        }
    }
