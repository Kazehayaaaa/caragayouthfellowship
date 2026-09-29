"""Routes: events."""

from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session
import datetime
from fastapi import APIRouter

from app.database import (
    get_db,
)
from app.models import (
    Event,
    Participant,
)
from app.schemas import (
    EventCreateSchema,
    EventUpdateSchema,
)
from app.services.registration import (
    get_registration_phase,
)

router = APIRouter()

    




# ======================================================
# CREATE EVENT
# ======================================================

@router.post("/event_create_event")
def event_create_event(

    data: EventCreateSchema,

    db: Session = Depends(get_db)

):

    # ----------------------------------------
    # Allowed Event Types
    # ----------------------------------------

    allowed_events = [

        "Summer Youth Camp",

        "Youth Bible Conference"

    ]

    if data.event_name not in allowed_events:

        raise HTTPException(

            status_code=400,

            detail="Invalid event type."

        )

    # ----------------------------------------
    # Date Validations
    # ----------------------------------------

    if data.registration_start > data.registration_end:

        raise HTTPException(

            status_code=400,

            detail="Registration Start Date cannot be later than Registration End Date."

        )

    if data.registration_end > data.kickoff_date:

        raise HTTPException(

            status_code=400,

            detail="Registration End Date must be on or before the Kickoff Date."

        )

    if data.kickoff_date > data.wrapup_date:

        raise HTTPException(

            status_code=400,

            detail="Kickoff Date cannot be later than Wrap-up Date."

        )

    # ----------------------------------------
    # Duplicate Event Validation
    # ----------------------------------------

    duplicate = db.query(Event).filter(

        Event.event_name == data.event_name,

        Event.registration_start == data.registration_start,

        Event.registration_end == data.registration_end,

        Event.kickoff_date == data.kickoff_date,

        Event.wrapup_date == data.wrapup_date,

        Event.is_archived == 0

    ).first()

    if duplicate:

        raise HTTPException(

            status_code=400,

            detail="This active event already exists."

        )

    # ----------------------------------------
    # Create Event
    # ----------------------------------------

    new_event = Event(

        event_name=data.event_name,

        registration_start=data.registration_start,

        registration_end=data.registration_end,

        kickoff_date=data.kickoff_date,

        wrapup_date=data.wrapup_date,

        is_archived=0

    )

    db.add(new_event)

    db.commit()

    db.refresh(new_event)

    return {

        "message": "Event created successfully.",

        "event_id": new_event.id,

        "event_name": new_event.event_name,

        "registration_period": {

            "start": new_event.registration_start,

            "end": new_event.registration_end

        },

        "event_schedule": {

            "kickoff": new_event.kickoff_date,

            "wrapup": new_event.wrapup_date

        }

    }

# ======================================================
# VIEW ALL EVENTS
# ======================================================

@router.get("/event_view_all_events")
def event_view_all_events(

    db: Session = Depends(get_db)

):

    events = db.query(Event).filter(

        Event.is_archived == 0

    ).all()

    today = datetime.date.today()

    results = []

    for event in events:

        # ==========================================
        # PARTICIPANT COUNTS
        # ==========================================

        total_participants = db.query(Participant).filter(

            Participant.event_id == event.id,

            Participant.is_archived == 0

        ).count()

        early_bird = db.query(Participant).filter(

            Participant.event_id == event.id,

            Participant.registration_phase == "Early-bird",

            Participant.is_archived == 0

        ).count()

        walk_in = db.query(Participant).filter(

            Participant.event_id == event.id,

            Participant.registration_phase == "Walk-in",

            Participant.is_archived == 0

        ).count()

        completed = db.query(Participant).filter(

            Participant.event_id == event.id,

            Participant.registration_status == "Completed",

            Participant.is_archived == 0

        ).count()

        pending = db.query(Participant).filter(

            Participant.event_id == event.id,

            Participant.registration_status == "Pending",

            Participant.is_archived == 0

        ).count()

        # ==========================================
        # EVENT STATUS
        # ==========================================

        if today < event.registration_start:

            event_status = "Upcoming"

        elif event.registration_start <= today <= event.registration_end:

            event_status = "Registration Open"

        elif event.registration_end < today < event.kickoff_date:

            event_status = "Walk-in Registration"

        elif event.kickoff_date <= today <= event.wrapup_date:

            event_status = "Ongoing"

        else:

            event_status = "Finished"

        # ==========================================
        # REGISTRATION PHASE
        # ==========================================

        registration_phase = get_registration_phase(event)

        # ==========================================
        # APPEND RESULT
        # ==========================================

        results.append({

            "event_id": event.id,

            "event_name": event.event_name,

            "registration_start": event.registration_start,

            "registration_end": event.registration_end,

            "kickoff_date": event.kickoff_date,

            "wrapup_date": event.wrapup_date,

            "registration_phase": registration_phase,

            "event_status": event_status,

            "participants": {

                "total": total_participants,

                "early_bird": early_bird,

                "walk_in": walk_in,

                "completed": completed,

                "pending": pending

            },

            "is_archived": bool(event.is_archived)

        })

    return results



# ======================================================
# RESTORE ARCHIVED EVENT
# ======================================================

@router.put("/event_restore_event")
def event_restore_event(

    event_id: int,

    db: Session = Depends(get_db)

):

    event = db.query(Event).filter(

        Event.id == event_id,

        Event.is_archived == 1

    ).first()

    if not event:

        raise HTTPException(

            status_code=404,

            detail="Archived event not found."

        )

    duplicate = db.query(Event).filter(

        Event.event_name == event.event_name,

        Event.kickoff_date == event.kickoff_date,

        Event.is_archived == 0,

        Event.id != event.id

    ).first()

    if duplicate:

        raise HTTPException(

            status_code=400,

            detail="Another active event with the same name and kickoff date already exists."

        )

    event.is_archived = 0

    event.updated_at = datetime.datetime.now()

    db.commit()

    db.refresh(event)

    return {

        "message": "Event restored successfully.",

        "event_id": event.id,

        "event_name": event.event_name

    }


# ======================================================
# VIEW SINGLE EVENT
# ======================================================

@router.get("/event_view_single_event")
def event_view_single_event(

    event_id: int,

    db: Session = Depends(get_db)

):

    event = db.query(Event).filter(

        Event.id == event_id

    ).first()

    if not event:

        raise HTTPException(

            status_code=404,

            detail="Event not found."

        )

    total_participants = db.query(Participant).filter(

        Participant.event_id == event.id,

        Participant.is_archived == 0

    ).count()

    return {

        "event_id": event.id,

        "event_name": event.event_name,

        "registration_start": event.registration_start,

        "registration_end": event.registration_end,

        "kickoff_date": event.kickoff_date,

        "wrapup_date": event.wrapup_date,

        "registration_phase": get_registration_phase(event),

        "is_archived": bool(event.is_archived),

        "total_participants": total_participants,

        "created_at": event.created_at,

        "updated_at": event.updated_at

    }


# ======================================================
# VIEW CURRENT ACTIVE EVENT
# ======================================================

@router.get("/event_view_current_active_event")
def event_view_current_active_event(

    db: Session = Depends(get_db)

):

    today = datetime.date.today()

    event = db.query(Event).filter(

        Event.is_archived == 0,

        Event.registration_start <= today,

        Event.wrapup_date >= today

    ).order_by(

        Event.kickoff_date.asc()

    ).first()

    if not event:

        raise HTTPException(

            status_code=404,

            detail="No active event found."

        )

    total_participants = db.query(Participant).filter(

        Participant.event_id == event.id,

        Participant.is_archived == 0

    ).count()

    early_bird = db.query(Participant).filter(

        Participant.event_id == event.id,

        Participant.registration_phase == "Early-bird",

        Participant.is_archived == 0

    ).count()

    walk_in = db.query(Participant).filter(

        Participant.event_id == event.id,

        Participant.registration_phase == "Walk-in",

        Participant.is_archived == 0

    ).count()

    return {

        "event_id": event.id,

        "event_name": event.event_name,

        "registration_start": event.registration_start,

        "registration_end": event.registration_end,

        "kickoff_date": event.kickoff_date,

        "wrapup_date": event.wrapup_date,

        "registration_phase": get_registration_phase(event),

        "participants": {

            "total": total_participants,

            "early_bird": early_bird,

            "walk_in": walk_in

        }

    }

# ======================================================
# UPDATE EVENTS
# ======================================================


@router.put("/event_update_event")
def event_update_event(

    event_id: int,

    data: EventUpdateSchema,

    db: Session = Depends(get_db)

):

    event = db.query(Event).filter(

        Event.id == event_id,

        Event.is_archived == 0

    ).first()

    if not event:

        raise HTTPException(

            status_code=404,

            detail="Event not found."

        )

    allowed_events = [

        "Summer Youth Camp",

        "Youth Bible Conference"

    ]

    if data.event_name not in allowed_events:

        raise HTTPException(

            status_code=400,

            detail="Invalid event name."

        )

    if data.registration_start > data.registration_end:

        raise HTTPException(

            status_code=400,

            detail="Registration start cannot be later than registration end."

        )

    if data.registration_end > data.kickoff_date:

        raise HTTPException(

            status_code=400,

            detail="Registration must end on or before the Kickoff date."

        )

    if data.kickoff_date > data.wrapup_date:

        raise HTTPException(

            status_code=400,

            detail="Kickoff date cannot be later than Wrap-up date."

        )

    duplicate = db.query(Event).filter(

        Event.event_name == data.event_name,

        Event.kickoff_date == data.kickoff_date,

        Event.id != event_id,

        Event.is_archived == 0

    ).first()

    if duplicate:

        raise HTTPException(

            status_code=400,

            detail="Another active event with the same name and kickoff date already exists."

        )

    event.event_name = data.event_name

    event.registration_start = data.registration_start

    event.registration_end = data.registration_end

    event.kickoff_date = data.kickoff_date

    event.wrapup_date = data.wrapup_date

    event.updated_at = datetime.datetime.now()

    db.commit()

    return {

        "message":"Event updated successfully."

    }
    
    
# ======================================================
# DELETE EVENTS
# ======================================================    


@router.delete("/event_delete_event")
def event_delete_event(

    event_id: int,

    db: Session = Depends(get_db)

):

    # ======================================================
    # CHECK EVENT
    # ======================================================

    event = db.query(Event).filter(

        Event.id == event_id

    ).first()

    if not event:

        raise HTTPException(

            status_code=404,

            detail="Event not found."

        )

    # ======================================================
    # CHECK REGISTERED PARTICIPANTS
    # ======================================================

    participant = db.query(Participant).filter(

        Participant.event_id == event_id,

        Participant.is_archived == 0

    ).first()

    if participant:

        raise HTTPException(

            status_code=400,

            detail="This event cannot be deleted because it already has registered participants."

        )

    # ======================================================
    # DELETE EVENT
    # ======================================================

    db.delete(event)

    db.commit()

    return {

        "message": "Event deleted successfully."

    }


# ======================================================
# ARCHIVE EVENT
# ======================================================

@router.put("/event_archive_event")
def event_archive_event(

    event_id: int,

    db: Session = Depends(get_db)

):

    # ======================================================
    # CHECK EVENT
    # ======================================================

    event = db.query(Event).filter(

        Event.id == event_id,

        Event.is_archived == 0

    ).first()

    if not event:

        raise HTTPException(

            status_code=404,

            detail="Event not found."

        )

    # ======================================================
    # CHECK EVENT HAS ENDED
    # ======================================================

    today = datetime.date.today()

    if today <= event.wrapup_date:

        raise HTTPException(

            status_code=400,

            detail="This event cannot be archived until the event has ended."

        )

    # ======================================================
    # CHECK INCOMPLETE REGISTRATIONS
    # ======================================================

    incomplete_registration = db.query(Participant).filter(

        Participant.event_id == event.id,

        Participant.is_archived == 0,

        Participant.registration_status != "Completed"

    ).first()

    if incomplete_registration:

        raise HTTPException(

            status_code=400,

            detail="This event cannot be archived because there are participants with incomplete registrations."

        )

    # ======================================================
    # ARCHIVE EVENT
    # ======================================================

    event.is_archived = 1

    event.updated_at = datetime.datetime.now()

    db.commit()

    db.refresh(event)

    # ======================================================
    # RETURN RESULT
    # ======================================================

    return {

        "message": "Event archived successfully.",

        "event": {

            "event_id": event.id,

            "event_name": event.event_name,

            "registration_start": event.registration_start,

            "registration_end": event.registration_end,

            "kickoff_date": event.kickoff_date,

            "wrapup_date": event.wrapup_date,

            "is_archived": bool(event.is_archived),

            "archived_at": event.updated_at

        }

    }


# ======================================================
# VIEW ARCHIVE EVENT
# ======================================================  
    

@router.get("/event_view_archived_events")
def event_view_archived_events(

    db: Session = Depends(get_db)

):

    events = db.query(Event).filter(

        Event.is_archived == 1

    ).all()

    result = []

    for event in events:

        result.append({

            "id":event.id,

            "event_name":event.event_name,

            "kickoff_date":event.kickoff_date,

            "wrapup_date":event.wrapup_date

        })

    return result
