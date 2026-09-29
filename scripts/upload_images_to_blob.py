"""Move existing store product images to Vercel Blob.

Run once after migrate_sqlite_to_postgres.py. For every store item whose
image is a local /uploads/... path, uploads the file to Vercel Blob and
saves the new https://... address on the item.

Usage (from the project root, with the virtual environment active):

    $env:BLOB_READ_WRITE_TOKEN = "vercel_blob_rw_..."
    python scripts/upload_images_to_blob.py path\\to\\uploads "postgresql://..."

The connection string can be left out when DATABASE_URL (and the token)
are set in .env.

path\\to\\uploads is a copy of the live server's /app/data/uploads folder
(the one that contains store/). Items whose file is missing are listed and
left unchanged.
"""

import mimetypes
import os
import sys

if len(sys.argv) not in (2, 3):
    sys.exit(__doc__)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

uploads_dir = sys.argv[1]
database_url = sys.argv[2] if len(sys.argv) == 3 else os.getenv("DATABASE_URL")

if not os.path.isdir(uploads_dir):
    sys.exit(f"Folder not found: {uploads_dir}")
if not database_url:
    sys.exit("No connection string: pass it as an argument or set DATABASE_URL in .env.")
if not os.getenv("BLOB_READ_WRITE_TOKEN"):
    sys.exit("Set BLOB_READ_WRITE_TOKEN first (Vercel → Storage → your Blob store → .env.local).")

os.environ["DATABASE_URL"] = database_url
os.environ.setdefault("SESSION_SECRET_KEY", "image-upload-script")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import StoreItem  # noqa: E402
from app.services.storage import _save_to_blob  # noqa: E402

db = SessionLocal()
moved, missing = 0, []

for item in db.query(StoreItem).filter(StoreItem.image_url.like("/uploads/%")).all():
    relative = item.image_url[len("/uploads/"):]
    path = os.path.join(uploads_dir, *relative.split("/"))
    if not os.path.isfile(path):
        missing.append(f"{item.id} {item.image_url}")
        continue

    content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        url = _save_to_blob(relative, f.read(), content_type)

    print(f"  item {item.id}: {item.image_url} -> {url}")
    item.image_url = url
    db.commit()
    moved += 1

db.close()

print(f"\nMoved {moved} image(s).")
if missing:
    print("These items' image files weren't found in the uploads folder (left unchanged):")
    for line in missing:
        print("  ", line)
