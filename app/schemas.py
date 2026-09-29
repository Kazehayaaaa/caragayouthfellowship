"""Pydantic request / response schemas."""

from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field
from typing import List
from typing import Optional
import datetime

# ======================================================
# PYDANTIC SCHEMAS
# ======================================================

class LoginSchema(BaseModel):

    username: str

    password: str
    

    
class AdminChangeCredentialSchema(BaseModel):

    username: str

    old_password: str

    new_username: str

    new_password: str
    
class LoginResponseSchema(BaseModel):

    message: str

    role: str

    redirect: str

    fullname: str

    username: str
    
class LogoutSchema(BaseModel):

    username: str
    
# ======================================================
# ADMIN SCHEMAS
# ======================================================

class AdminCreateRegistrationTeamSchema(BaseModel):

    admin_username: str

    fname: str

    mname: str

    lname: str


    birthday: datetime.date

    address: str

    email: EmailStr

    sex: str

    local_church: str

    contact_number: str

    sector: str

    username: str

    password: str

class AdminUpdateCredentialSchema(BaseModel):

    username: str

    old_password: str

    new_username: str

    new_password: str
    

# ======================================================
# EVENT SCHEMAS
# ======================================================

class EventCreateSchema(BaseModel):

    event_name: str

    registration_start: datetime.date

    registration_end: datetime.date

    kickoff_date: datetime.date

    wrapup_date: datetime.date
    

class EventUpdateSchema(BaseModel):

    event_name: str

    registration_start: datetime.date

    registration_end: datetime.date

    kickoff_date: datetime.date

    wrapup_date: datetime.date    



# ======================================================
# PARTICIPANT SCHEMAS
# ======================================================

class ParticipantCreateSchema(BaseModel):

    event_id: int

    participant_type: str

    fname: str
    mname: Optional[str] = None
    lname: str

    sex: str
    birthdate: datetime.date

    address: str
    contact_number: str
    emergency_contact: str

    email: EmailStr

    local_church: str
    sector: str
    

class ParticipantUpdateSchema(BaseModel):

    event_id:int
    
    participant_type: str

    fname:str

    mname:str=""

    lname:str

    sex:str

    birthdate:datetime.date

    address:str

    contact_number:str

    emergency_contact:str

    email:EmailStr

    local_church:str

    sector:str


# ======================================================
# QUESTIONNAIRE SCHEMA
# ======================================================

class QuestionnaireSchema(BaseModel):

    participant_id: int

    camp_attendance: str

    leadership_position: str

    church_involvement: str

    primary_strength: str

    ministry_skill: str

    salvation_assurance: str

    daily_devotion: str

    ministry_involvement: str

    sermon_notes: str

    small_group: str

    gospel_sharing: str

    temptation_response: str
    
# ======================================================
# COMPLETE ONLINE REGISTRATION SCHEMA
# ======================================================

class OnlineRegistrationSchema(BaseModel):

    # --------------------------------------------------
    # PARTICIPANT INFORMATION
    # --------------------------------------------------

    participant: ParticipantCreateSchema

    # --------------------------------------------------
    # QUESTIONNAIRE
    # --------------------------------------------------

    questionnaire: dict

    # --------------------------------------------------
    # AGREEMENTS
    # --------------------------------------------------

    rules_agreed: bool

    confidentiality_agreed: bool


# ======================================================
# EVENT RULES SCHEMA
# ======================================================

class EventRulesAgreementSchema(BaseModel):

    participant_id: int

    agreed: bool



# ======================================================
# STAFF REGISTRATION SCHEMA
# ======================================================

class StaffCreateSchema(BaseModel):

    event_id: int

    fname: str

    mname: Optional[str] = None

    lname: str

    position: str

    sex: Optional[str] = None

    birthday: Optional[datetime.date] = None

    contact_number: Optional[str] = None

    local_church: Optional[str] = None

    sector: Optional[str] = None


# ======================================================
# CHAPERONE REGISTRATION SCHEMA
# ======================================================

class ChaperoneCreateSchema(BaseModel):

    event_id: int

    fname: str

    mname: Optional[str] = None

    lname: str

    sex: str

    birthday: datetime.date

    contact_number: str

    local_church: str

    sector: str


class ChaperoneUpdateSchema(BaseModel):

    fname: str

    mname: Optional[str] = None

    lname: str

    sex: str

    birthday: datetime.date

    contact: str

    local_church: str

    sector: str


class StaffUpdateSchema(BaseModel):

    fname: str

    mname: Optional[str] = None

    lname: str

    position: str

    sex: Optional[str] = None

    birthday: Optional[datetime.date] = None

    contact_number: Optional[str] = None

    local_church: Optional[str] = None

    sector: Optional[str] = None








# ======================================================
# PAYMENT CREATE SCHEMA
# SUPPORTS SINGLE + BULK PARTICIPANTS
# ======================================================

class PaymentCreateSchema(BaseModel):

    # --------------------------------------------------
    # SINGLE PARTICIPANT
    # --------------------------------------------------

    participant_id: Optional[int] = None


    # --------------------------------------------------
    # BULK PARTICIPANTS
    # --------------------------------------------------

    participant_ids: Optional[List[int]] = None


    # --------------------------------------------------
    # ITEM SELECTION
    # --------------------------------------------------

    tshirt_selected: bool = False

    lanyard_selected: bool = False


    # --------------------------------------------------
    # OPTIONAL ALIASES
    #
    # Allows frontend to send:
    #
    # "tshirt"
    # "lanyard"
    #
    # in addition to:
    #
    # "tshirt_selected"
    # "lanyard_selected"
    # --------------------------------------------------

    tshirt: Optional[bool] = None

    lanyard: Optional[bool] = None


    # --------------------------------------------------
    # T-SHIRT SIZE
    # --------------------------------------------------

    tshirt_size: Optional[str] = None
    
    participant_tshirt_selections: Optional[List[dict]] = None

    # --------------------------------------------------
    # BULK FLAG
    # --------------------------------------------------

    bulk: bool = False
    
    
    
    
    


# ============================================================
# MANUAL FINDING SPONSOR SCHEMAS
# ============================================================

class ManualFindingSponsorTriggerSchema(BaseModel):
    participant_id: int


class ManualFindingSponsorToggleSchema(BaseModel):
    enabled: bool





    
    

# ============================================================
# CASH SPONSORSHIP SCHEMA
# ============================================================

class CashSponsorshipCreate(BaseModel):

    sponsor_name: str = Field(
        min_length=2,
        max_length=255
    )

    local_church: str = Field(
        min_length=2,
        max_length=255
    )

    contact: str = Field(
        min_length=7,
        max_length=50
    )

    sector: str

    email: EmailStr

    selected_tier: str

    donation_amount: float










# ============================================================
# ITEM SPONSORSHIP SCHEMA
# ============================================================

class ItemSponsorshipItem(BaseModel):

    item_id: int

    item_name: Optional[str] = None

    quantity: int


class ItemSponsorshipCreate(BaseModel):

    sponsor_name: str

    local_church: str

    visiting_church: Optional[str] = None

    contact: Optional[str] = None

    sector: str

    email: Optional[str] = None

    items: List[ItemSponsorshipItem]









# ============================================================
# CREATE SPONSORSHIP ITEM
# ============================================================

class SponsorshipItemCreate(BaseModel):

    item_name: str

    description: Optional[str] = None

    quantity: int = Field(
        gt=0
    )

    unit: str = "piece"










# ======================================================
# CREATE SPONSORSHIP ITEM SCHEMA
# ======================================================

class SponsorshipItemCreateSchema(BaseModel):

    item_name: str
    description: Optional[str] = None
    unit: str
    required_quantity: int











# ============================================================
# STORE ITEM CREATE SCHEMA
# ============================================================

class StoreItemCreateSchema(BaseModel):
    item_name: str
    description: str | None = None
    category: str
    quantity: int
    price: float
    image_url: str | None = None
    sizes: list[str] | None = None


class StoreItemUpdateSchema(BaseModel):
    item_name: str
    description: str | None = None
    category: str
    quantity: int
    price: float
    image_url: str | None = None
    sizes: list[str] | None = None











# ============================================================
# STORE CART ITEM
# ============================================================

class StorePurchaseItemSchema(BaseModel):

    store_item_id: int

    quantity: int

    size: Optional[str] = None








# ============================================================
# STORE PURCHASE
# ============================================================

class StorePurchaseSchema(BaseModel):

    customer_name: str

    customer_contact: str

    customer_email: EmailStr

    items: List[StorePurchaseItemSchema]






# ==========================================================
# CONTACT REQUEST MODEL
# ==========================================================

class ContactRequest(BaseModel):

    name: str
    email: EmailStr
    subject: str
    message: str



















# ============================================================
# ITEM SPONSORSHIP RESPONSE
# ============================================================

class ItemSponsorshipResponse(BaseModel):

    id: int

    sponsor_name: str

    local_church: str

    visiting_church: Optional[str] = None

    contact: Optional[str] = None

    sector: Optional[str] = None

    email: Optional[str] = None

    item_id: int

    item_name: str

    quantity: int

    status: str

    created_at: datetime.datetime

    class Config:
        from_attributes = True











# ============================================================
# CASH SPONSORSHIP RESPONSE
# ============================================================

class CashSponsorshipResponse(BaseModel):

    id: int

    sponsor_name: str

    local_church: str

    contact: Optional[str] = None

    sector: Optional[str] = None

    email: Optional[str] = None

    selected_tier: str

    donation_amount: int

    payment_status: str

    paymongo_link_id: Optional[str] = None

    paymongo_reference: Optional[str] = None

    payment_url: Optional[str] = None

    created_at: datetime.datetime

    paid_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class PaymentResponse(BaseModel):

    id: int

    participant_id: Optional[int] = None

    payment_type: str

    store_item_id: Optional[int] = None
    store_quantity: Optional[int] = None
    store_size: Optional[str] = None

    amount: int
    currency: str
    status: str

    tshirt_selected: int = 0
    lanyard_selected: int = 0
    tshirt_size: Optional[str] = None

    sponsorship_tier: Optional[str] = None
    sponsor_id: Optional[int] = None

    paymongo_link_id: Optional[str] = None
    paymongo_payment_id: Optional[str] = None
    paymongo_reference: Optional[str] = None
    checkout_url: Optional[str] = None

    description: Optional[str] = None

    customer_name: Optional[str] = None
    customer_contact: Optional[str] = None
    customer_email: Optional[str] = None

    created_at: Optional[datetime.datetime] = None
    paid_at: Optional[datetime.datetime] = None

    # ==========================================
    # DISPLAY NAME
    # ==========================================

    participant_name: Optional[str] = None

    class Config:
        from_attributes = True
 
 
 
 
 
 
 
        
        
# ============================================================
# REGISTRATION ITEM SCHEMAS
# ============================================================

class RegistrationItemCreate(BaseModel):

    item_name: str

    price: int


class RegistrationItemUpdate(BaseModel):

    item_name: Optional[str] = None

    price: Optional[int] = None

    is_active: Optional[bool] = None


class RegistrationItemResponse(BaseModel):

    id: int

    item_name: str

    price: int

    is_active: bool

    created_at: datetime.datetime

    updated_at: datetime.datetime

    class Config:
        from_attributes = True        
        
 
 
 
 
 
 
 
        
        
# ============================================================
# SCHEMAS
# ============================================================

class CashDonationTotalCreateSchema(BaseModel):

    amount: int


class CashDonationTotalUpdateSchema(BaseModel):

    amount: int        
