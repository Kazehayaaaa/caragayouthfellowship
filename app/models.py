"""SQLAlchemy models."""

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
import datetime

from app.database import (
    Base,
)

# ======================================================
# DATABASE MODELS
# ======================================================

class User(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    fname = Column(String(100))
    mname = Column(String(100))
    lname = Column(String(100))

    age = Column(Integer)

    birthday = Column(Date)

    address = Column(String(255))

    email = Column(
        String(150),
        unique=True
    )

    sex = Column(String(20))

    local_church = Column(String(150))

    contact_number = Column(String(20))

    sector = Column(String(100))

    username = Column(
        String(100),
        unique=True
    )

    password = Column(String(255))

    role = Column(String(50))

    created_at = Column(
        DateTime,
        default=datetime.datetime.now
    )

    updated_at = Column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now
    )
    
    last_login = Column(
        DateTime, 
        nullable=True
    )
    
    
# ======================================================
# EVENT MODEL
# ======================================================

class Event(Base):

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)

    event_name = Column(String(100), nullable=False)

    registration_start = Column(Date, nullable=False)

    registration_end = Column(Date, nullable=False)

    kickoff_date = Column(Date, nullable=False)

    wrapup_date = Column(Date, nullable=False)

    is_archived = Column(Integer, default=0)

    created_at = Column(
        DateTime,
        default=datetime.datetime.now
    )

    updated_at = Column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now
    )
    

# ======================================================
# PARTICIPANT MODEL
# ======================================================

class Participant(Base):

    __tablename__ = "participants"

    # ======================================================
    # PRIMARY KEY
    # ======================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # ======================================================
    # EVENT REFERENCE
    # ======================================================

    event_id = Column(
        Integer,
        nullable=False
    )

    # ======================================================
    # EVENT SNAPSHOT
    # ======================================================

    event_name = Column(
        String(100),
        nullable=False
    )

    registration_start = Column(
        Date,
        nullable=False
    )

    registration_end = Column(
        Date,
        nullable=False
    )

    kickoff_date = Column(
        Date,
        nullable=False
    )

    wrapup_date = Column(
        Date,
        nullable=False
    )

    # ======================================================
    # REGISTRATION INFORMATION
    # ======================================================

    registration_number = Column(
        String(30),
        unique=True,
        nullable=False
    )

    registration_date = Column(
        Date,
        default=datetime.date.today
    )

    registration_phase = Column(
        String(20),
        nullable=False
    )

    registration_status = Column(
        String(20),
        nullable=False,
        default="Pending"
    )
    
    participant_type = Column(
    String(50),
    nullable=False,
    default="Regular Participants"
    )

    # ======================================================
    # PARTICIPANT INFORMATION
    # ======================================================

    fname = Column(
        String(100),
        nullable=False
    )

    mname = Column(
    String(100),
    nullable=True
    )

    lname = Column(
        String(100),
        nullable=False
    )

    registration_age = Column(
        Integer,
        nullable=False
    )

    sex = Column(
        String(20)
    )

    birthdate = Column(
        Date
    )

    address = Column(
        String(255)
    )

    contact_number = Column(
        String(20)
    )

    emergency_contact = Column(
        String(20)
    )

    email = Column(
        String(150)
    )

    local_church = Column(
        String(150)
    )

    sector = Column(
        String(100)
    )
    
    # ======================================================
    # MERCHANDISE PAYMENT STATUS
    # ======================================================

    tshirt_status = Column(
        String(20),
        nullable=False,
        default="Unpaid"
    )

    lanyard_status = Column(
        String(20),
        nullable=False,
        default="Unpaid"
    )    
    
    tshirt_size = Column(
    String(10),
    nullable=True
    )

    # ======================================================
    # RECORD STATUS
    # ======================================================

    is_archived = Column(
        Integer,
        default=0
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.now
    )

    updated_at = Column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now
    )

# ======================================================
# QUESTIONNAIRE MODEL
# ======================================================

class Questionnaire(Base):

    __tablename__ = "questionnaires"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    participant_id = Column(
        Integer,
        unique=True,
        nullable=False
    )

    # -----------------------------
    # Section 1
    # -----------------------------

    camp_attendance = Column(String(100))

    leadership_position = Column(String(100))

    church_involvement = Column(String(100))

    # -----------------------------
    # Section 2
    # -----------------------------

    primary_strength = Column(String(150))

    ministry_skill = Column(String(150))

    # -----------------------------
    # Section 3
    # -----------------------------

    salvation_assurance = Column(String(255))

    daily_devotion = Column(String(255))

    ministry_involvement = Column(String(255))

    sermon_notes = Column(String(255))

    small_group = Column(String(255))

    gospel_sharing = Column(String(255))

    temptation_response = Column(String(255))

    created_at = Column(
        DateTime,
        default=datetime.datetime.now
    )

    updated_at = Column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now
    )
    
# ======================================================
# PARTICIPANT EVALUATION
# ======================================================

class ParticipantEvaluation(Base):

    __tablename__ = "participant_evaluations"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    participant_id = Column(
        Integer,
        unique=True,
        nullable=False
    )

    influence_score = Column(
        Integer,
        default=0
    )

    spiritual_score = Column(
        Integer,
        default=0
    )

    creative_status = Column(
        String(30)
    )

    participant_tier = Column(
        String(50)
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.now
    )

    updated_at = Column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now
    )

# ======================================================
# EVENT RULES AGREEMENT
# ======================================================

class EventRulesAgreement(Base):

    __tablename__ = "event_rules_agreements"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    participant_id = Column(
        Integer,
        unique=True,
        nullable=False
    )

    agreed = Column(
        Integer,
        default=0
    )

    agreed_at = Column(
        DateTime,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.now
    )        

# ======================================================
# CHAPERONE MODEL
# ======================================================

class Chaperone(Base):

    __tablename__ = "chaperones"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # ======================================================
    # EVENT REFERENCE
    # ======================================================

    event_id = Column(
        Integer,
        nullable=False
    )

    # ======================================================
    # CHAPERONE INFORMATION
    # ======================================================

    fname = Column(
        String(100),
        nullable=False
    )

    mname = Column(
        String(100),
        nullable=True
    )

    lname = Column(
        String(100),
        nullable=False
    )


    sex = Column(
        String(20),
        nullable=True
    )

    birthday = Column(
        Date,
        nullable=True
    )

    contact = Column(
        String(20),
        nullable=True
    )

    local_church = Column(
        String(150),
        nullable=True
    )

    sector = Column(
        String(100),
        nullable=True
    )

    # ======================================================
    # RECORD STATUS
    # ======================================================

    is_archived = Column(
        Integer,
        default=0
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.now
    )

    updated_at = Column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now
    )
    
    
# ======================================================
# STAFF MODEL
# ======================================================

class Staff(Base):

    __tablename__ = "staff"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # ======================================================
    # EVENT REFERENCE
    # ======================================================

    event_id = Column(
        Integer,
        nullable=False
    )

    # ======================================================
    # STAFF INFORMATION
    # ======================================================

    fname = Column(
        String(100),
        nullable=False
    )

    mname = Column(
        String(100)
    )

    lname = Column(
        String(100),
        nullable=False
    )
    
     # ADD THIS
    position = Column(String, nullable=True)

    sex = Column(
        String(20),
        nullable=False
    )

    birthday = Column(
        Date,
        nullable=False
    )

    contact = Column(
        String(20),
        nullable=False
    )

    local_church = Column(
        String(150),
        nullable=False
    )

    sector = Column(
        String(100),
        nullable=False
    )

    # ======================================================
    # RECORD STATUS
    # ======================================================

    is_archived = Column(
        Integer,
        default=0
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.now
    )

    updated_at = Column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now
    ) 
    
    
    
    
       

# ======================================================
# PAYMENT MODEL
# ======================================================

class Payment(Base):

    __tablename__ = "payments"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # ==================================================
    # PARTICIPANT
    # ==================================================

    participant_id = Column(
        Integer,
        ForeignKey("participants.id"),
        nullable=True
    )

    # ==================================================
    # PAYMENT TYPE
    # ==================================================
    #
    # Participant
    # Sponsor
    # Store
    #

    payment_type = Column(
        String(30),
        nullable=False,
        default="Participant",
        index=True
    )

    # ==================================================
    # STORE PURCHASE
    # ==================================================
    #
    # These fields are important.
    #
    # The webhook must be able to identify the
    # purchased StoreItem without depending on
    # PayMongo metadata.
    #


    # ========================================================
    # STORE
    # ========================================================

    store_order_id = Column(
        String(100),
        nullable=True,
        index=True
    )

    
    store_item_id = Column(
        Integer,
        ForeignKey("store_items.id"),
        nullable=True,
        index=True
    )

    store_quantity = Column(
        Integer,
        nullable=True,
        default=1
    )

    # Store clothing size.
    #
    # Example:
    # S
    # M
    # L
    # XL
    # 2XL
    #

    store_size = Column(
        String(20),
        nullable=True
    )

    # ==================================================
    # AMOUNT
    # ==================================================

    amount = Column(
        Integer,
        nullable=False
    )

    currency = Column(
        String(10),
        nullable=False,
        default="PHP"
    )

    # ==================================================
    # PAYMENT STATUS
    # ==================================================

    status = Column(
        String(30),
        nullable=False,
        default="Pending",
        index=True
    )

    # ==================================================
    # PARTICIPANT ITEMS
    # ==================================================

    tshirt_selected = Column(
        Integer,
        default=0
    )

    lanyard_selected = Column(
        Integer,
        default=0
    )

    tshirt_size = Column(
        String(10),
        nullable=True
    )

    # ==================================================
    # SPONSORSHIP
    # ==================================================

    sponsorship_tier = Column(
        String(30),
        nullable=True,
        index=True
    )

    sponsor_id = Column(
        Integer,
        nullable=True,
        index=True
    )

    # ==================================================
    # PAYMONGO
    # ==================================================

    paymongo_link_id = Column(
        String(100),
        nullable=True,
        index=True
    )

    paymongo_payment_id = Column(
        String(100),
        nullable=True,
        index=True
    )

    paymongo_reference = Column(
        String(100),
        nullable=True,
        index=True
    )

    checkout_url = Column(
        String(500),
        nullable=True
    )

    # ==================================================
    # PAYMENT DESCRIPTION
    # ==================================================

    description = Column(
        String(500),
        nullable=True
    )

    # ==================================================
    # CUSTOMER INFORMATION
    # ==================================================

    customer_name = Column(
        String(255),
        nullable=True
    )

    customer_contact = Column(
        String(100),
        nullable=True
    )

    customer_email = Column(
        String(255),
        nullable=True
    )

    # ==================================================
    # PAYMENT DATES
    # ==================================================

    created_at = Column(
        DateTime,
        default=datetime.datetime.now
    )

    paid_at = Column(
        DateTime,
        nullable=True
    )
    receipt_sent = Column(
        Boolean,
        nullable=False,
        default=False
    )

    
    
    
    
    
    


# ============================================================
# SPONSORSHIP PACKAGE
# ============================================================

class SponsorshipPackage(Base):

    __tablename__ = "sponsorship_packages"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    tier = Column(
        String(50),
        nullable=False,
        unique=True
    )

    minimum_amount = Column(
        Integer,
        nullable=False
    )

    maximum_amount = Column(
        Integer,
        nullable=True
    )

    description = Column(
        Text,
        nullable=True
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False
    )


# ============================================================
# CASH SPONSORSHIP
# ============================================================

class CashSponsorship(Base):

    __tablename__ = "cash_sponsorships"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    sponsor_name = Column(
        String(255),
        nullable=False
    )

    local_church = Column(
        String(255),
        nullable=False
    )

    contact = Column(
        String(100),
        nullable=False
    )

    sector = Column(
        String(100),
        nullable=False
    )

    email = Column(
        String(255),
        nullable=False
    )

    selected_tier = Column(
        String(50),
        nullable=False
    )

    donation_amount = Column(
        Integer,
        nullable=False
    )

    payment_status = Column(
        String(30),
        default="Pending",
        nullable=False
    )

    paymongo_link_id = Column(
        String(255),
        nullable=True,
        index=True
    )

    paymongo_reference = Column(
        String(255),
        nullable=True,
        index=True
    )

    payment_url = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.now,
        nullable=False
    )

    paid_at = Column(
        DateTime,
        nullable=True
    )
    
    cash_total_added = Column(
    Integer,
    default=False,
    nullable=False
    )


# ============================================================
# ITEM DONATION INVENTORY
# ============================================================

class SponsorshipItem(Base):

    __tablename__ = "sponsorship_items"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    item_name = Column(
        String(255),
        nullable=False
    )

    description = Column(
        Text,
        nullable=True
    )

    total_quantity = Column(
        Integer,
        nullable=False,
        default=0
    )

    remaining_quantity = Column(
        Integer,
        nullable=False,
        default=0
    )

    unit = Column(
        String(50),
        nullable=False,
        default="piece"
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.now,
        nullable=False
    )


# ============================================================
# ITEM DONATION RECORD
# ============================================================

class ItemSponsorship(Base):

    __tablename__ = "item_sponsorships"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    sponsor_name = Column(
        String(255),
        nullable=False
    )

    local_church = Column(
        String(255),
        nullable=False
    )
    
    visiting_church = Column(
    String,
    nullable=True
    )

    contact = Column(
        String(100),
        nullable=False
    )

    sector = Column(
        String(100),
        nullable=False
    )

    email = Column(
        String(255),
        nullable=False
    )

    item_id = Column(
        Integer,
        nullable=False,
        index=True
    )

    item_name = Column(
        String(255),
        nullable=False
    )

    quantity = Column(
        Integer,
        nullable=False
    )

    status = Column(
        String(30),
        default="Confirmed",
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.now,
        nullable=False
    )


# ============================================================
# STORE ITEM MODEL
# ============================================================

class StoreItem(Base):

    __tablename__ = "store_items"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # --------------------------------------------------------
    # ITEM NAME
    # --------------------------------------------------------

    item_name = Column(
        String(255),
        nullable=False
    )

    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    description = Column(
        String(1000),
        nullable=True
    )

    # --------------------------------------------------------
    # CATEGORY
    #
    # clothes
    # souvenir
    # others
    # --------------------------------------------------------

    category = Column(
        String(50),
        nullable=False,
        default="others",
        index=True
    )

    # --------------------------------------------------------
    # AVAILABLE SIZES
    #
    # Stored as JSON text.
    #
    # Example:
    #
    # ["S","M","L","XL","2XL"]
    #
    # For non-clothes:
    #
    # NULL
    # --------------------------------------------------------

    sizes = Column(
        Text,
        nullable=True
    )

    # --------------------------------------------------------
    # INVENTORY
    # --------------------------------------------------------

    quantity = Column(
        Integer,
        nullable=False,
        default=0
    )

    # --------------------------------------------------------
    # PRICE
    #
    # Store this as PHP amount.
    #
    # Example:
    #
    # 350
    #
    # means ₱350.00
    # --------------------------------------------------------

    price = Column(
        Integer,
        nullable=False
    )
    
    # --------------------------------------------------------
    # IMAGES
    # --------------------------------------------------------
    
    
    image_url = Column(
    String,
    nullable=True
    )

    # --------------------------------------------------------
    # ARCHIVE
    # --------------------------------------------------------

    is_archived = Column(
        Integer,
        nullable=False,
        default=0
    )

    # --------------------------------------------------------
    # DATES
    # --------------------------------------------------------

    created_at = Column(
        DateTime,
        default=datetime.datetime.now
    )

    updated_at = Column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now
    )

class RegistrationItem(Base):

    __tablename__ = "registration_items"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    item_name = Column(
        String(100),
        unique=True,
        nullable=False
    )

    price = Column(
        Integer,
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.now,
        nullable=False
    )

    updated_at = Column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        nullable=False
    )


# ============================================================
# CASH DONATION TOTAL MODEL
# ============================================================

class CashDonationTotal(Base):

    __tablename__ = "cash_donation_total"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    total_amount = Column(
        Integer,
        nullable=False,
        default=0
    )

    created_at = Column(
        DateTime,
        default=datetime.datetime.now,
        nullable=False
    )

    updated_at = Column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        nullable=False
    )
