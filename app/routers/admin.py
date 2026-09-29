"""Routes: admin."""

from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session
import datetime
from fastapi import APIRouter

from app.database import (
    get_db,
)
from app.models import (
    User,
)
from app.schemas import (
    AdminCreateRegistrationTeamSchema,
    AdminUpdateCredentialSchema,
)
from app.security import (
    hash_password,
    verify_admin,
    verify_password,
)
from app.services.registration import (
    calculate_registration_age,
)

router = APIRouter()

# ======================================================
# ADMIN APIs
# ======================================================

    

@router.put("/admin_change_admin_credentials")
def admin_change_admin_credentials(

    data: AdminUpdateCredentialSchema,

    db: Session = Depends(get_db)

):

    admin = verify_admin(

        db,

        data.username

    )

    if not verify_password(

        data.old_password,

        admin.password

    ):

        raise HTTPException(

            status_code=400,

            detail="Old password is incorrect."

        )

    username_exist = db.query(User).filter(

        User.username == data.new_username,

        User.id != admin.id

    ).first()

    if username_exist:

        raise HTTPException(

            status_code=400,

            detail="Username already exists."

        )

    admin.username = data.new_username

    admin.password = hash_password(

        data.new_password

    )

    admin.updated_at = datetime.datetime.now()

    db.commit()

    return {

        "message": "Administrator credentials updated successfully."

    }
    

@router.post("/admin_create_registration_team_user")
def admin_create_registration_team_user(

    data: AdminCreateRegistrationTeamSchema,

    db: Session = Depends(get_db)

):

    # ======================================================
    # VERIFY ADMIN
    # ======================================================

    verify_admin(

        db,

        data.admin_username

    )

    # ======================================================
    # USERNAME VALIDATION
    # ======================================================

    username_exist = db.query(User).filter(

        User.username == data.username

    ).first()

    if username_exist:

        raise HTTPException(

            status_code=400,

            detail="Username already exists."

        )

    # ======================================================
    # EMAIL VALIDATION
    # ======================================================

    email_exist = db.query(User).filter(

        User.email == data.email

    ).first()

    if email_exist:

        raise HTTPException(

            status_code=400,

            detail="Email already exists."

        )

    # ======================================================
    # CONTACT NUMBER VALIDATION
    # ======================================================

    contact_exist = db.query(User).filter(

        User.contact_number == data.contact_number

    ).first()

    if contact_exist:

        raise HTTPException(

            status_code=400,

            detail="Contact number already exists."

        )
        
        

    # ======================================================
    # USERNAME FORMAT VALIDATION
    # ======================================================

    if len(data.username) < 5:

        raise HTTPException(

            status_code=400,

            detail="Username must be at least 5 characters."

        )

    # ======================================================
    # PASSWORD VALIDATION
    # ======================================================

    if len(data.password) < 8:

        raise HTTPException(

            status_code=400,

            detail="Password must be at least 8 characters."

        )

    # ======================================================
    # CONTACT NUMBER VALIDATION
    # ======================================================

    if len(data.contact_number) < 11:

        raise HTTPException(

            status_code=400,

            detail="Invalid contact number."

        )

    # ======================================================
    # CALCULATE AGE
    # ======================================================

    user_age = calculate_registration_age(

        data.birthday

    )

    # ======================================================
    # CREATE REGISTRATION TEAM ACCOUNT
    # ======================================================

    new_user = User(

        fname=data.fname,

        mname=data.mname,

        lname=data.lname,

        age=user_age,

        birthday=data.birthday,

        address=data.address,

        email=data.email,

        sex=data.sex,

        local_church=data.local_church,

        contact_number=data.contact_number,

        sector=data.sector,

        username=data.username,

        password=hash_password(

            data.password

        ),

        role="Registration Team",

        created_at=datetime.datetime.now(),

        updated_at=datetime.datetime.now()

    )

    db.add(new_user)

    db.commit()

    db.refresh(new_user)

    return {

        "message": "Registration Team account created successfully.",

        "user": {

            "user_id": new_user.id,

            "fullname": f"{new_user.fname} {new_user.mname} {new_user.lname}".strip(),

            "username": new_user.username,

            "email": new_user.email,

            "role": new_user.role,

            "age": new_user.age,

            "sector": new_user.sector,

            "local_church": new_user.local_church

        }

    }






@router.get("/admin_view_registration_team_users")
def admin_view_registration_team_users(

    admin_username: str,

    db: Session = Depends(get_db)

):

    verify_admin(

        db,

        admin_username

    )

    users = db.query(User).filter(

        User.role == "Registration Team"

    ).all()

    return [

        {

            "id":user.id,

            "fullname":f"{user.fname} {user.mname} {user.lname}",

            "username":user.username,

            "email":user.email,

            "sector":user.sector,

            "local_church":user.local_church,

            "contact_number":user.contact_number

        }

        for user in users

    ]
