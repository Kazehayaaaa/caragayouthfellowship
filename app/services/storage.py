"""Where uploaded files are kept.

- BLOB_READ_WRITE_TOKEN set (Vercel): uploaded to Vercel Blob, and the
  public https://... URL is returned.
- Otherwise (server with a disk): written under DATA_DIR/uploads and the
  site-relative /uploads/... URL is returned, exactly as before.
"""

import os

import httpx

from app.config import BLOB_READ_WRITE_TOKEN, UPLOADS_DIR

_BLOB_API = "https://blob.vercel-storage.com"
_BLOB_API_VERSION = "10"


def save_upload(folder: str, filename: str, data: bytes, content_type: str) -> str:
    """Store a file and return the URL the site should use for it."""
    if BLOB_READ_WRITE_TOKEN:
        return _save_to_blob(f"{folder}/{filename}", data, content_type)
    return _save_to_disk(folder, filename, data)


def _save_to_disk(folder: str, filename: str, data: bytes) -> str:
    directory = os.path.join(UPLOADS_DIR, folder)
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), "wb") as buffer:
        buffer.write(data)
    return f"/uploads/{folder}/{filename}"


def _save_to_blob(pathname: str, data: bytes, content_type: str) -> str:
    response = httpx.put(
        f"{_BLOB_API}/",
        params={"pathname": pathname},
        headers={
            "authorization": f"Bearer {BLOB_READ_WRITE_TOKEN}",
            "x-api-version": _BLOB_API_VERSION,
            "access": "public",
            "x-content-type": content_type,
        },
        content=data,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["url"]
