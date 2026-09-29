"""Protects the admin / registration-team HTML pages by session role."""

from fastapi.responses import RedirectResponse
from fastapi import Request
import urllib.error
import urllib.parse
import urllib.request

# ======================================================
# PROTECTED PAGE ROUTES
# ======================================================
ADMIN_PROTECTED_PAGES = {
    "/admin_dashboard.html", "/activity_event.html", "/team_event.html",
    "/program_event.html", "/finances_event.html", "/report_event.html",
    "/event_event.html", "/participants.html", "/staff.html",
    "/chaperone.html", "/store_items.html", "/sponsor_management.html",
    "/payment_management.html", "/report.html", "/admin/dashboard",
}

REGISTRATION_PROTECTED_PAGES = {
    "/registration_dashboard.html", "/activity_event_rt.html",
    "/team_event_rt.html", "/program_event_rt.html", "/finances_event_rt.html",
    "/report_event_rt.html", "/event_event_rt.html", "/participants_rt.html",
    "/staff_rt.html", "/chaperone_rt.html", "/store_items_rt.html",
    "/sponsor_management_rt.html", "/payment_management_rt.html",
    "/report_rt.html", "/registration/dashboard",
}

# ======================================================
# AUTHENTICATION MIDDLEWARE
# ======================================================

async def session_auth_middleware(request: Request, call_next):

    path = request.url.path.rstrip("/") or "/"

    required_role = (
        "Admin"
        if path in ADMIN_PROTECTED_PAGES
        else
        "Registration Team"
        if path in REGISTRATION_PROTECTED_PAGES
        else
        None
    )

    if required_role:

        session_user = request.session.get("user")

        if not session_user:

            next_url = request.url.path

            if request.url.query:
                next_url += "?" + request.url.query

            return RedirectResponse(
                url=(
                    "/login.html?next="
                    + urllib.parse.quote(next_url, safe="")
                ),
                status_code=303
            )

        if session_user.get("role") != required_role:

            if session_user.get("role") == "Admin":
                return RedirectResponse(
                    "/admin_dashboard.html",
                    status_code=303
                )

            if session_user.get("role") == "Registration Team":
                return RedirectResponse(
                    "/registration_dashboard.html",
                    status_code=303
                )

            request.session.clear()

            return RedirectResponse(
                "/login.html",
                status_code=303
            )

    return await call_next(request)
