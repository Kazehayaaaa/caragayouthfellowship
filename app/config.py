"""Settings read from the environment (.env), and project paths."""

from dotenv import load_dotenv
import os

# Project root (this file lives in <root>/app/config.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")

load_dotenv()


# ======================================================
# PAYMONGO CONFIGURATION
# ======================================================

PAYMONGO_SECRET_KEY = os.getenv(
    "PAYMONGO_SECRET_KEY"
)

PAYMONGO_API_URL = os.getenv(
    "PAYMONGO_API_URL",
    "https://api.paymongo.com"
)


# ======================================================
# PAYMONGO WEBHOOK CONFIGURATION
# ======================================================

PAYMONGO_WEBHOOK_SECRET = os.getenv(
    "PAYMONGO_WEBHOOK_SECRET"
)


# ======================================================
# GMAIL SETTINGS
# ======================================================

GMAIL_CLIENT_ID = os.getenv(
    "GMAIL_CLIENT_ID",
    ""
).strip()


GMAIL_CLIENT_SECRET = os.getenv(
    "GMAIL_CLIENT_SECRET",
    ""
).strip()


GMAIL_REFRESH_TOKEN = os.getenv(
    "GMAIL_REFRESH_TOKEN",
    ""
).strip()


GMAIL_SENDER_EMAIL = os.getenv(
    "GMAIL_SENDER_EMAIL",
    ""
).strip()


GMAIL_FROM_NAME = os.getenv(
    "GMAIL_FROM_NAME",
    "Event Registration System"
).strip()


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]






# ==========================================================
# EMAIL CONFIGURATION
# ==========================================================

CONTACT_RECEIVER = (
    "caragayouthfellowship.official@gmail.com"
)







# ==========================================================
# GMAIL API EMAIL CONFIGURATION
# ==========================================================

# The authorized Gmail account is the sender.
# No custom domain and no Gmail App Password are required.

CONTACT_RECEIVER_EMAIL = (
    os.getenv("CONTACT_RECEIVER_EMAIL")
    or GMAIL_SENDER_EMAIL
)


# ======================================================
# SESSION MIDDLEWARE
# MUST BE REGISTERED AFTER THE AUTH MIDDLEWARE
# ======================================================

SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")

if not SESSION_SECRET_KEY:
    raise RuntimeError(
        "SESSION_SECRET_KEY environment variable is not set."
    )

SESSION_HTTPS_ONLY = (
    os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true"
)
