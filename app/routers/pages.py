"""Routes: HTML pages and site files served from web/.

URL → file mapping. Admin and registration-team pages are still protected by
app.middleware.session_auth_middleware (by URL), exactly as before.
"""

import os

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

from app.config import WEB_DIR

router = APIRouter()

PUBLIC = os.path.join(WEB_DIR, "public")
ADMIN = os.path.join(WEB_DIR, "admin")
TEAM = os.path.join(WEB_DIR, "team")
ASSETS = os.path.join(WEB_DIR, "assets")

# url path -> (folder, file, media type or None)
PAGES = {
    "/": (PUBLIC, "home.html", None),
    "/styles.css": (ASSETS, "styles.css", "text/css"),
    "/auth.js": (ASSETS, "auth.js", "application/javascript"),

    # Public site
    "/home.html": (PUBLIC, "home.html", None),
    "/store.html": (PUBLIC, "store.html", None),
    "/register.html": (PUBLIC, "register.html", None),
    "/sponsor.html": (PUBLIC, "sponsor.html", None),
    "/sponsor_rt.html": (TEAM, "sponsor_rt.html", None),
    "/cash-sponsor.html": (PUBLIC, "cash-sponsor.html", None),
    "/item-sponsor.html": (PUBLIC, "item-sponsor.html", None),
    "/payment.html": (PUBLIC, "payment.html", None),
    "/login.html": (PUBLIC, "login.html", None),

    # Dashboards
    "/admin_dashboard.html": (ADMIN, "admin_dashboard.html", None),
    "/registration_dashboard.html": (TEAM, "registration_dashboard.html", None),

    # Admin pages and their registration-team (_rt) versions
    "/activity_event.html": (ADMIN, "activity_event.html", None),
    "/activity_event_rt.html": (TEAM, "activity_event_rt.html", None),
    "/team_event.html": (ADMIN, "team_event.html", None),
    "/team_event_rt.html": (TEAM, "team_event_rt.html", None),
    "/program_event.html": (ADMIN, "program_event.html", None),
    "/program_event_rt.html": (TEAM, "program_event_rt.html", None),
    "/finances_event.html": (ADMIN, "finances_event.html", None),
    "/finances_event_rt.html": (TEAM, "finances_event_rt.html", None),
    "/report_event.html": (ADMIN, "report_event.html", None),
    "/report_event_rt.html": (TEAM, "report_event_rt.html", None),
    "/event_event.html": (ADMIN, "event_event.html", None),
    "/event_event_rt.html": (TEAM, "event_event_rt.html", None),
    "/participants.html": (ADMIN, "participants.html", None),
    "/participants_rt.html": (TEAM, "participants_rt.html", None),
    "/staff.html": (ADMIN, "staff.html", None),
    "/staff_rt.html": (TEAM, "staff_rt.html", None),
    "/chaperone.html": (ADMIN, "chaperone.html", None),
    "/chaperone_rt.html": (TEAM, "chaperone_rt.html", None),
    "/store_items.html": (ADMIN, "store_items.html", None),
    "/store_items_rt.html": (TEAM, "store_items_rt.html", None),
    "/sponsor_management.html": (ADMIN, "sponsor_management.html", None),
    "/sponsor_management_rt.html": (TEAM, "sponsor_management_rt.html", None),
    "/payment_management.html": (ADMIN, "payment_management.html", None),
    "/payment_management_rt.html": (TEAM, "payment_management_rt.html", None),
    "/report.html": (ADMIN, "report.html", None),
    "/report_rt.html": (TEAM, "report_rt.html", None),

    # Legal pages and site files
    "/privacy": (PUBLIC, "privacy.html", None),
    "/terms": (PUBLIC, "terms.html", None),
    "/sitemap.xml": (WEB_DIR, "sitemap.xml", None),
    "/favicon.png": (ASSETS, "favicon.png", "image/png"),
}

# About and Contact are sections of the home page; keep the old URLs working.
REDIRECTS = {
    "/contact.html": "/#contact",
    "/about.html": "/#about",
}


def _file_endpoint(path, media_type):
    def endpoint():
        if media_type:
            return FileResponse(path, media_type=media_type)
        return FileResponse(path)

    return endpoint


def _redirect_endpoint(target):
    def endpoint():
        return RedirectResponse(target, status_code=301)

    return endpoint


def _name(url):
    slug = url.strip("/").replace(".", "_").replace("-", "_") or "home"
    return "page_" + slug


# Registered in the same order as the original routes.
_ORDER = [
    "/", "/styles.css", "/auth.js", "/home.html", "/store.html", "/register.html",
    "/sponsor.html", "/sponsor_rt.html", "/cash-sponsor.html", "/item-sponsor.html",
    "/payment.html", "/contact.html", "/about.html", "/login.html",
    "/admin_dashboard.html", "/registration_dashboard.html",
    "/activity_event.html", "/activity_event_rt.html", "/team_event.html", "/team_event_rt.html",
    "/program_event.html", "/program_event_rt.html", "/finances_event.html", "/finances_event_rt.html",
    "/report_event.html", "/report_event_rt.html", "/event_event.html", "/event_event_rt.html",
    "/participants.html", "/participants_rt.html", "/staff.html", "/staff_rt.html",
    "/chaperone.html", "/chaperone_rt.html", "/store_items.html", "/store_items_rt.html",
    "/sponsor_management.html", "/sponsor_management_rt.html",
    "/payment_management.html", "/payment_management_rt.html",
    "/report.html", "/report_rt.html", "/privacy", "/terms", "/sitemap.xml", "/favicon.png",
]

for _url in _ORDER:
    if _url in REDIRECTS:
        _endpoint = _redirect_endpoint(REDIRECTS[_url])
    else:
        _folder, _file, _media = PAGES[_url]
        _endpoint = _file_endpoint(os.path.join(_folder, _file), _media)
    _endpoint.__name__ = _name(_url)
    router.add_api_route(_url, _endpoint, methods=["GET"])
