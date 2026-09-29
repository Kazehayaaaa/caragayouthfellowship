# CYF Registration System

Registration, payments, sponsorship and store system for the Caraga Youth Fellowship.
FastAPI backend with plain HTML/CSS/JS pages, PayMongo payments and Gmail emails.
Runs on a normal server with a SQLite database, or on Vercel with Supabase Postgres and Vercel Blob
(see [Deploying to Vercel](#deploying-to-vercel)).

## Run it locally (Windows)

```powershell
# 1. Virtual environment and packages (first time only)
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt

# 2. Settings: create a .env file in the project root (first time only)
#    SESSION_SECRET_KEY is required; generate one with:
python -c "import secrets; print(secrets.token_hex(32))"

# 3. Data folder: by default the app uses /app/data (C:\app\data on Windows)
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
| `DATA_DIR` | Folder for the SQLite database and uploads. Default `/app/data`. |
| `DATABASE_URL` | Use a Postgres database instead of the SQLite file (Vercel). |
| `BLOB_READ_WRITE_TOKEN` | Store uploaded images in Vercel Blob instead of `DATA_DIR/uploads` (Vercel). |

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
    storage.py          Saves uploaded files (local folder, or Vercel Blob)
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
scripts/                One-time tools: copy SQLite data to Postgres, move images to Vercel Blob
uploads/                Source copies of uploaded images (the app reads DATA_DIR/uploads)
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
- **A database table:** `app/models.py`. New tables are created automatically at startup;
  for a new column on an existing table, add a migration in `app/migrations.py`.

## Accounts

Staff log in at `/login.html`. Accounts are stored in the database, and there is no sign-up page.

- **Registration Team accounts:** an admin creates them from **Staff → + Registration Team Account**.
- **Admin account:** change its username and password from **Settings** in the admin sidebar.

## Useful

- `ngrok http 8000` gives a temporary public link to your local server, which PayMongo webhooks need when you test payments locally.

## Deploying to Vercel

Vercel has no permanent disk, so on Vercel the database is Supabase Postgres and uploaded
images go to Vercel Blob. The same code still runs on a normal server with SQLite.

### 1. Create the storage (once)

1. **Supabase:** create a project at supabase.com. Then go to **Connect**, choose the
   **Transaction pooler**, and copy the URI (port `6543`), with your database password filled in.
2. **Vercel Blob:** in your Vercel project, go to **Storage → Create → Blob** and connect it to the project.
   Vercel adds `BLOB_READ_WRITE_TOKEN` to the project automatically.

### 2. Environment variables (Vercel → Settings → Environment Variables)

| Key | Value |
|---|---|
| `DATABASE_URL` | The Supabase transaction-pooler URI |
| `SESSION_SECRET_KEY` | A long random string (see "Run it locally") |
| `SESSION_HTTPS_ONLY` | `true` |
| `GMAIL_*`, `PAYMONGO_*` | Same values as the live server |

### 3. Copy the live data into Supabase (once)

Download the live server's `/app/data/registration_system.db` and its `/app/data/uploads` folder, then run:

```powershell
.venv\Scripts\activate
python scripts/migrate_sqlite_to_postgres.py path\to\registration_system.db "<supabase uri>"

$env:BLOB_READ_WRITE_TOKEN = "<token from Vercel → Storage → Blob → .env.local>"
python scripts/upload_images_to_blob.py path\to\uploads "<supabase uri>"
```

The first script creates all tables, copies every row (keeping ids), and checks the counts.
It won't overwrite a database that already has data unless you add `--replace`.
The second script moves the store product images to Blob and updates their addresses.

### 4. Deploy

Push to the branch Vercel deploys from, or run `vercel deploy`. Then update the PayMongo
webhook URL to `https://<your-vercel-domain>/webhooks/paymongo`.

### Notes

- `.vercelignore` keeps the local database, `uploads/`, `.env` and `.venv` out of the deployment.
- Vercel servers run on UTC, so times the app records with the server clock (`created_at`,
  payment times) are 8 hours behind Manila time.
