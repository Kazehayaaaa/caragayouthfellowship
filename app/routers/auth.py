"""Routes: auth."""

from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
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
    LoginResponseSchema,
    LoginSchema,
)
from app.security import (
    verify_password,
)

router = APIRouter()

    
# ======================================================
# AUTHENTICATION
# ======================================================

@router.post(
    "/auth_login_user",
    response_model=LoginResponseSchema
)
def auth_login_user(
    login: LoginSchema,
    request: Request,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(

        User.username == login.username

    ).first()

    if not user:

        raise HTTPException(

            status_code=401,

            detail="Invalid username or password."

        )

    if not verify_password(

        login.password,

        user.password

    ):

        raise HTTPException(

            status_code=401,

            detail="Invalid username or password."

        )

    user.last_login = datetime.datetime.now()

    db.commit()

    
    request.session.clear()
    request.session["user"] = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
    }

    fullname = f"{user.fname} {user.lname}"

    if user.role == "Admin":

        return {

            "message": "Login Successful",

            "role": user.role,

            "redirect": "/admin/dashboard",

            "fullname": fullname,

            "username": user.username

        }

    if user.role == "Registration Team":

        return {

            "message": "Login Successful",

            "role": user.role,

            "redirect": "/registration/dashboard",

            "fullname": fullname,

            "username": user.username

        }

    raise HTTPException(

        status_code=403,

        detail="Account role is invalid."

    )
    
@router.post("/auth_logout_user")
def auth_logout_user(
    request: Request
):
    session_user = request.session.get("user") or {}
    username = session_user.get("username")
    request.session.clear()
    return {
        "message": "Logout Successful",
        "username": username
    }

# ======================================================
# USERS DASHBOARD
# ======================================================
    
    
@router.get("/admin/dashboard")
def dashboard_admin_home():

    return {

        "dashboard": "Admin Dashboard"

    }
    

@router.get("/registration/dashboard")
def dashboard_registration_team_home():

    return {

        "dashboard": "Registration Team Dashboard"

    }
