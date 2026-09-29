"""Small schema migrations run at startup for existing databases."""

from sqlalchemy import text

from app.database import (
    engine,
)

# def migrate_cash_sponsorship_cash_total_added():

#     with engine.connect() as connection:

#         # ====================================================
#         # CHECK EXISTING COLUMNS
#         # ====================================================

#         result = connection.execute(
#             text("""
#                 PRAGMA table_info(cash_sponsorships)
#             """)
#         )

#         columns = {
#             row[1]: row
#             for row in result
#         }

#         # ====================================================
#         # COLUMN DOES NOT EXIST
#         # ====================================================
#         #
#         # If the column does not exist at all, simply create
#         # it as INTEGER.
#         #
#         # ====================================================

#         if "cash_total_added" not in columns:

#             connection.execute(
#                 text("""
#                     ALTER TABLE cash_sponsorships
#                     ADD COLUMN cash_total_added
#                     INTEGER NOT NULL DEFAULT 0
#                 """)
#             )

#             connection.commit()

#             print(
#                 "Created cash_total_added INTEGER column."
#             )

#             return

#         # ====================================================
#         # EXISTING COLUMN
#         #
#         # SQLite cannot directly change BOOLEAN -> INTEGER.
#         #
#         # Rename the old column first.
#         # ====================================================

#         old_column = columns[
#             "cash_total_added"
#         ]

#         old_type = str(
#             old_column[2] or ""
#         ).upper()

#         print(
#             "Existing cash_total_added type:",
#             old_type
#         )

#         # ====================================================
#         # ALREADY INTEGER
#         # ====================================================

#         if old_type in [
#             "INTEGER",
#             "INT",
#             "BIGINT"
#         ]:

#             print(
#                 "cash_total_added is already INTEGER."
#             )

#             connection.commit()

#             return

#         # ====================================================
#         # RENAME OLD BOOLEAN COLUMN
#         # ====================================================

#         connection.execute(
#             text("""
#                 ALTER TABLE cash_sponsorships
#                 RENAME COLUMN cash_total_added
#                 TO cash_total_added_old
#             """)
#         )

#         # ====================================================
#         # CREATE CORRECT INTEGER COLUMN
#         # ====================================================

#         connection.execute(
#             text("""
#                 ALTER TABLE cash_sponsorships
#                 ADD COLUMN cash_total_added
#                 INTEGER NOT NULL DEFAULT 0
#             """)
#         )

#         # ====================================================
#         # BACKFILL OLD PAID CASH SPONSORSHIPS
#         # ====================================================
#         #
#         # Old records did not have cash_total_added.
#         #
#         # If an old sponsorship is already Paid, assume its
#         # donation amount has already been received.
#         #
#         # donation_amount is stored in centavos.
#         #
#         # Example:
#         #
#         # donation_amount = 50000
#         # cash_total_added = 500
#         #
#         # This prevents old paid sponsorships from being added
#         # again when the webhook is triggered.
#         #
#         # ====================================================

#         connection.execute(
#             text("""
#                 UPDATE cash_sponsorships
#                 SET cash_total_added =
#                     CAST(
#                         COALESCE(
#                             donation_amount,
#                             0
#                         ) / 100
#                         AS INTEGER
#                     )
#                 WHERE LOWER(
#                     COALESCE(
#                         payment_status,
#                         ''
#                     )
#                 ) = 'paid'
#             """)
#         )

#         # ====================================================
#         # OLD PENDING / FAILED RECORDS
#         #
#         # These should remain 0 because their donation has not
#         # been added to CashDonationTotal.
#         # ====================================================

#         connection.execute(
#             text("""
#                 UPDATE cash_sponsorships
#                 SET cash_total_added = 0
#                 WHERE LOWER(
#                     COALESCE(
#                         payment_status,
#                         ''
#                     )
#                 ) != 'paid'
#             """)
#         )

#         # ====================================================
#         # DROP OLD BOOLEAN COLUMN
#         # ====================================================
#         #
#         # SQLite versions supporting DROP COLUMN can remove it.
#         #
#         # ====================================================

#         try:

#             connection.execute(
#                 text("""
#                     ALTER TABLE cash_sponsorships
#                     DROP COLUMN cash_total_added_old
#                 """)
#             )

#         except Exception as e:

#             print(
#                 "WARNING: Could not drop old "
#                 "cash_total_added_old column:",
#                 repr(e)
#             )

#             print(
#                 "The old column can remain temporarily."
#             )

#         # ====================================================
#         # COMMIT
#         # ====================================================

#         connection.commit()

#         print(
#             "cash_total_added successfully migrated "
#             "to INTEGER."
#         )







# def migrate_staff_table():
#     inspector = inspect(engine)

#     columns = {
#         column["name"]
#         for column in inspector.get_columns("staff")
#     }

#     with engine.begin() as conn:

#         if "position" not in columns:
#             conn.execute(
#                 text("ALTER TABLE staff ADD COLUMN position VARCHAR")
#             )

#         if "sex" in columns:
#             pass

#         if "birthday" in columns:
#             pass

#         if "contact" in columns:
#             pass

#         if "local_church" in columns:
#             pass

#         if "sector" in columns:
#             pass


# # ============================================================
# # MIGRATE CASH SPONSORSHIP COLUMNS
# # ============================================================

# def migrate_cash_sponsorship_columns():

#     with engine.connect() as connection:

#         # ----------------------------------------------------
#         # CHECK EXISTING COLUMNS
#         # ----------------------------------------------------

#         result = connection.execute(
#             text(
#                 "PRAGMA table_info(cash_sponsorships)"
#             )
#         )

#         columns = [
#             row[1]
#             for row in result
#         ]

#         # ----------------------------------------------------
#         # ADD CASH TOTAL ADDED
#         # ----------------------------------------------------

#         if "cash_total_added" not in columns:

#             connection.execute(
#                 text("""
#                     ALTER TABLE cash_sponsorships
#                     ADD COLUMN cash_total_added
#                     BOOLEAN
#                     DEFAULT 0
#                     NOT NULL
#                 """)
#             )

#             connection.commit()

#         # ----------------------------------------------------
#         # IMPORTANT:
#         #
#         # OLD PAID SPONSORSHIPS
#         #
#         # These records existed before
#         # cash_total_added was created.
#         #
#         # Mark them as already added so the new
#         # sponsorship logic does NOT add them again.
#         # ----------------------------------------------------

#         connection.execute(
#             text("""
#                 UPDATE cash_sponsorships

#                 SET cash_total_added = 1

#                 WHERE
#                     LOWER(
#                         TRIM(
#                             COALESCE(
#                                 payment_status,
#                                 ''
#                             )
#                         )
#                     )

#                     IN (
#                         'paid',
#                         'success',
#                         'succeeded',
#                         'completed'
#                     )
#             """)
#         )

#         # ----------------------------------------------------
#         # OLD PENDING / FAILED RECORDS
#         #
#         # These should NOT be added to the cash total.
#         # ----------------------------------------------------

#         connection.execute(
#             text("""
#                 UPDATE cash_sponsorships

#                 SET cash_total_added = 0

#                 WHERE
#                     LOWER(
#                         TRIM(
#                             COALESCE(
#                                 payment_status,
#                                 ''
#                             )
#                         )
#                     )

#                     NOT IN (
#                         'paid',
#                         'success',
#                         'succeeded',
#                         'completed'
#                     )
#             """)
#         )

#         # ----------------------------------------------------
#         # COMMIT
#         # ----------------------------------------------------

#         connection.commit()




# # ============================================================
# # MIGRATE STORE ITEM TABLE
# # ============================================================

# def migrate_store_item_columns():

#     with engine.connect() as connection:

#         result = connection.execute(
#             text("PRAGMA table_info(store_items)")
#         )

#         columns = [
#             row[1]
#             for row in result
#         ]

#         # ----------------------------------------------------
#         # CATEGORY
#         # ----------------------------------------------------

#         if "category" not in columns:

#             connection.execute(
#                 text("""
#                     ALTER TABLE store_items
#                     ADD COLUMN category
#                     VARCHAR(50)
#                     NOT NULL
#                     DEFAULT 'others'
#                 """)
#             )

#         # ----------------------------------------------------
#         # SIZES
#         # ----------------------------------------------------

#         if "sizes" not in columns:

#             connection.execute(
#                 text("""
#                     ALTER TABLE store_items
#                     ADD COLUMN sizes
#                     TEXT
#                 """)
#             )

#         # ----------------------------------------------------
#         # IMAGE
#         # ----------------------------------------------------

#         if "image_url" not in columns:

#             connection.execute(
#                 text("""
#                     ALTER TABLE store_items
#                     ADD COLUMN image_url
#                     TEXT
#                 """)
#             )

#         # ----------------------------------------------------
#         # COMMIT
#         # ----------------------------------------------------

#         connection.commit()







    
    
# # # ======================================================
# # # MIGRATE PAYMENT TABLE
# # # ======================================================

# # def migrate_payment_columns():

# #     with engine.connect() as connection:

# #         result = connection.execute(
# #             text("PRAGMA table_info(payments)")
# #         )

# #         columns = [
# #             row[1]
# #             for row in result
# #         ]

# #         # ----------------------------------------------
# #         # PAYMENT TYPE
# #         # ----------------------------------------------

# #         if "payment_type" not in columns:

# #             connection.execute(
# #                 text("""
# #                     ALTER TABLE payments
# #                     ADD COLUMN payment_type
# #                     VARCHAR(30)
# #                     NOT NULL
# #                     DEFAULT 'Participant'
# #                 """)
# #             )

# #         # ----------------------------------------------
# #         # SPONSORSHIP TIER
# #         # ----------------------------------------------

# #         if "sponsorship_tier" not in columns:

# #             connection.execute(
# #                 text("""
# #                     ALTER TABLE payments
# #                     ADD COLUMN sponsorship_tier
# #                     VARCHAR(30)
# #                 """)
# #             )

# #         # ----------------------------------------------
# #         # SPONSOR ID
# #         # ----------------------------------------------

# #         if "sponsor_id" not in columns:

# #             connection.execute(
# #                 text("""
# #                     ALTER TABLE payments
# #                     ADD COLUMN sponsor_id
# #                     INTEGER
# #                 """)
# #             )

# #         # ----------------------------------------------
# #         # DESCRIPTION
# #         # ----------------------------------------------

# #         if "description" not in columns:

# #             connection.execute(
# #                 text("""
# #                     ALTER TABLE payments
# #                     ADD COLUMN description
# #                     VARCHAR(500)
# #                 """)
# #             )

# #         # ----------------------------------------------
# #         # CUSTOMER NAME
# #         # ----------------------------------------------

# #         if "customer_name" not in columns:

# #             connection.execute(
# #                 text("""
# #                     ALTER TABLE payments
# #                     ADD COLUMN customer_name
# #                     VARCHAR(150)
# #                 """)
# #             )

# #         # ----------------------------------------------
# #         # CUSTOMER CONTACT
# #         # ----------------------------------------------

# #         if "customer_contact" not in columns:

# #             connection.execute(
# #                 text("""
# #                     ALTER TABLE payments
# #                     ADD COLUMN customer_contact
# #                     VARCHAR(50)
# #                 """)
# #             )

# #         # ----------------------------------------------
# #         # CUSTOMER EMAIL
# #         # ----------------------------------------------

# #         if "customer_email" not in columns:

# #             connection.execute(
# #                 text("""
# #                     ALTER TABLE payments
# #                     ADD COLUMN customer_email
# #                     VARCHAR(255)
# #                 """)
# #             )

# #         connection.commit()


# # # ======================================================
# # # MAKE PARTICIPANT ID NULLABLE
# # #
# # # REQUIRED FOR STORE PAYMENTS
# # # ======================================================

# # def migrate_payment_participant_nullable():

# #     with engine.connect() as connection:

# #         # --------------------------------------------------
# #         # CHECK PAYMENTS TABLE
# #         # --------------------------------------------------

# #         result = connection.execute(
# #             text("""
# #                 PRAGMA table_info(payments)
# #             """)
# #         )

# #         columns = list(result)

# #         participant_column = None

# #         for column in columns:

# #             # PRAGMA table_info:
# #             #
# #             # column[0] = cid
# #             # column[1] = name
# #             # column[2] = type
# #             # column[3] = notnull
# #             # column[4] = default
# #             # column[5] = primary key

# #             if column[1] == "participant_id":

# #                 participant_column = column

# #                 break

# #         # --------------------------------------------------
# #         # PARTICIPANT COLUMN NOT FOUND
# #         # --------------------------------------------------

# #         if participant_column is None:

# #             raise RuntimeError(
# #                 "payments.participant_id column was not found."
# #             )

# #         # --------------------------------------------------
# #         # ALREADY NULLABLE
# #         # --------------------------------------------------

# #         if participant_column[3] == 0:

# #             print(
# #                 "Payment migration: "
# #                 "participant_id is already nullable."
# #             )

# #             return

# #         # --------------------------------------------------
# #         # GET ORIGINAL TABLE SQL
# #         # --------------------------------------------------

# #         result = connection.execute(
# #             text("""
# #                 SELECT sql
# #                 FROM sqlite_master
# #                 WHERE type = 'table'
# #                 AND name = 'payments'
# #             """)
# #         )

# #         row = result.fetchone()

# #         if not row or not row[0]:

# #             raise RuntimeError(
# #                 "Unable to read payments table definition."
# #             )

# #         original_sql = row[0]

# #         # --------------------------------------------------
# #         # RENAME ORIGINAL TABLE
# #         # --------------------------------------------------

# #         connection.execute(
# #             text("""
# #                 ALTER TABLE payments
# #                 RENAME TO payments_old
# #             """)
# #         )

# #         # --------------------------------------------------
# #         # CHANGE PARTICIPANT_ID
# #         #
# #         # Remove NOT NULL from participant_id only.
# #         # --------------------------------------------------

# #         new_sql = original_sql

# #         replacements = [

# #             (
# #                 '"participant_id" INTEGER NOT NULL',
# #                 '"participant_id" INTEGER'
# #             ),

# #             (
# #                 '`participant_id` INTEGER NOT NULL',
# #                 '`participant_id` INTEGER'
# #             ),

# #             (
# #                 'participant_id INTEGER NOT NULL',
# #                 'participant_id INTEGER'
# #             ),

# #             (
# #                 '"participant_id" INTEGER NOT NULL DEFAULT',
# #                 '"participant_id" INTEGER DEFAULT'
# #             ),

# #             (
# #                 '`participant_id` INTEGER NOT NULL DEFAULT',
# #                 '`participant_id` INTEGER DEFAULT'
# #             ),

# #             (
# #                 'participant_id INTEGER NOT NULL DEFAULT',
# #                 'participant_id INTEGER DEFAULT'
# #             )
# #         ]

# #         for old_text, new_text in replacements:

# #             new_sql = new_sql.replace(
# #                 old_text,
# #                 new_text
# #             )

# #         # --------------------------------------------------
# #         # CHANGE TABLE NAME
# #         # --------------------------------------------------

# #         new_sql = new_sql.replace(
# #             '"payments"',
# #             '"payments_new"',
# #             1
# #         )

# #         new_sql = new_sql.replace(
# #             '`payments`',
# #             '`payments_new`',
# #             1
# #         )

# #         # Handle unquoted CREATE TABLE payments
# #         if (
# #             "CREATE TABLE payments_new"
# #             not in new_sql
# #         ):

# #             new_sql = new_sql.replace(
# #                 "CREATE TABLE payments",
# #                 "CREATE TABLE payments_new",
# #                 1
# #             )

# #         # --------------------------------------------------
# #         # VERIFY PARTICIPANT_ID IS NOW NULLABLE
# #         # --------------------------------------------------

# #         if (
# #             'participant_id INTEGER NOT NULL'
# #             in new_sql
# #             or
# #             '"participant_id" INTEGER NOT NULL'
# #             in new_sql
# #             or
# #             '`participant_id` INTEGER NOT NULL'
# #             in new_sql
# #         ):

# #             # Roll back before raising the error.
# #             connection.rollback()

# #             raise RuntimeError(
# #                 "Unable to make payments.participant_id nullable. "
# #                 "The existing SQLite table definition has an "
# #                 "unexpected format."
# #             )

# #         # --------------------------------------------------
# #         # CREATE NEW PAYMENTS TABLE
# #         # --------------------------------------------------

# #         connection.execute(
# #             text(new_sql)
# #         )

# #         # --------------------------------------------------
# #         # GET COLUMN NAMES
# #         # --------------------------------------------------

# #         column_result = connection.execute(
# #             text("""
# #                 PRAGMA table_info(payments_old)
# #             """)
# #         )

# #         column_names = [
# #             row[1]
# #             for row in column_result
# #         ]

# #         if not column_names:

# #             connection.rollback()

# #             raise RuntimeError(
# #                 "Unable to read columns from payments_old."
# #             )

# #         column_list = ", ".join(
# #             f'"{column}"'
# #             for column in column_names
# #         )

# #         # --------------------------------------------------
# #         # COPY EXISTING PAYMENT DATA
# #         # --------------------------------------------------

# #         connection.execute(
# #             text(
# #                 f"""
# #                 INSERT INTO payments_new (
# #                     {column_list}
# #                 )
# #                 SELECT
# #                     {column_list}
# #                 FROM payments_old
# #                 """
# #             )
# #         )

# #         # --------------------------------------------------
# #         # REMOVE OLD TABLE
# #         # --------------------------------------------------

# #         connection.execute(
# #             text("""
# #                 DROP TABLE payments_old
# #             """)
# #         )

# #         # --------------------------------------------------
# #         # RENAME NEW TABLE
# #         # --------------------------------------------------

# #         connection.execute(
# #             text("""
# #                 ALTER TABLE payments_new
# #                 RENAME TO payments
# #             """)
# #         )

# #         connection.commit()

# #         print(
# #             "Payment migration: "
# #             "participant_id is now nullable."
# #         )


# # ======================================================
# # STAFF DATABASE MIGRATION
# # ======================================================

# def migrate_staff_columns():
#     """Add Staff.position and allow profile fields to remain empty for admin-created placeholders."""
#     from sqlalchemy import text

#     with engine.begin() as connection:
#         columns = connection.execute(text("PRAGMA table_info(staff)")).fetchall()
#         if not columns:
#             return

#         names = {row[1] for row in columns}
#         if "position" not in names:
#             connection.execute(text("ALTER TABLE staff ADD COLUMN position VARCHAR(100)"))

#         # SQLite cannot directly change NOT NULL columns. Rebuild only when the
#         # existing staff table still has the old NOT NULL profile columns.
#         info = connection.execute(text("PRAGMA table_info(staff)")).fetchall()
#         notnull = {row[1]: row[3] for row in info}
#         needs_rebuild = any(notnull.get(col) == 1 for col in [
#             "sex", "birthday", "contact", "local_church", "sector"
#         ])

#         if not needs_rebuild:
#             return

#         connection.execute(text("PRAGMA foreign_keys=OFF"))
#         connection.execute(text("DROP TABLE IF EXISTS staff_new"))
#         connection.execute(text("""
#             CREATE TABLE staff_new (
#                 id INTEGER PRIMARY KEY,
#                 event_id INTEGER NOT NULL,
#                 fname VARCHAR(100) NOT NULL,
#                 mname VARCHAR(100),
#                 lname VARCHAR(100) NOT NULL,
#                 position VARCHAR(100) NOT NULL DEFAULT '',
#                 sex VARCHAR(20),
#                 birthday DATE,
#                 contact VARCHAR(20),
#                 local_church VARCHAR(150),
#                 sector VARCHAR(100),
#                 is_archived INTEGER DEFAULT 0,
#                 created_at DATETIME,
#                 updated_at DATETIME
#             )
#         """))
#         connection.execute(text("""
#             INSERT INTO staff_new
#             (id,event_id,fname,mname,lname,position,sex,birthday,contact,local_church,sector,is_archived,created_at,updated_at)
#             SELECT id,event_id,fname,mname,lname,COALESCE(position,''),sex,birthday,contact,local_church,sector,is_archived,created_at,updated_at
#             FROM staff
#         """))
#         connection.execute(text("DROP TABLE staff"))
#         connection.execute(text("ALTER TABLE staff_new RENAME TO staff"))
#         connection.execute(text("CREATE INDEX IF NOT EXISTS ix_staff_id ON staff (id)"))
#         connection.execute(text("PRAGMA foreign_keys=ON"))


# # ======================================================
# # CREATE TABLES
# # ======================================================

# Base.metadata.create_all(
#     bind=engine
# )


# # ======================================================
# # RUN STAFF MIGRATION
# # ======================================================

# migrate_staff_columns()


# # ======================================================
# # RUN PAYMENT MIGRATIONS
# # ======================================================

# # migrate_payment_columns()


# # ======================================================
# # MAKE STORE PAYMENTS POSSIBLE
# # ======================================================

# # migrate_payment_participant_nullable()

# migrate_store_item_columns()

# migrate_cash_sponsorship_columns()

# migrate_staff_table()



# ============================================================
# MIGRATE PAYMENT TABLE
# ADD STORE ORDER ID
# ============================================================

def migrate_payment_store_order_id():

    with engine.connect() as connection:

        result = connection.execute(
            text("PRAGMA table_info(payments)")
        )

        columns = [
            row[1]
            for row in result
        ]

        # ----------------------------------------------------
        # STORE ORDER ID
        # ----------------------------------------------------

        if "store_order_id" not in columns:

            connection.execute(
                text("""
                    ALTER TABLE payments
                    ADD COLUMN store_order_id
                    VARCHAR(100)
                """)
            )

        # ----------------------------------------------------
        # COMMIT
        # ----------------------------------------------------

        connection.commit()







































# ============================================================
# MIGRATE PAYMENT TABLE
# ADD RECEIPT_SENT
# ============================================================

def migrate_payment_receipt_sent():
    with engine.connect() as connection:
        result = connection.execute(text("PRAGMA table_info(payments)"))
        columns = [row[1] for row in result]
        if "receipt_sent" not in columns:
            connection.execute(text("""
                ALTER TABLE payments
                ADD COLUMN receipt_sent BOOLEAN NOT NULL DEFAULT 0
            """))
        connection.commit()











# ============================================================
# MANUAL FINDING SPONSOR CONTROL / ALLOCATION TABLES
# ============================================================
# These tables are created with SQL so existing production
# databases do not require Base.metadata.create_all().
# ============================================================

def ensure_manual_sponsor_tables():
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS manual_sponsor_settings (
                id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1,
                updated_at DATETIME
            )
        """))

        connection.execute(text("""
            INSERT OR IGNORE INTO manual_sponsor_settings
                (id, enabled, updated_at)
            VALUES
                (1, 1, CURRENT_TIMESTAMP)
        """))

        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS manual_sponsor_allocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                tshirt_amount REAL NOT NULL DEFAULT 0,
                lanyard_amount REAL NOT NULL DEFAULT 0,
                previous_tshirt_status VARCHAR(20),
                previous_lanyard_status VARCHAR(20),
                previous_registration_status VARCHAR(30),
                previous_sponsor_review_status VARCHAR(30),
                sponsor_review_field VARCHAR(50),
                admin_username VARCHAR(100),
                status VARCHAR(20) NOT NULL DEFAULT 'Active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                cancelled_at DATETIME,
                FOREIGN KEY(participant_id) REFERENCES participants(id)
            )
        """))

        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS
            ix_manual_sponsor_allocations_participant
            ON manual_sponsor_allocations(participant_id)
        """))

        connection.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            ux_manual_sponsor_allocations_active_participant
            ON manual_sponsor_allocations(participant_id)
            WHERE status = 'Active'
        """))
