"""Routes: contact."""

from fastapi import HTTPException
from fastapi import APIRouter

from app.schemas import (
    ContactRequest,
)
from app.services.email import (
    send_contact_email,
)

router = APIRouter()

# ==========================================================
# CONTACT API
# ==========================================================

@router.post("/contact")
async def contact_us(
    contact: ContactRequest
):

    try:

        send_contact_email(
            contact
        )

        return {
            "success": True,
            "message": (
                "Your message has been sent successfully."
            )
        }


    except Exception as error:

        print(
            "CONTACT EMAIL ERROR:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to send your message. "
                "Please try again later."
            )
        )
