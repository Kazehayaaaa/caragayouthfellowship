"""Registration rules, validation, scoring and tier assignment."""

from sqlalchemy.orm import Session
import datetime

from app.models import (
    EventRulesAgreement,
    Participant,
    Questionnaire,
)

# ======================================================
# EVENT HELPER FUNCTIONS
# ======================================================

def get_registration_phase(event):

    today = datetime.date.today()

    if today < event.registration_start:

        return "Registration Closed"

    elif event.registration_start <= today <= event.registration_end:

        return "Early-bird"

    elif event.registration_end < today <= event.wrapup_date:

        return "Walk-in"

    else:

        return "Event Closed"
    

# ======================================================
# PARTICIPANT HELPER FUNCTIONS
# ======================================================

def registration_duplicate_validation(

    db: Session,

    event_id: int,

    fname: str,

    mname: str,

    lname: str,

    birthdate: datetime.date

):

    participant = db.query(Participant).filter(

        Participant.event_id == event_id,

        Participant.fname == fname,

        Participant.mname == mname,

        Participant.lname == lname,

        Participant.birthdate == birthdate,

        Participant.is_archived == 0

    ).first()

    return participant



def registration_phase_validation(event):

    today = datetime.date.today()

    if today <= event.registration_end:

        return "Early-bird"

    return "Walk-in"




def registration_number_generator(

    db: Session,

    event

):

    year = event.kickoff_date.year

    if event.event_name == "Summer Youth Camp":

        prefix = "SYC"

    else:

        prefix = "YBC"

    count = db.query(Participant).filter(

        Participant.event_id == event.id

    ).count()

    return f"{prefix}-{year}-{count + 1:04d}"    


# ======================================================
# QUESTIONNAIRE HELPER
# ======================================================

def questionnaire_duplicate_validation(

    db: Session,

    participant_id: int

):

    return db.query(Questionnaire).filter(

        Questionnaire.participant_id == participant_id

    ).first()


def influence_score_calculator(questionnaire):

    score = 0

    # Camp Attendance

    if questionnaire.camp_attendance == "3 or more camps":

        score += 3

    elif questionnaire.camp_attendance == "1 to 2 camps":

        score += 2

    else:

        score += 1

    # Leadership

    if questionnaire.leadership_position == "Yes, active leader":

        score += 3

    elif questionnaire.leadership_position == "No, but I help out often":

        score += 2

    else:

        score += 1

    # Church Involvement

    if questionnaire.church_involvement.startswith("Highly active"):

        score += 3

    elif questionnaire.church_involvement.startswith("Fairly regular"):

        score += 2

    else:

        score += 1

    return score


def spiritual_score_calculator(questionnaire):

    score = 0

    questions = [

        questionnaire.salvation_assurance,

        questionnaire.daily_devotion,

        questionnaire.ministry_involvement,

        questionnaire.sermon_notes,

        questionnaire.small_group,

        questionnaire.gospel_sharing,

        questionnaire.temptation_response

    ]

    for answer in questions:

        if answer.startswith("Yes") or answer.startswith("Very"):

            score += 2

        elif answer.startswith("Sometimes") or answer.startswith("Somewhat") or answer.startswith("No, but") or answer.startswith("I believe") or answer.startswith("I try"):

            score += 1

        else:

            score += 0

    return score


def creative_identifier(questionnaire):

    creative_skills = [

        "Music / Singing",

        "Arts / Dance / Media Production"

    ]

    if questionnaire.ministry_skill in creative_skills:

        return "Creative"

    return "Non-Creative"


def tier_assignment(

    influence_score,

    spiritual_score,

    creative_status

):

    if spiritual_score >= 11 and influence_score >= 7:

        return "Tier 1 - Anchor Leaders"

    if creative_status == "Creative":

        return "Tier 2 - Culture Catalysts"

    if 7 <= spiritual_score <= 10:

        return "Tier 3 - The Steady Core"

    if 3 <= spiritual_score <= 6:

        return "Tier 4 - The Fresh Soil"

    return "Tier 5 - The Wildcards"


# ======================================================
# RULES VALIDATION
# ======================================================

def registration_rules_validation(

    db: Session,

    participant_id: int

):

    return db.query(EventRulesAgreement).filter(

        EventRulesAgreement.participant_id == participant_id,

        EventRulesAgreement.agreed == 1

    ).first()


def calculate_registration_age(

    birthdate: datetime.date

):

    today = datetime.date.today()

    age = today.year - birthdate.year

    if (

        today.month,

        today.day

    ) < (

        birthdate.month,

        birthdate.day

    ):

        age -= 1

    return age
