"""Settings read from the environment (.env), and project paths."""

from dotenv import load_dotenv
import os

# Project root (this file lives in <root>/app/config.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")

# Load <root>/.env explicitly so it works no matter which folder
# the server is started from.
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _clean_env(name, default=""):
    """Read an env var and strip whitespace, \\r and wrapping quotes."""

    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().strip('"').strip("'").strip()


# ======================================================
# PAYMONGO CONFIGURATION
# ======================================================

# Must be the SECRET key: sk_test_... (testing) or sk_live_... (live)
PAYMONGO_SECRET_KEY = _clean_env("PAYMONGO_SECRET_KEY")

PAYMONGO_API_URL = (
    _clean_env("PAYMONGO_API_URL", "https://api.paymongo.com")
    or "https://api.paymongo.com"
).rstrip("/")

if not PAYMONGO_SECRET_KEY.startswith(("sk_test_", "sk_live_")):
    print(
        "WARNING: PAYMONGO_SECRET_KEY is missing or is not a secret key "
        "(expected it to start with sk_test_ or sk_live_). "
        "PayMongo requests will fail with 401."
    )


# ======================================================
# PAYMONGO WEBHOOK CONFIGURATION
# ======================================================

PAYMONGO_WEBHOOK_SECRET = _clean_env("PAYMONGO_WEBHOOK_SECRET")


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

# ======================================================
# STORAGE
# DATABASE_URL picks the database:
#   - not set  → SQLite file in DATA_DIR (the original server setup)
#   - set      → e.g. a Supabase Postgres connection string (Vercel)
# DATA_DIR holds the SQLite file and local uploads (default /app/data).
# BLOB_READ_WRITE_TOKEN, when set, stores uploaded images in Vercel Blob
# instead of the local uploads folder.
# ======================================================

DATA_DIR = os.getenv("DATA_DIR", "/app/data")

UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or "sqlite:///" + os.path.join(DATA_DIR, "registration_system.db").replace("\\", "/")
)

BLOB_READ_WRITE_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN", "").strip()