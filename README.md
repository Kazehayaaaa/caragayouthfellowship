# CYF Registration System

Registration, payments, sponsorship and store system for the Caraga Youth Fellowship.
FastAPI backend with plain HTML/CSS/JS pages, SQLite database, PayMongo payments and Gmail emails.

## Run it locally (Windows)

```powershell
# 1. Virtual environment and packages (first time only)
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt

# 2. Settings: create a .env file in the project root (first time only)
#    SESSION_SECRET_KEY is required; generate one with:
python -c "import secrets; print(secrets.token_hex(32))"

# 3. Data folder: the app always uses /app/data (C:\app\data on Windows)
New-Item -ItemType Directory -Force C:\app\data\uploads\store
Copy-Item registration_system.db C:\app\data\      # skip if you already have a database there

# 4. Start the server
uvicorn main:app --reload
```

Open http://127.0.0.1:8000. Stop the server with **Ctrl + C**.

### `.env` settings

| Key | Needed for |
|---|---|
| `SESSION_SECRET_KEY` | **Required.** Signs login sessions. |
| `SESSION_HTTPS_ONLY` | Set to `true` in production (HTTPS). |
| `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_SENDER_EMAIL` | Sending emails (confirmations, receipts, contact form). |
| `PAYMONGO_SECRET_KEY`, `PAYMONGO_WEBHOOK_SECRET` | Online payments. |

`.env` is git-ignored. Never commit it.

## Project structure

For a full explanation of how the code is organized and how requests flow, see [docs/STRUCTURE.md](docs/STRUCTURE.md).

```
main.py                 Entry point for `uvicorn main:app` (imports app/main.py)
app/
  main.py               Creates the FastAPI app: mounts, middleware, routers
  config.py             Settings from .env and project paths
  database.py           Database engine, sessions, get_db
  models.py             Database tables (SQLAlchemy models)
  schemas.py            Request/response shapes (Pydantic)
  security.py           Password hashing and admin checks
  middleware.py         Login protection for admin / registration-team pages
  migrations.py         Small database updates run at startup
  services/
    email.py            Gmail sending and all email templates
    qr.py               Participant QR codes
    registration.py     Registration rules, scoring and tiers
    sponsorship.py      Sponsorship tiers and the finding-sponsor queue
  routers/              One file per area of the API
    pages.py            Which URL serves which HTML page
    auth.py  admin.py  events.py  participants.py  questionnaire.py
    staff.py  chaperones.py  payments.py  webhooks.py  sponsorships.py
    store.py  registration_items.py  dashboards.py  manual_sponsor.py  contact.py
web/
  public/               Public site: home, store, register, sponsor, payment, login, legal pages
  admin/                Admin pages (login required, Admin role)
  team/                 Registration-team pages, the *_rt versions (Registration Team role)
  assets/               CSS, JavaScript, images and favicon (served at /assets/...)
  sitemap.xml
uploads/                Source copies of uploaded images (the app reads /app/data/uploads)
registration_system.db  Copy of the database
```

### Where to change things

- **A page's content or look:** the HTML file in `web/public`, `web/admin` or `web/team`.
  Shared styles are in `web/assets/`: `styles.css` for the public site,
  `admin-theme.css` for admin pages, `dashboard.css` for the dashboards.
- **Add a new page:** put the file in `web/...` and add its URL to `PAGES` in `app/routers/pages.py`.
  If it needs a login, add the URL to `app/middleware.py`.
- **An API endpoint:** the matching file in `app/routers/`.
- **Email wording:** `app/services/email.py`.
- **A database table:** `app/models.py`, plus a migration in `app/migrations.py` for existing databases.

## Accounts

Staff log in at `/login.html`. Accounts are stored in the database, and there is no sign-up page.

- **Registration Team accounts:** an admin creates them from **Staff → + Registration Team Account**.
- **Admin account:** change its username and password from **Settings** in the admin sidebar.

## Useful

- `ngrok http 8000` gives a temporary public link to your local server, which PayMongo webhooks need when you test payments locally.
