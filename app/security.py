"""Password hashing and admin checks."""

from passlib.context import CryptContext
from fastapi import HTTPException
from fastapi import Request
from sqlalchemy.orm import Session
import datetime

from app.database import (
    SessionLocal,
)
from app.models import (
    User,
)

        
# ======================================================
# PASSWORD HASHING
# ======================================================

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def hash_password(password: str):

    return pwd_context.hash(password)


def verify_password(
    plain_password,
    hashed_password
):

    return pwd_context.verify(
        plain_password,
        hashed_password
    )


def require_admin_session(request: Request):
    session_user = request.session.get("user") or {}
    if session_user.get("role") != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator access is required."
        )
    return session_user
        
        
        
        
        
        
        
        
        
















    

# ======================================================
# HELPER FUNCTIONS
# ======================================================

def verify_admin(db: Session, username: str):

    admin = db.query(User).filter(

        User.username == username,

        User.role == "Admin"

    ).first()

    if not admin:

        raise HTTPException(

            status_code=403,

            detail="Administrator account not found."

        )

    return admin


    
# ======================================================
# DEFAULT ADMIN
# ======================================================

def create_default_admin():

    db = SessionLocal()

    admin = db.query(User).filter(
        User.role == "Admin"
    ).first()

    if admin:

        db.close()

        return

    admin = User(

        fname="System",

        mname="",

        lname="Administrator",

        age=0,

        birthday=datetime.date.today(),

        address="",

        email="admin@system.local",

        sex="",

        local_church="",

        contact_number="",

        sector="Administrator",

        username="admin",

        password=hash_password("admin123"),

        role="Admin"
    )

    db.add(admin)

    db.commit()

    db.close()

    print("Default Admin Created")
