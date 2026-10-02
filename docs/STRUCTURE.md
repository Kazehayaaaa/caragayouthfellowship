# Project Structure

How the CYF Registration System is organized, how a request flows through it,
and where to make common changes. For setup and running instructions, see the
[README](../README.md).

The backend used to be one 25,700-line `main.py`, with 40 HTML files in the project
root. It is now split into an `app/` package (Python) and a `web/` folder
(everything the browser loads). Every URL and API stayed the same.

---

## At a glance

```
Registration_System_CYF/
├── main.py                  Entry point: `uvicorn main:app` (one line, imports app/main.py)
├── app/                     Backend (FastAPI)
│   ├── main.py              Builds the app: mounts, middleware, routers
│   ├── config.py            Settings from .env, project paths
│   ├── database.py          Database engine, sessions, get_db
│   ├── models.py            Database tables
│   ├── schemas.py           Request/response shapes
│   ├── security.py          Passwords and admin checks
│   ├── middleware.py        Login protection for admin/team pages
│   ├── migrations.py        Small database updates run at startup
│   ├── services/            Business logic shared by several routers
│   └── routers/             API endpoints and page URLs, one file per area
├── web/                     Frontend (served as-is)
│   ├── site/                Public website
│   ├── admin/               Admin pages
│   ├── team/                Registration-team pages (*_rt)
│   ├── assets/              CSS, JavaScript, images, favicon
│   └── sitemap.xml
├── uploads/                 Source copies of uploaded images
├── registration_system.db   Copy of the database
├── requirements.txt
└── README.md
```

---

## How a request is handled

```
Browser
  │
  ▼
main.py ──► app/main.py (FastAPI app)
              │
              ├─ Session middleware        reads the login cookie (cyf_session)
              ├─ Auth middleware           app/middleware.py
              │     └─ admin/team page URLs without the right role → redirect to /login.html
              ├─ CORS middleware
              │
              ├─ /assets/...   → files in web/assets/
              ├─ /uploads/...  → files in /app/data/uploads/
              │
              └─ routers (checked in order)
                    ├─ routers/pages.py    page URL → HTML file in web/
                    └─ routers/*.py        API endpoint → services → models → database
```

- **Pages:** `/home.html` is served by `routers/pages.py` from
  `web/site/home.html`. The browser then calls API endpoints such as
  `/event_participant_count` with `fetch()`.
- **API endpoints** read and write the database through the models, and use
  `services/` for shared logic such as sending emails or assigning tiers.

---

## The `app/` package

### Core modules

| File | What it holds | Change it when… |
|---|---|---|
| `config.py` | Values from `.env` (PayMongo, Gmail, session settings, contact email), `BASE_DIR` (project root) and `WEB_DIR` (`web/`) | You add a new setting or secret |
| `database.py` | `DATABASE_URL` (always `/app/data/registration_system.db`), `engine`, `SessionLocal`, `Base`, and `get_db` (the per-request database session) | You change the database location or type |
| `models.py` | Every database table as a SQLAlchemy class: `User`, `Event`, `Participant`, `Staff`, `Chaperone`, `Payment`, `CashSponsorship`, `StoreItem`, … | You add or change a table or column |
| `schemas.py` | Pydantic classes that validate request bodies and shape responses | An endpoint accepts or returns new fields |
| `security.py` | Password hashing (`hash_password`, `verify_password`), `require_admin_session`, `verify_admin`, `create_default_admin` | You change how logins or admin checks work |
| `middleware.py` | `ADMIN_PROTECTED_PAGES`, `REGISTRATION_PROTECTED_PAGES` and the middleware that redirects visitors without the right role | You add a page that needs a login |
| `migrations.py` | Functions that add missing columns/tables to existing databases; `app/main.py` runs them at startup | You add a column that existing databases don't have yet |
| `main.py` | Creates the app and wires everything up in a fixed order (see below) | You add a new router or middleware |

### `services/`: shared business logic

Code used by more than one router, or not tied to one URL.

| File | What it does |
|---|---|
| `email.py` | Sends email through the Gmail API, and builds every system email: registration and payment confirmations, store receipts, sponsorship emails, the contact form |
| `qr.py` | Generates participant QR codes |
| `registration.py` | Registration rules: phase (early-bird / walk-in), duplicate checks, registration numbers, age calculation, questionnaire scoring and tier assignment |
| `sponsorship.py` | Sponsorship tiers, the finding-sponsor queue (`process_finding_sponsor_queue_logic`), cash donation totals, and the manual-sponsor on/off setting |

### `routers/`: endpoints by area

Each file creates `router = APIRouter()` and defines its endpoints with
`@router.get(...)`, `@router.post(...)` and so on. `app/main.py` includes them all.

| File | Endpoints | Covers |
|---|---:|---|
| `pages.py` | 46 URLs | Which URL serves which HTML file; old About/Contact URLs redirect to home |
| `auth.py` | 4 | Log in, log out, and the two role landing endpoints (`/admin/dashboard`, `/registration/dashboard`) |
| `admin.py` | 3 | Change admin credentials, create and list registration-team accounts |
| `events.py` | 9 | Create, update, archive, restore and list events; the current active event |
| `participants.py` | 15 | Register, search, filter, update and archive participants; complete online registration |
| `questionnaire.py` | 7 | Questionnaire answers, rules agreement, score recalculation, evaluations |
| `staff.py` | 7 | Event staff records |
| `chaperones.py` | 5 | Chaperone records |
| `payments.py` | 8 | Create PayMongo payments, participant payment status, payment lists |
| `webhooks.py` | 2 | PayMongo webhook: confirms payments and updates records |
| `sponsorships.py` | 11 | Cash and item sponsorships, sponsorship inventory, sponsor dashboard stats |
| `manual_sponsor.py` | 6 | Admin tools for manually matching sponsors to participants |
| `store.py` | 9 | Store items, purchases, image upload |
| `registration_items.py` | 8 | Registration add-ons (t-shirt, lanyard, …) |
| `dashboards.py` | 6 | Dashboard totals, the dashboard overview, reports data |
| `contact.py` | 1 | Contact form |

### Import direction

Dependencies only point downward, so there are no circular imports:

```
routers/*   ──►  services/*  ──►  models, schemas  ──►  database  ──►  config
    │                                  ▲
    └──────────────────────────────────┘   (routers also use models/schemas/security directly)
```

- Routers never import from other routers. Logic that two routers both need
  belongs in `services/`.
- Imports are explicit, for example `from app.models import Participant`, so
  every file lists what it depends on.

### Startup order (`app/main.py`)

The order matches the original single-file app and matters:

1. Create the app
2. Mount `/uploads` (from `/app/data/uploads`)
3. Add CORS
4. Run the startup migrations
5. Mount `/assets` (from `web/assets`)
6. Register the auth middleware
7. Add the session middleware. It must come after the auth middleware, so that
   it wraps it and the session is available when the auth check runs.
8. Include the routers in their original order, so URL matching is unchanged

---

## The `web/` folder

Everything the browser loads. Files are served unchanged, with no build step.

| Folder | Contents | Who can open it |
|---|---|---|
| `site/` | `home`, `store`, `register`, `sponsor`, `cash-sponsor`, `item-sponsor`, `payment`, `login`, `privacy`, `terms` | Everyone |
| `admin/` | `admin_dashboard` plus 13 admin pages: events, participants, staff, chaperones, store items, sponsors, payments, reports, … | Admin role |
| `team/` | `registration_dashboard` plus the `*_rt` versions of the admin pages | Registration Team role |
| `assets/` | Shared CSS, JS and images (table below) | Everyone |

**URLs don't include the folder.** `web/admin/staff.html` is still opened at
`/staff.html`; `routers/pages.py` maps each URL to its file.

### Shared assets (`web/assets/`)

| File | Used by |
|---|---|
| `styles.css` | Public site design system: colors, fonts, header, footer, buttons (served at `/styles.css`) |
| `site.js` | Public site mobile menu |
| `admin-theme.css` | All admin/team pages: palette, sidebar, top bar, cards, tables, buttons |
| `admin-shell.js` | All admin/team pages: profile chip, settings link, mobile sidebar |
| `dashboard.css`, `dashboard.js` | The two dashboards (charts, cards, activity feed) |
| `auth.js` | Logout on admin/team pages (served at `/auth.js`) |
| `cyf-logo.png`, `favicon.png` | Logo and browser icon (`favicon.png` is also the email logo) |
| `hero-bg.jpg`, `dashboard-banner.jpg` | Home page hero and dashboard banner photos |

Admin pages load these files with a version tag, for example
`/assets/admin-theme.css?v=20260926`. **When you change a shared admin file,
update that tag** so browsers fetch the new version instead of a cached copy.

---

## Common tasks

**Add a public page**
1. Create `web/site/newpage.html`. Copy the `<head>`, header and footer from an existing public page.
2. In `app/routers/pages.py`, add `"/newpage.html": (PUBLIC, "newpage.html", None)` to `PAGES`, and add the URL to `_ORDER`.

**Add an admin page**
1. Create `web/admin/newpage.html`, starting from an existing admin page so it has the sidebar and theme links.
2. Register it in `pages.py` with the `ADMIN` folder.
3. Add `"/newpage.html"` to `ADMIN_PROTECTED_PAGES` in `app/middleware.py`.
4. Add a link to it in the sidebar of the admin pages.

**Add an API endpoint**
1. Add it to the router file for that area, e.g. `app/routers/events.py`.
2. If it needs a request body, add a schema to `app/schemas.py`.
3. If the logic is shared, put it in `app/services/` and import it.
4. For a new area, create `app/routers/newarea.py` with `router = APIRouter()` and add the module to the list in `app/main.py`.

**Add a database column**
1. Add the column to the model in `app/models.py`.
2. Add a migration in `app/migrations.py` that adds the column when it's missing, and call it from `app/main.py` with the other migrations.

**Change an email**
Edit the matching `send_*_email` function in `app/services/email.py`.

---

## Things to know

- **The app always uses `/app/data`.** The database (`/app/data/registration_system.db`)
  and uploaded files (`/app/data/uploads`) live outside the project; on Windows
  that's `C:\app\data`. The `registration_system.db` and `uploads/` in the
  repository are copies.
- **Admin and team pages are near-duplicates.** Each admin page has a `*_rt`
  version for the Registration Team. A fix usually needs to go into both files.
- **Some files are still large.** `payments.py`, `webhooks.py` and
  `sponsorships.py` are about 3,000 lines each because individual functions in
  them are very long. `migrations.py` includes old commented-out migrations kept
  for reference.
- **Login checks cover the pages, not most APIs.** The middleware protects
  admin/team HTML pages, but most API endpoints don't check the session yet.
  `/dashboard_overview` and the `/admin/manual-sponsor/*` endpoints do. New
  admin endpoints should use `require_admin_session` from `app/security.py`.
