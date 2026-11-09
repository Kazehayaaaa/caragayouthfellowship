"""Settings read from the environment (.env), and project paths."""

from dotenv import load_dotenv
import os

# Project root (this file lives in <root>/app/config.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")

# Load <root>/.env explicitly so it works no matter which folder
# the server is started from.
# NOTE: load_dotenv does NOT override variables already set in the
# shell/OS. If an old PAYMONGO_SECRET_KEY is exported there, it wins.
# Use load_dotenv(..., override=True) if you want .env to always win.
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

# Single source of truth for "which mode is this server in?".
# Used by payments.py (stale link detection) and webhooks.py
# (signature selection + livemode filtering).
PAYMONGO_LIVE = PAYMONGO_SECRET_KEY.startswith("sk_live_")

print("PAYMONGO MODE:", "LIVE" if PAYMONGO_LIVE else "TEST")


# ======================================================
# PAYMONGO WEBHOOK CONFIGURATION
# ======================================================

# Webhook secrets are per mode. In live mode this MUST be the secret of
# a webhook created in PayMongo's LIVE dashboard (not the test one).
PAYMONGO_WEBHOOK_SECRET = _clean_env("PAYMONGO_WEBHOOK_SECRET")

if not PAYMONGO_WEBHOOK_SECRET:
    print(
        "WARNING: PAYMONGO_WEBHOOK_SECRET is not set. "
        "All PayMongo webhooks will be rejected."
    )


# ======================================================
# ADMIN ACCESS FOR PAYMENT LISTS
# ======================================================

# Name of the session key that is set when an admin is logged in
# (for example "admin_id" or "user"). When set, the /payments/store,
# /payments/tshirt and /payments/lanyard endpoints require that key to
# be present in the session. When empty, they stay open (and a warning
# is printed) so existing behaviour does not break.
ADMIN_SESSION_KEY = _clean_env("ADMIN_SESSION_KEY")

if not ADMIN_SESSION_KEY:
    print(
        "WARNING: ADMIN_SESSION_KEY is not set. The /payments/* list "
        "endpoints are publicly readable."
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

if PAYMONGO_LIVE and not SESSION_HTTPS_ONLY:
    print(
        "WARNING: Live PayMongo key in use but SESSION_HTTPS_ONLY is not "
        "true. Set SESSION_HTTPS_ONLY=True when serving over HTTPS."
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