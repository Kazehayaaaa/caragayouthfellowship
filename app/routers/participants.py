"""Routes: participants."""

from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session
import base64
import datetime
import io
import qrcode
from fastapi import APIRouter

from app.database import (
    get_db,
)
from app.models import (
    Event,
    EventRulesAgreement,
    Participant,
    ParticipantEvaluation,
    Questionnaire,
    RegistrationItem,
)
from app.schemas import (
    OnlineRegistrationSchema,
    ParticipantCreateSchema,
    ParticipantUpdateSchema,
)
from app.services.registration import (
    calculate_registration_age,
    creative_identifier,
    influence_score_calculator,
    registration_duplicate_validation,
    registration_number_generator,
    registration_phase_validation,
    registration_rules_validation,
    spiritual_score_calculator,
    tier_assignment,
)

router = APIRouter()

# ======================================================
# CREATE PARTICIPANT
# ======================================================  


@router.post("/registration_create_participant")
def registration_create_participant(

    data: ParticipantCreateSchema,

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
    # CHECK PARTICIPANT TYPE
    # ======================================================

    allowed_participant_types = [

        "Regular Participants",

        "Finding Sponsor"

    ]

    if data.participant_type not in allowed_participant_types:

        raise HTTPException(

            status_code=400,

            detail="Invalid participant type. Choose either Regular Participants or Finding Sponsor."

        )

    # ======================================================
    # CHECK REGISTRATION PERIOD
    # ======================================================

    today = datetime.date.today()

    if today < event.registration_start:

        raise HTTPException(

            status_code=400,

            detail="Event registration has not started yet."

        )

    # ======================================================
    # CHECK EVENT KICKOFF
    # ======================================================

    if today > event.kickoff_date:

        raise HTTPException(

            status_code=400,

            detail="Registration is already closed because the event has started."

        )

    # ======================================================
    # DUPLICATE VALIDATION
    # ======================================================

    duplicate = registration_duplicate_validation(

        db,

        data.event_id,

        data.fname,

        data.mname,

        data.lname,

        data.birthdate

    )

    if duplicate:

        raise HTTPException(

            status_code=400,

            detail="Participant is already registered for this event."

        )

    # ======================================================
    # REGISTRATION PHASE
    # ======================================================

    registration_phase = registration_phase_validation(

        event

    )

    # ======================================================
    # CALCULATE REGISTRATION AGE
    # ======================================================

    registration_age = calculate_registration_age(

        data.birthdate

    )

    # ======================================================
    # GENERATE REGISTRATION NUMBER
    # ======================================================

    registration_number = registration_number_generator(

        db,

        event

    )

    # ======================================================
    # CREATE PARTICIPANT
    # ======================================================

    participant = Participant(

        # -----------------------------
        # Event Reference
        # -----------------------------

        event_id=event.id,

        # -----------------------------
        # Event Snapshot
        # -----------------------------

        event_name=event.event_name,

        registration_start=event.registration_start,

        registration_end=event.registration_end,

        kickoff_date=event.kickoff_date,

        wrapup_date=event.wrapup_date,

        # -----------------------------
        # Registration Information
        # -----------------------------

        registration_number=registration_number,

        registration_date=today,

        registration_phase=registration_phase,

        registration_status="Pending",

        participant_type=data.participant_type,

        registration_age=registration_age,

        # -----------------------------
        # Participant Information
        # -----------------------------

        fname=data.fname,

        mname=data.mname,

        lname=data.lname,

        sex=data.sex,

        birthdate=data.birthdate,

        address=data.address,

        contact_number=data.contact_number,

        emergency_contact=data.emergency_contact,

        email=data.email,

        local_church=data.local_church,

        sector=data.sector

    )

    # ======================================================
    # SAVE PARTICIPANT
    # ======================================================

    db.add(participant)

    db.commit()

    db.refresh(participant)

    # ======================================================
    # RESPONSE
    # ======================================================

    return {

        "message": "Participant registered successfully.",

        "participant": {

            "participant_id": participant.id,

            "registration_number": participant.registration_number,

            "participant_type": participant.participant_type,

            "registration_phase": participant.registration_phase,

            "registration_status": participant.registration_status,

            "registration_age": participant.registration_age

        },

        "event": {

            "event_id": participant.event_id,

            "event_name": participant.event_name,

            "registration_start": participant.registration_start,

            "registration_end": participant.registration_end,

            "kickoff_date": participant.kickoff_date,

            "wrapup_date": participant.wrapup_date

        }

    }











# ======================================================
# SEARCH PARTICIPANT
# ======================================================

@router.get("/registration_search_participant")
def registration_search_participant(
    keyword: str,
    db: Session = Depends(get_db)
):

    # ==================================================
    # CLEAN SEARCH KEYWORD
    # ==================================================

    keyword = (keyword or "").strip().lower()

    # ==================================================
    # PREVENT SINGLE-LETTER SEARCH
    # ==================================================

    if len(keyword) < 2:
        return []

    # ==================================================
    # GET ACTIVE PARTICIPANTS
    # ==================================================

    participants = db.query(Participant).filter(
        Participant.is_archived == 0
    ).all()

    result = []

    for participant in participants:

        # ==================================================
        # FULL NAME
        # ==================================================

        fullname = " ".join(
            part for part in [
                participant.fname,
                participant.mname,
                participant.lname
            ]
            if part
        ).strip()

        fullname_lower = fullname.lower()

        # ==================================================
        # REGISTRATION NUMBER
        # ==================================================

        registration_number = str(
            participant.registration_number or ""
        ).strip()

        registration_number_lower = (
            registration_number.lower()
        )

        # ==================================================
        # EVENT NAME
        # ==================================================

        event_name = str(
            participant.event_name or ""
        ).strip()

        event_name_lower = event_name.lower()

        # ==================================================
        # SEARCHABLE VALUES
        # ==================================================

        searchable_values = [
            fullname_lower,
            event_name_lower,
            registration_number_lower
        ]

        # ==================================================
        # MATCH SEARCH
        # ==================================================

        matched = any(
            keyword in value
            for value in searchable_values
        )

        if not matched:
            continue

        # ==================================================
        # PARTICIPANT TYPE
        # ==================================================

        participant_type = str(
            participant.participant_type or ""
        ).strip()

        is_sponsor_participant = (
            participant_type.lower()
            == "finding sponsor"
        )

        # ==================================================
        # PAYMENT STATUS
        # ==================================================

        tshirt_status = str(
            participant.tshirt_status or "Unpaid"
        )

        lanyard_status = str(
            participant.lanyard_status or "Unpaid"
        )

        tshirt_status_lower = (
            tshirt_status.lower()
        )

        lanyard_status_lower = (
            lanyard_status.lower()
        )

        if (
            tshirt_status_lower == "paid"
            and
            lanyard_status_lower == "paid"
        ):

            payment_status = "Paid"

        elif (
            tshirt_status_lower == "paid"
            or
            lanyard_status_lower == "paid"
        ):

            payment_status = "Partial"

        else:

            payment_status = "Unpaid"

        # ==================================================
        # SPONSORSHIP STATUS
        # ==================================================

        if is_sponsor_participant:

            sponsorship_status = (
                "Sponsored in Review"
            )

            if (
                tshirt_status_lower == "paid"
                and
                lanyard_status_lower == "paid"
            ):

                merchandise_status = (
                    "Sponsored Confirmed"
                )

            elif (
                tshirt_status_lower == "paid"
                or
                lanyard_status_lower == "paid"
            ):

                merchandise_status = (
                    "Sponsored - Partial"
                )

            else:

                merchandise_status = (
                    "Sponsored in Review"
                )

            payment_status = (
                sponsorship_status
            )

        else:

            sponsorship_status = None
            merchandise_status = payment_status

        # ==================================================
        # PARTICIPANT TIER / EVALUATION
        # ==================================================

        evaluation = db.query(
            ParticipantEvaluation
        ).filter(
            ParticipantEvaluation.participant_id
            == participant.id
        ).first()

        participant_tier = (
            evaluation.participant_tier
            if evaluation
            else None
        )

        # ==================================================
        # GENERATE QR CODE
        #
        # QR CONTENT:
        # REGISTRATION NUMBER ONLY
        #
        # Example:
        # CYF-2026-000123
        # ==================================================

        qr_code_base64 = None

        if registration_number:

            try:

                qr = qrcode.QRCode(
                    version=None,
                    error_correction=qrcode.constants.ERROR_CORRECT_M,
                    box_size=10,
                    border=4
                )

                qr.add_data(
                    registration_number
                )

                qr.make(
                    fit=True
                )

                qr_image = qr.make_image(
                    fill_color="black",
                    back_color="white"
                )

                qr_buffer = io.BytesIO()

                qr_image.save(
                    qr_buffer,
                    format="PNG"
                )

                qr_buffer.seek(0)

                qr_code_base64 = (
                    "data:image/png;base64,"
                    +
                    base64.b64encode(
                        qr_buffer.getvalue()
                    ).decode("utf-8")
                )

            except Exception as e:

                print(
                    "QR CODE GENERATION ERROR:",
                    repr(e)
                )

                qr_code_base64 = None

        # ==================================================
        # RESULT
        # ==================================================

        result.append({

            # ----------------------------------------------
            # PARTICIPANT
            # ----------------------------------------------

            "participant_id":
                participant.id,

            "registration_number":
                registration_number,

            "fullname":
                fullname,

            # ----------------------------------------------
            # QR CODE
            # ----------------------------------------------

            "qr_code":
                qr_code_base64,

            "qr_code_filename":
                (
                    f"{registration_number}-QR.png"
                    if registration_number
                    else
                    f"participant-{participant.id}-QR.png"
                ),

            # ----------------------------------------------
            # EVENT
            # ----------------------------------------------

            "event_name":
                participant.event_name,

            # ----------------------------------------------
            # PARTICIPANT TYPE
            # ----------------------------------------------

            "participant_type":
                participant_type,

            "is_sponsor_participant":
                is_sponsor_participant,

            # ----------------------------------------------
            # REGISTRATION
            # ----------------------------------------------

            "registration_phase":
                participant.registration_phase,

            "registration_status":
                participant.registration_status,

            # ----------------------------------------------
            # PAYMENT
            # ----------------------------------------------

            "payment_status":
                payment_status,

            # ----------------------------------------------
            # SPONSORSHIP
            # ----------------------------------------------

            "sponsorship_status":
                sponsorship_status,

            # ----------------------------------------------
            # MERCHANDISE
            # ----------------------------------------------

            "merchandise_status":
                merchandise_status,

            "tshirt_status":
                participant.tshirt_status or "Unpaid",

            "lanyard_status":
                participant.lanyard_status or "Unpaid",

            # ----------------------------------------------
            # EVALUATION
            # ----------------------------------------------

            "participant_tier":
                participant_tier
        })

    return result











# ======================================================
# FILTER REGISTRATION PHASE
# ======================================================  

@router.get("/registration_filter_registration_phase")
def registration_filter_registration_phase(

    registration_phase: str,

    db: Session = Depends(get_db)

):

    participants = db.query(Participant).filter(

        Participant.registration_phase == registration_phase,

        Participant.is_archived == 0

    ).all()

    return participants


# ======================================================
# FILTER REGISTRATION STATUS
# ======================================================  

@router.get("/registration_filter_registration_status")
def registration_filter_registration_status(

    registration_status: str,

    db: Session = Depends(get_db)

):

    participants = db.query(Participant).filter(

        Participant.registration_status == registration_status,

        Participant.is_archived == 0

    ).all()

    return participants

# ======================================================
# FILTER PARTICIPANTS BY EVENT
# ======================================================  

@router.get("/registration_filter_event")
def registration_filter_event(

    event_id: int,

    db: Session = Depends(get_db)

):

    participants = db.query(Participant).filter(

        Participant.event_id == event_id,

        Participant.is_archived == 0

    ).all()

    return participants

# ======================================================
# FILTER PARTICIPANT TIER
# ======================================================  

@router.get("/registration_filter_participant_tier")
def registration_filter_participant_tier(

    participant_tier: str,

    db: Session = Depends(get_db)

):

    evaluations = db.query(

        ParticipantEvaluation

    ).filter(

        ParticipantEvaluation.participant_tier == participant_tier

    ).all()

    result = []

    for evaluation in evaluations:

        participant = db.query(Participant).filter(

            Participant.id == evaluation.participant_id,

            Participant.is_archived == 0

        ).first()

        if participant:

            result.append({

                "participant_id": participant.id,

                "registration_number": participant.registration_number,

                "fullname": f"{participant.fname} {participant.mname} {participant.lname}",

                "event_name": participant.event_name,

                "participant_tier": evaluation.participant_tier,

                "spiritual_score": evaluation.spiritual_score,

                "influence_score": evaluation.influence_score

            })

    return result
    
# ======================================================
# VIEW ALL PARTICIPANTS
# ======================================================  

@router.get("/registration_view_all_participants")
def registration_view_all_participants(

    db: Session = Depends(get_db)

):

    participants = db.query(Participant).filter(

        Participant.is_archived == 0

    ).all()

    return participants


# ======================================================
# VIEW PARTICIPANT DETAILS
# ======================================================  

@router.get("/registration_view_participant_details/{participant_id}")
def registration_view_participant_details(

    participant_id: int,

    db: Session = Depends(get_db)

):

    participant = db.query(Participant).filter(

        Participant.id == participant_id,

        Participant.is_archived == 0

    ).first()

    if not participant:

        raise HTTPException(

            status_code=404,

            detail="Participant not found."

        )

    return participant


# ======================================================
# UPDATE PARTICIPANT
# ======================================================

@router.put("/registration_update_participant/{participant_id}")
def registration_update_participant(

    participant_id: int,

    data: ParticipantUpdateSchema,

    db: Session = Depends(get_db)

):

    # ======================================================
    # CHECK PARTICIPANT
    # ======================================================

    participant = db.query(Participant).filter(

        Participant.id == participant_id,

        Participant.is_archived == 0

    ).first()

    if not participant:

        raise HTTPException(

            status_code=404,

            detail="Participant not found."

        )

    # ======================================================
    # CHECK PARTICIPANT TYPE
    # ======================================================

    allowed_participant_types = [

        "Regular Participants",

        "Finding Sponsor"

    ]

    if data.participant_type not in allowed_participant_types:

        raise HTTPException(

            status_code=400,

            detail="Invalid participant type. Choose either Regular Participants or Finding Sponsor."

        )

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

    duplicate = db.query(Participant).filter(

        Participant.event_id == data.event_id,

        Participant.fname == data.fname,

        Participant.mname == data.mname,

        Participant.lname == data.lname,

        Participant.birthdate == data.birthdate,

        Participant.id != participant_id,

        Participant.is_archived == 0

    ).first()

    if duplicate:

        raise HTTPException(

            status_code=400,

            detail="Another participant with the same name and birthdate is already registered for this event."

        )

    # ======================================================
    # UPDATE EVENT REFERENCE
    # ======================================================

    participant.event_id = event.id

    # ======================================================
    # UPDATE EVENT SNAPSHOT
    # ======================================================

    participant.event_name = event.event_name

    participant.registration_start = event.registration_start

    participant.registration_end = event.registration_end

    participant.kickoff_date = event.kickoff_date

    participant.wrapup_date = event.wrapup_date

    # ======================================================
    # UPDATE PARTICIPANT TYPE
    # ======================================================

    participant.participant_type = data.participant_type

    # ======================================================
    # UPDATE PARTICIPANT INFORMATION
    # ======================================================

    participant.fname = data.fname

    participant.mname = data.mname

    participant.lname = data.lname

    participant.sex = data.sex

    participant.birthdate = data.birthdate

    participant.registration_age = calculate_registration_age(

        data.birthdate

    )

    participant.address = data.address

    participant.contact_number = data.contact_number

    participant.emergency_contact = data.emergency_contact

    participant.email = data.email

    participant.local_church = data.local_church

    participant.sector = data.sector

    # ======================================================
    # UPDATE TIMESTAMP
    # ======================================================

    participant.updated_at = datetime.datetime.now()

    # ======================================================
    # SAVE CHANGES
    # ======================================================

    db.commit()

    db.refresh(participant)

    # ======================================================
    # RESPONSE
    # ======================================================

    return {

        "message": "Participant updated successfully.",

        "participant": {

            "participant_id": participant.id,

            "registration_number": participant.registration_number,

            "participant_type": participant.participant_type,

            "registration_age": participant.registration_age,

            "registration_phase": participant.registration_phase,

            "registration_status": participant.registration_status

        },

        "event": {

            "event_id": participant.event_id,

            "event_name": participant.event_name,

            "registration_start": participant.registration_start,

            "registration_end": participant.registration_end,

            "kickoff_date": participant.kickoff_date,

            "wrapup_date": participant.wrapup_date

        }

    }
    

# ======================================================
# ARCHIVE PARTICIPANT
# ======================================================  


@router.put("/registration_archive_participant/{participant_id}")
def registration_archive_participant(

    participant_id: int,

    db: Session = Depends(get_db)

):

    participant = db.query(Participant).filter(

        Participant.id == participant_id,

        Participant.is_archived == 0

    ).first()

    if not participant:

        raise HTTPException(

            status_code=404,

            detail="Participant not found."

        )

    participant.is_archived = 1

    participant.updated_at = datetime.datetime.now()

    db.commit()

    return {

        "message":"Participant archived successfully."

    }
    



# ======================================================
# RESTORE PARTICIPANT
# ======================================================  

@router.put("/registration_restore_participant/{participant_id}")
def registration_restore_participant(

    participant_id: int,

    db: Session = Depends(get_db)

):

    participant = db.query(Participant).filter(

        Participant.id == participant_id,

        Participant.is_archived == 1

    ).first()

    if not participant:

        raise HTTPException(

            status_code=404,

            detail="Archived participant not found."

        )

    participant.is_archived = 0

    participant.updated_at = datetime.datetime.now()

    db.commit()

    return {

        "message":"Participant restored successfully."

    }

# ======================================================
# VIEW ARCHIVED PARTICIPANTS
# ======================================================      

@router.get("/registration_view_archived_participants")
def registration_view_archived_participants(

    db: Session = Depends(get_db)

):

    participants = db.query(Participant).filter(

        Participant.is_archived == 1

    ).all()

    return participants
    
    
# ======================================================
# COMPLETE REGISTRATION VALIDATION
# ======================================================

@router.post("/registration_complete_registration")
def registration_complete_registration(

    participant_id: int,

    db: Session = Depends(get_db)

):

    # ======================================================
    # CHECK PARTICIPANT
    # ======================================================

    participant = db.query(Participant).filter(

        Participant.id == participant_id,

        Participant.is_archived == 0

    ).first()

    if not participant:

        raise HTTPException(

            status_code=404,

            detail="Participant not found."

        )

    # ======================================================
    # PREVENT DUPLICATE COMPLETION
    # ======================================================

    if participant.registration_status == "Completed":

        raise HTTPException(

            status_code=400,

            detail="Participant registration is already completed."

        )

    # ======================================================
    # CHECK QUESTIONNAIRE
    # ======================================================

    questionnaire = db.query(Questionnaire).filter(

        Questionnaire.participant_id == participant_id

    ).first()

    if not questionnaire:

        raise HTTPException(

            status_code=400,

            detail="Questionnaire has not been completed."

        )

    # ======================================================
    # CHECK RULES AGREEMENT
    # ======================================================

    agreement = registration_rules_validation(

        db,

        participant_id

    )

    if not agreement:

        raise HTTPException(

            status_code=400,

            detail="Participant must accept the Event Rules & Regulations."

        )

    # ======================================================
    # GET EVENT
    # ======================================================

    event = db.query(Event).filter(

        Event.id == participant.event_id,

        Event.is_archived == 0

    ).first()

    if not event:

        raise HTTPException(

            status_code=404,

            detail="Event not found."

        )

    # ======================================================
    # CALCULATE SCORES
    # ======================================================

    influence_score = influence_score_calculator(

        questionnaire

    )

    spiritual_score = spiritual_score_calculator(

        questionnaire

    )

    creative_status = creative_identifier(

        questionnaire

    )

    participant_tier = tier_assignment(

        influence_score,

        spiritual_score,

        creative_status

    )

    # ======================================================
    # SAVE / UPDATE EVALUATION
    # ======================================================

    evaluation = db.query(ParticipantEvaluation).filter(

        ParticipantEvaluation.participant_id == participant_id

    ).first()

    if evaluation:

        evaluation.influence_score = influence_score

        evaluation.spiritual_score = spiritual_score

        evaluation.creative_status = creative_status

        evaluation.participant_tier = participant_tier

        evaluation.updated_at = datetime.datetime.now()

    else:

        evaluation = ParticipantEvaluation(

            participant_id=participant_id,

            influence_score=influence_score,

            spiritual_score=spiritual_score,

            creative_status=creative_status,

            participant_tier=participant_tier

        )

        db.add(evaluation)

    # ======================================================
    # UPDATE PARTICIPANT STATUS
    # ======================================================

    participant.registration_status = "Completed"

    participant.updated_at = datetime.datetime.now()

    db.commit()

    db.refresh(participant)

    db.refresh(evaluation)

    # ======================================================
    # RETURN COMPLETE SUMMARY
    # ======================================================

    return {

        "message":
            "Registration completed successfully.",

        "participant": {

            "participant_id":
                participant.id,

            "registration_number":
                participant.registration_number,

            "fullname":
                f"{participant.fname} "
                f"{participant.mname or ''} "
                f"{participant.lname}"
                .replace("  ", " ")
                .strip(),

            "registration_age":
                participant.registration_age,

            "registration_date":
                participant.registration_date,

            "registration_phase":
                participant.registration_phase,

            "registration_status":
                participant.registration_status

        },

        "event": {

            "event_id":
                event.id,

            "event_name":
                event.event_name,

            "registration_start":
                event.registration_start,

            "registration_end":
                event.registration_end,

            "kickoff_date":
                event.kickoff_date,

            "wrapup_date":
                event.wrapup_date

        },

        "evaluation": {

            "influence_score":
                evaluation.influence_score,

            "spiritual_score":
                evaluation.spiritual_score,

            "creative_status":
                evaluation.creative_status,

            "participant_tier":
                evaluation.participant_tier

        },

        "completed_at":
            participant.updated_at

    }




    

































# ======================================================
# COMPLETE ONLINE REGISTRATION
# ======================================================

@router.post("/registration_submit_all")
def registration_submit_all(
    data: OnlineRegistrationSchema,
    db: Session = Depends(get_db)
):

    try:

        # ==================================================
        # CHECK EVENT
        # ==================================================

        event = db.query(Event).filter(
            Event.id == data.participant.event_id,
            Event.is_archived == 0
        ).first()

        if not event:

            raise HTTPException(
                status_code=404,
                detail="Event not found."
            )

        # ==================================================
        # CHECK PARTICIPANT TYPE
        # ==================================================

        allowed_participant_types = [
            "Regular Participants",
            "Finding Sponsor"
        ]

        if (
            data.participant.participant_type
            not in allowed_participant_types
        ):

            raise HTTPException(
                status_code=400,
                detail="Invalid participant type."
            )

        # ==================================================
        # CHECK REGISTRATION PERIOD
        # ==================================================

        today = datetime.date.today()

        if today < event.registration_start:

            raise HTTPException(
                status_code=400,
                detail="Event registration has not started yet."
            )

        if today > event.kickoff_date:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Registration is already closed "
                    "because the event has started."
                )
            )

        # ==================================================
        # CHECK RULES AGREEMENT
        # ==================================================

        if not data.rules_agreed:

            raise HTTPException(
                status_code=400,
                detail=(
                    "You must accept the "
                    "Event Rules & Regulations."
                )
            )

        # ==================================================
        # CHECK DATA CONFIDENTIALITY
        # ==================================================

        if not data.confidentiality_agreed:

            raise HTTPException(
                status_code=400,
                detail=(
                    "You must agree to the "
                    "Data Confidentiality clause."
                )
            )

        # ==================================================
        # VALIDATE QUESTIONNAIRE
        # ==================================================

        questionnaire_fields = [

            "camp_attendance",
            "leadership_position",
            "church_involvement",
            "primary_strength",
            "ministry_skill",
            "salvation_assurance",
            "daily_devotion",
            "ministry_involvement",
            "sermon_notes",
            "small_group",
            "gospel_sharing",
            "temptation_response"

        ]

        for field in questionnaire_fields:

            value = data.questionnaire.get(field)

            if not value or not str(value).strip():

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Questionnaire field "
                        f"'{field}' is required."
                    )
                )

        # ==================================================
        # DUPLICATE VALIDATION
        # ==================================================

        duplicate = registration_duplicate_validation(

            db,

            data.participant.event_id,

            data.participant.fname,

            data.participant.mname,

            data.participant.lname,

            data.participant.birthdate

        )

        if duplicate:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Participant is already registered "
                    "for this event."
                )
            )

        # ==================================================
        # REGISTRATION PHASE
        # ==================================================

        registration_phase = (
            registration_phase_validation(event)
        )

        # ==================================================
        # CALCULATE AGE
        # ==================================================

        registration_age = (
            calculate_registration_age(
                data.participant.birthdate
            )
        )

        # ==================================================
        # GENERATE REGISTRATION NUMBER
        # ==================================================

        registration_number = (
            registration_number_generator(
                db,
                event
            )
        )

        # ==================================================
        # CREATE PARTICIPANT
        # ==================================================

        participant = Participant(

            event_id=event.id,

            event_name=event.event_name,

            registration_start=event.registration_start,

            registration_end=event.registration_end,

            kickoff_date=event.kickoff_date,

            wrapup_date=event.wrapup_date,

            registration_number=registration_number,

            registration_date=today,

            registration_phase=registration_phase,

            registration_status="Pending",

            participant_type=(
                data.participant.participant_type
            ),

            registration_age=registration_age,

            fname=data.participant.fname,

            mname=data.participant.mname,

            lname=data.participant.lname,

            sex=data.participant.sex,

            birthdate=data.participant.birthdate,

            address=data.participant.address,

            contact_number=data.participant.contact_number,

            emergency_contact=data.participant.emergency_contact,

            email=str(data.participant.email),

            local_church=data.participant.local_church,

            sector=data.participant.sector,

            tshirt_status="Unpaid",

            lanyard_status="Unpaid",

            is_archived=0
        )

        db.add(participant)

        # ==================================================
        # FLUSH PARTICIPANT
        # ==================================================

        db.flush()

        # ==================================================
        # CREATE QUESTIONNAIRE
        # ==================================================

        questionnaire = Questionnaire(

            participant_id=participant.id,

            camp_attendance=(
                data.questionnaire[
                    "camp_attendance"
                ]
            ),

            leadership_position=(
                data.questionnaire[
                    "leadership_position"
                ]
            ),

            church_involvement=(
                data.questionnaire[
                    "church_involvement"
                ]
            ),

            primary_strength=(
                data.questionnaire[
                    "primary_strength"
                ]
            ),

            ministry_skill=(
                data.questionnaire[
                    "ministry_skill"
                ]
            ),

            salvation_assurance=(
                data.questionnaire[
                    "salvation_assurance"
                ]
            ),

            daily_devotion=(
                data.questionnaire[
                    "daily_devotion"
                ]
            ),

            ministry_involvement=(
                data.questionnaire[
                    "ministry_involvement"
                ]
            ),

            sermon_notes=(
                data.questionnaire[
                    "sermon_notes"
                ]
            ),

            small_group=(
                data.questionnaire[
                    "small_group"
                ]
            ),

            gospel_sharing=(
                data.questionnaire[
                    "gospel_sharing"
                ]
            ),

            temptation_response=(
                data.questionnaire[
                    "temptation_response"
                ]
            )
        )

        db.add(questionnaire)

        # ==================================================
        # CREATE RULES AGREEMENT
        # ==================================================

        agreement = EventRulesAgreement(

            participant_id=participant.id,

            agreed=1,

            agreed_at=datetime.datetime.now()

        )

        db.add(agreement)

        # ==================================================
        # GET REGISTRATION ITEMS FROM DATABASE
        # ==================================================

        registration_items = (
            db.query(RegistrationItem)
            .filter(
                RegistrationItem.is_active == True
            )
            .order_by(
                RegistrationItem.id.asc()
            )
            .all()
        )

        # ==================================================
        # PREPARE REQUIRED / OPTIONAL ITEMS
        # ==================================================

        required_items = []

        optional_items = []

        for item in registration_items:

            item_data = {

                "id":
                    item.id,

                "name":
                    item.item_name,

                "price":
                    item.price

            }

            if getattr(item, "is_required", False):

                required_items.append(
                    item_data
                )

            else:

                optional_items.append(
                    item_data
                )

        # ==================================================
        # SAVE EVERYTHING
        # ==================================================

        db.commit()

        db.refresh(participant)

        db.refresh(questionnaire)

        db.refresh(agreement)

        # ==================================================
        # RESPONSE
        # ==================================================

        return {

            "message":
                "Registration submitted successfully.",

            "participant": {

                "participant_id":
                    participant.id,

                "registration_number":
                    participant.registration_number,

                "fullname":
                    (
                        f"{participant.fname} "
                        f"{participant.mname or ''} "
                        f"{participant.lname}"
                    ).replace(
                        "  ",
                        " "
                    ).strip(),

                "registration_status":
                    participant.registration_status,

                "registration_phase":
                    participant.registration_phase,

                "event_id":
                    participant.event_id,

                "event_name":
                    participant.event_name

            },

            "payment_required":
                len(required_items) > 0,

            "required_items":
                required_items,

            "optional_items":
                optional_items

        }

    except HTTPException:

        db.rollback()

        raise

    except Exception as e:

        db.rollback()

        raise HTTPException(

            status_code=500,

            detail=(
                "Registration could not be completed: "
                f"{str(e)}"
            )

        )
    
    
    
    
    








# ======================================================
# VIEW ACTIVE PARTICIPANTS
# ======================================================

@router.get("/registration_view_active_participants")
def registration_view_active_participants(
    db: Session = Depends(get_db)
):

    # ==================================================
    # GET ACTIVE PARTICIPANTS
    # ==================================================

    participants = db.query(Participant).filter(
        Participant.is_archived == 0
    ).all()

    result = []

    for participant in participants:

        # ==================================================
        # FULL NAME
        # ==================================================

        fullname = " ".join(
            part for part in [
                participant.fname,
                participant.mname,
                participant.lname
            ]
            if part
        ).strip()

        # ==================================================
        # REGISTRATION NUMBER
        # ==================================================

        registration_number = str(
            participant.registration_number or ""
        ).strip()

        # ==================================================
        # EVENT NAME
        # ==================================================

        event_name = str(
            participant.event_name or ""
        ).strip()

        # ==================================================
        # PARTICIPANT TYPE
        # ==================================================

        participant_type = str(
            participant.participant_type or ""
        ).strip()

        is_sponsor_participant = (
            participant_type.lower()
            == "finding sponsor"
        )

        # ==================================================
        # PAYMENT STATUS
        # ==================================================

        tshirt_status = str(
            participant.tshirt_status or "Unpaid"
        )

        lanyard_status = str(
            participant.lanyard_status or "Unpaid"
        )

        tshirt_status_lower = (
            tshirt_status.lower()
        )

        lanyard_status_lower = (
            lanyard_status.lower()
        )

        if (
            tshirt_status_lower == "paid"
            and
            lanyard_status_lower == "paid"
        ):

            payment_status = "Paid"

        elif (
            tshirt_status_lower == "paid"
            or
            lanyard_status_lower == "paid"
        ):

            payment_status = "Partial"

        else:

            payment_status = "Unpaid"

        # ==================================================
        # SPONSORSHIP STATUS
        # ==================================================

        if is_sponsor_participant:

            sponsorship_status = (
                "Sponsored in Review"
            )

            if (
                tshirt_status_lower == "paid"
                and
                lanyard_status_lower == "paid"
            ):

                merchandise_status = (
                    "Sponsored Confirmed"
                )

            elif (
                tshirt_status_lower == "paid"
                or
                lanyard_status_lower == "paid"
            ):

                merchandise_status = (
                    "Sponsored - Partial"
                )

            else:

                merchandise_status = (
                    "Sponsored in Review"
                )

            payment_status = (
                sponsorship_status
            )

        else:

            sponsorship_status = None
            merchandise_status = payment_status

        # ==================================================
        # PARTICIPANT TIER / EVALUATION
        # ==================================================

        evaluation = db.query(
            ParticipantEvaluation
        ).filter(
            ParticipantEvaluation.participant_id
            == participant.id
        ).first()

        participant_tier = (
            evaluation.participant_tier
            if evaluation
            else None
        )

        # ==================================================
        # GENERATE QR CODE
        #
        # QR CONTENT:
        # REGISTRATION NUMBER ONLY
        # ==================================================

        qr_code_base64 = None

        if registration_number:

            try:

                qr = qrcode.QRCode(
                    version=None,
                    error_correction=qrcode.constants.ERROR_CORRECT_M,
                    box_size=10,
                    border=4
                )

                qr.add_data(
                    registration_number
                )

                qr.make(
                    fit=True
                )

                qr_image = qr.make_image(
                    fill_color="black",
                    back_color="white"
                )

                qr_buffer = io.BytesIO()

                qr_image.save(
                    qr_buffer,
                    format="PNG"
                )

                qr_buffer.seek(0)

                qr_code_base64 = (
                    "data:image/png;base64,"
                    +
                    base64.b64encode(
                        qr_buffer.getvalue()
                    ).decode("utf-8")
                )

            except Exception as e:

                print(
                    "QR CODE GENERATION ERROR:",
                    repr(e)
                )

                qr_code_base64 = None

        # ==================================================
        # RESULT
        # ==================================================

        result.append({

            # ----------------------------------------------
            # PARTICIPANT
            # ----------------------------------------------

            "participant_id":
                participant.id,

            "registration_number":
                registration_number,

            "fullname":
                fullname,

            # ----------------------------------------------
            # QR CODE
            # ----------------------------------------------

            "qr_code":
                qr_code_base64,

            "qr_code_filename":
                (
                    f"{registration_number}-QR.png"
                    if registration_number
                    else
                    f"participant-{participant.id}-QR.png"
                ),

            # ----------------------------------------------
            # EVENT
            # ----------------------------------------------

            "event_name":
                participant.event_name,

            # ----------------------------------------------
            # PARTICIPANT TYPE
            # ----------------------------------------------

            "participant_type":
                participant_type,

            "is_sponsor_participant":
                is_sponsor_participant,

            # ----------------------------------------------
            # REGISTRATION
            # ----------------------------------------------

            "registration_phase":
                participant.registration_phase,

            "registration_status":
                participant.registration_status,

            # ----------------------------------------------
            # PAYMENT
            # ----------------------------------------------

            "payment_status":
                payment_status,

            # ----------------------------------------------
            # SPONSORSHIP
            # ----------------------------------------------

            "sponsorship_status":
                sponsorship_status,

            # ----------------------------------------------
            # MERCHANDISE
            # ----------------------------------------------

            "merchandise_status":
                merchandise_status,

            "tshirt_status":
                participant.tshirt_status or "Unpaid",

            "lanyard_status":
                participant.lanyard_status or "Unpaid",

            # ----------------------------------------------
            # EVALUATION
            # ----------------------------------------------

            "participant_tier":
                participant_tier
        })

    return result
