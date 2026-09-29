"""Routes: questionnaire."""

from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session
import datetime
from fastapi import APIRouter

from app.database import (
    get_db,
)
from app.models import (
    EventRulesAgreement,
    Participant,
    ParticipantEvaluation,
    Questionnaire,
)
from app.schemas import (
    EventRulesAgreementSchema,
    QuestionnaireSchema,
)
from app.services.registration import (
    creative_identifier,
    influence_score_calculator,
    questionnaire_duplicate_validation,
    spiritual_score_calculator,
    tier_assignment,
)

router = APIRouter()

# ======================================================
# Questionnaire
# ====================================================== 


@router.post("/questionnaire_submit_answers")
def questionnaire_submit_answers(

    data: QuestionnaireSchema,

    db: Session = Depends(get_db)

):

    participant = db.query(Participant).filter(

        Participant.id == data.participant_id,

        Participant.is_archived == 0

    ).first()

    if not participant:

        raise HTTPException(

            status_code=404,

            detail="Participant not found."

        )

    duplicate = questionnaire_duplicate_validation(

        db,

        data.participant_id

    )

    if duplicate:

        raise HTTPException(

            status_code=400,

            detail="Questionnaire already submitted."

        )

    questionnaire = Questionnaire(

        participant_id=data.participant_id,

        camp_attendance=data.camp_attendance,

        leadership_position=data.leadership_position,

        church_involvement=data.church_involvement,

        primary_strength=data.primary_strength,

        ministry_skill=data.ministry_skill,

        salvation_assurance=data.salvation_assurance,

        daily_devotion=data.daily_devotion,

        ministry_involvement=data.ministry_involvement,

        sermon_notes=data.sermon_notes,

        small_group=data.small_group,

        gospel_sharing=data.gospel_sharing,

        temptation_response=data.temptation_response

    )

    db.add(questionnaire)

    db.commit()

    db.refresh(questionnaire)

    return {

        "message":"Questionnaire submitted successfully.",

        "questionnaire_id":questionnaire.id

    }
    

# ======================================================
# View Questionnaire
# ====================================================== 


@router.get("/questionnaire_view_answers/{participant_id}")
def questionnaire_view_answers(

    participant_id: int,

    db: Session = Depends(get_db)

):

    questionnaire = db.query(Questionnaire).filter(

        Questionnaire.participant_id == participant_id

    ).first()

    if not questionnaire:

        raise HTTPException(

            status_code=404,

            detail="Questionnaire not found."

        )

    return questionnaire


# ======================================================
# Update Questionnaire
# ======================================================     

@router.put("/questionnaire_update_answers/{participant_id}")
def questionnaire_update_answers(

    participant_id: int,

    data: QuestionnaireSchema,

    db: Session = Depends(get_db)

):

    questionnaire = db.query(Questionnaire).filter(

        Questionnaire.participant_id == participant_id

    ).first()

    if not questionnaire:

        raise HTTPException(

            status_code=404,

            detail="Questionnaire not found."

        )

    questionnaire.camp_attendance = data.camp_attendance
    questionnaire.leadership_position = data.leadership_position
    questionnaire.church_involvement = data.church_involvement
    questionnaire.primary_strength = data.primary_strength
    questionnaire.ministry_skill = data.ministry_skill
    questionnaire.salvation_assurance = data.salvation_assurance
    questionnaire.daily_devotion = data.daily_devotion
    questionnaire.ministry_involvement = data.ministry_involvement
    questionnaire.sermon_notes = data.sermon_notes
    questionnaire.small_group = data.small_group
    questionnaire.gospel_sharing = data.gospel_sharing
    questionnaire.temptation_response = data.temptation_response
    questionnaire.updated_at = datetime.datetime.now()

    db.commit()

    return {

        "message":"Questionnaire updated successfully."

    }
    
    

# ======================================================
# Accept Rules
# ======================================================    

@router.post("/rules_accept_event_agreement")
def rules_accept_event_agreement(

    data: EventRulesAgreementSchema,

    db: Session = Depends(get_db)

):

    participant = db.query(Participant).filter(

        Participant.id == data.participant_id,

        Participant.is_archived == 0

    ).first()

    if not participant:

        raise HTTPException(

            status_code=404,

            detail="Participant not found."

        )

    agreement = db.query(EventRulesAgreement).filter(

        EventRulesAgreement.participant_id == data.participant_id

    ).first()

    if agreement:

        agreement.agreed = data.agreed
        agreement.agreed_at = datetime.datetime.now()

    else:

        agreement = EventRulesAgreement(

            participant_id=data.participant_id,

            agreed=data.agreed,

            agreed_at=datetime.datetime.now() if data.agreed else None

        )

        db.add(agreement)

    db.commit()

    db.refresh(agreement)

    return {

        "message":"Rules agreement saved successfully.",

        "agreed":bool(agreement.agreed)

    }
    
      
# ======================================================
# View Agreement
# ======================================================  

@router.get("/rules_view_event_agreement/{participant_id}")
def rules_view_event_agreement(

    participant_id:int,

    db:Session=Depends(get_db)

):

    agreement=db.query(EventRulesAgreement).filter(

        EventRulesAgreement.participant_id==participant_id

    ).first()

    if not agreement:

        raise HTTPException(

            status_code=404,

            detail="Agreement not found."

        )

    return agreement


# ======================================================
# RECALCULATE PARTICIPANT SCORES
# ======================================================   

@router.post("/questionnaire_recalculate_scores")
def questionnaire_recalculate_scores(

    participant_id: int,

    db: Session = Depends(get_db)

):

    questionnaire = db.query(Questionnaire).filter(

        Questionnaire.participant_id == participant_id

    ).first()

    if not questionnaire:

        raise HTTPException(

            status_code=404,

            detail="Questionnaire not found."

        )

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

    evaluation = db.query(

        ParticipantEvaluation

    ).filter(

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

    db.commit()

    db.refresh(evaluation)

    return {

        "message": "Participant evaluation recalculated successfully.",

        "participant_id": participant_id,

        "participant_tier": evaluation.participant_tier,

        "spiritual_score": evaluation.spiritual_score,

        "influence_score": evaluation.influence_score,

        "creative_status": evaluation.creative_status

    }

# ======================================================
# VIEW PARTICIPANT EVALUATION
# ======================================================      

@router.get("/evaluation_view_participant_evaluation")
def evaluation_view_participant_evaluation(

    participant_id: int,

    db: Session = Depends(get_db)

):

    participant = db.query(Participant).filter(

        Participant.id == participant_id

    ).first()

    if not participant:

        raise HTTPException(

            status_code=404,

            detail="Participant not found."

        )

    evaluation = db.query(

        ParticipantEvaluation

    ).filter(

        ParticipantEvaluation.participant_id == participant_id

    ).first()

    if not evaluation:

        raise HTTPException(

            status_code=404,

            detail="Participant has not yet been evaluated."

        )

    return {

        "participant": {

            "participant_id": participant.id,

            "registration_number": participant.registration_number,

            "fullname": f"{participant.fname} {participant.mname} {participant.lname}",

            "event_name": participant.event_name,

            "registration_phase": participant.registration_phase,

            "registration_status": participant.registration_status

        },

        "evaluation": {

            "participant_tier": evaluation.participant_tier,

            "spiritual_score": evaluation.spiritual_score,

            "influence_score": evaluation.influence_score,

            "creative_status": evaluation.creative_status

        }

    }
