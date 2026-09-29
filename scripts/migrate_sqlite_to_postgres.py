"""Copy a SQLite registration_system.db into a Postgres database (e.g. Supabase).

Usage (from the project root, with the virtual environment active):

    python scripts/migrate_sqlite_to_postgres.py path\\to\\registration_system.db "postgresql://..."

or, with DATABASE_URL set in .env:

    python scripts/migrate_sqlite_to_postgres.py path\\to\\registration_system.db

- Creates the full schema in Postgres (same code the app runs at startup).
- Copies every table, keeping all ids, then resets the id counters.
- Refuses to run if the target already has data (pass --replace to wipe it first).
- Refuses to drop any column that holds data but doesn't exist in the models.
- Prints a row-count check for every table at the end.

The SQLite file is only read, never changed.
"""

import argparse
import datetime
import os
import sqlite3
import sys

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("sqlite_path", help="path to the source registration_system.db")
parser.add_argument(
    "database_url", nargs="?",
    help="target Postgres connection string (default: DATABASE_URL from .env)",
)
parser.add_argument("--replace", action="store_true", help="delete existing rows in the target first")
args = parser.parse_args()

if not os.path.isfile(args.sqlite_path):
    sys.exit(f"SQLite file not found: {args.sqlite_path}")

# The app reads its settings at import time, so point it at the target first.
if args.database_url:
    os.environ["DATABASE_URL"] = args.database_url
else:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    if not os.getenv("DATABASE_URL"):
        sys.exit("No connection string: pass it as an argument or set DATABASE_URL in .env.")
os.environ.setdefault("SESSION_SECRET_KEY", "migration-script")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, MetaData, Numeric, String, Text, text  # noqa: E402

from app.database import IS_SQLITE, Base, engine  # noqa: E402
from app.migrations import (  # noqa: E402
    create_missing_tables,
    ensure_manual_sponsor_tables,
    migrate_payment_receipt_sent,
    migrate_payment_store_order_id,
)

if IS_SQLITE:
    sys.exit("The target must be a Postgres connection string, not SQLite.")

# ----------------------------------------------------------------------
# 1. Schema
# ----------------------------------------------------------------------

print("Creating schema in Postgres...")
create_missing_tables()
migrate_payment_store_order_id()
migrate_payment_receipt_sent()
ensure_manual_sponsor_tables()

target = MetaData()
target.reflect(bind=engine)

source = sqlite3.connect(f"file:{args.sqlite_path}?mode=ro", uri=True)
source.row_factory = sqlite3.Row

source_tables = [
    r[0] for r in source.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
]

missing = [t for t in source_tables if t not in target.tables]
if missing:
    sys.exit(f"These tables exist in SQLite but not in the app's models: {missing}. Nothing was copied.")

# Tables referenced by foreign keys are copied first.
ordered = [t.name for t in target.sorted_tables if t.name in source_tables]

# Match the source's NOT NULL rules. Some live tables were created before a
# column was made required in the models, and already hold empty values;
# SQLite never enforced the newer rule, so the app keeps working exactly
# as it does on the live server.
relaxed = []
for name in ordered:
    source_nullable = {
        r[1] for r in source.execute(f'PRAGMA table_info("{name}")') if not r[3] and not r[5]
    }
    for column in target.tables[name].c:
        if column.name in source_nullable and not column.nullable and not column.primary_key:
            relaxed.append((name, column.name))

if relaxed:
    with engine.begin() as conn:
        for name, column in relaxed:
            conn.execute(text(f'ALTER TABLE "{name}" ALTER COLUMN "{column}" DROP NOT NULL'))
            print(f"  allowing empty values in {name}.{column} (as in the source database)")
    target = MetaData()
    target.reflect(bind=engine)

# ----------------------------------------------------------------------
# 2. Safety checks
# ----------------------------------------------------------------------

problems = []
fill_values = {}
for name in ordered:
    source_cols = [r[1] for r in source.execute(f'PRAGMA table_info("{name}")')]
    extra = [c for c in source_cols if c not in target.tables[name].c]
    for column in extra:
        filled = source.execute(f'SELECT COUNT(*) FROM "{name}" WHERE "{column}" IS NOT NULL').fetchone()[0]
        if filled:
            problems.append(f"{name}.{column} has {filled} values but no matching column in the models")
        else:
            print(f"  skipping empty legacy column {name}.{column}")

    for column in target.tables[name].c:
        if isinstance(column.type, String) and column.type.length and column.name in source_cols:
            too_long = source.execute(
                f'SELECT COUNT(*) FROM "{name}" WHERE LENGTH("{column.name}") > ?', (column.type.length,)
            ).fetchone()[0]
            if too_long:
                problems.append(f"{name}.{column.name}: {too_long} values longer than {column.type.length} characters")

    # Required columns an older source database doesn't have yet (the app
    # adds them at startup) get the model's default, as new rows would.
    for column in target.tables[name].c:
        if column.name in source_cols or column.nullable or column.primary_key or column.server_default:
            continue
        model_table = Base.metadata.tables.get(name)
        model_column = model_table.c.get(column.name) if model_table is not None else None
        default = getattr(model_column, "default", None)
        if default is not None and default.is_scalar:
            fill_values.setdefault(name, {})[column.name] = default.arg
            print(f"  {name}.{column.name} is missing in the source; using the default {default.arg!r}")
        else:
            problems.append(f"{name}.{column.name} is required but missing in the source and has no default")

with engine.connect() as conn:
    non_empty = [n for n in ordered if conn.execute(text(f'SELECT COUNT(*) FROM "{n}"')).scalar()]
if non_empty and not args.replace:
    problems.append(f"target already has data in {non_empty}; rerun with --replace to overwrite it")

if problems:
    print("\nNot copying anything, because:")
    for p in problems:
        print("  -", p)
    sys.exit(1)

# ----------------------------------------------------------------------
# 3. Copy
# ----------------------------------------------------------------------


def convert(value, column_type):
    if value is None:
        return None
    if isinstance(column_type, Boolean):
        return bool(int(value)) if not isinstance(value, bool) else value
    if isinstance(column_type, DateTime):
        return value if isinstance(value, datetime.datetime) else datetime.datetime.fromisoformat(str(value))
    if isinstance(column_type, Date):
        return value if isinstance(value, datetime.date) else datetime.date.fromisoformat(str(value)[:10])
    if isinstance(column_type, Integer):
        return int(value)
    if isinstance(column_type, (Float, Numeric)):
        return float(value)
    if isinstance(column_type, (String, Text)):
        return str(value)
    return value


with engine.begin() as conn:
    if args.replace:
        names = ", ".join(f'"{n}"' for n in ordered)
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))

    for name in ordered:
        table = target.tables[name]
        source_cols = {r[1] for r in source.execute(f'PRAGMA table_info("{name}")')}
        columns = [c for c in table.c if c.name in source_cols]
        rows = source.execute(f'SELECT * FROM "{name}"').fetchall()
        extra_values = fill_values.get(name, {})
        payload = [{**{c.name: convert(row[c.name], c.type) for c in columns}, **extra_values} for row in rows]
        if payload:
            conn.execute(table.insert(), payload)
        print(f"  {name:32} {len(payload):6} rows")

    # Point each id counter past the highest copied id.
    for name in ordered:
        table = target.tables[name]
        if "id" in table.c and isinstance(table.c.id.type, Integer):
            seq = conn.execute(text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": name}).scalar()
            if seq:
                conn.execute(text(
                    f'SELECT setval(:seq, COALESCE((SELECT MAX(id) FROM "{name}"), 0) + 1, false)'
                ), {"seq": seq})

# ----------------------------------------------------------------------
# 4. Verify
# ----------------------------------------------------------------------

print("\nRow counts (SQLite -> Postgres):")
ok = True
with engine.connect() as conn:
    for name in ordered:
        a = source.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        b = conn.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar()
        mark = "ok" if a == b else "MISMATCH"
        ok &= a == b
        print(f"  {name:32} {a:6} -> {b:6}  {mark}")

print("\nDone." if ok else "\nFinished with mismatches - check the lines above.")
sys.exit(0 if ok else 1)
