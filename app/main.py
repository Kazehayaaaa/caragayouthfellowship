"""CYF Registration System: FastAPI application.

Creates the app and wires everything up in the same order as the original
single-file main.py: mounts, CORS, startup migrations, the page-protection
middleware, sessions, then the routers.

Run from the project root with:  uvicorn main:app --reload
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import SESSION_HTTPS_ONLY, SESSION_SECRET_KEY, UPLOADS_DIR, WEB_DIR
from app.middleware import session_auth_middleware
from app.migrations import (
    create_missing_tables,
    ensure_manual_sponsor_tables,
    migrate_payment_receipt_sent,
    migrate_payment_store_order_id,
)
from app.routers import (
    admin,
    auth,
    chaperones,
    contact,
    dashboards,
    events,
    manual_sponsor,
    pages,
    participants,
    payments,
    questionnaire,
    registration_items,
    sponsorships,
    staff,
    store,
    webhooks,
)


# ======================================================
# APP CONFIGURATION
# ======================================================

app = FastAPI()


# ============================================================
# UPLOADED FILES
# Served from DATA_DIR/uploads when that folder exists (server setup).
# On Vercel there is no local uploads folder; images live in Vercel Blob.
# ============================================================

if os.path.isdir(UPLOADS_DIR):
    app.mount(
        "/uploads",
        StaticFiles(
            directory=UPLOADS_DIR
        ),
        name="uploads"
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================================================
# STARTUP SCHEMA SETUP
# New databases get every table from the models; existing databases
# only need these small column/table additions.
# ======================================================

create_missing_tables()

migrate_payment_store_order_id()

migrate_payment_receipt_sent()

ensure_manual_sponsor_tables()


# ============================================================
# SITE ASSETS (web/assets)
# ============================================================

app.mount(
    "/assets",
    StaticFiles(
        directory=os.path.join(WEB_DIR, "assets")
    ),
    name="assets"
)


# ======================================================
# AUTHENTICATION MIDDLEWARE
# ======================================================

app.middleware("http")(session_auth_middleware)


# ======================================================
# SESSION MIDDLEWARE
# MUST BE REGISTERED AFTER THE AUTH MIDDLEWARE
# ======================================================

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="cyf_session",
    max_age=60 * 60 * 8,
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
)


# ======================================================
# ROUTES
# Included in the order their routes first appeared in the
# original main.py, so request matching is unchanged.
# ======================================================

for module in (
    sponsorships,
    contact,
    pages,
    auth,
    admin,
    chaperones,
    staff,
    events,
    participants,
    questionnaire,
    payments,
    dashboards,
    webhooks,
    store,
    registration_items,
    manual_sponsor,
):
    app.include_router(module.router)
