import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import app
from database.models import db
from sqlalchemy import text

def migrate():
    with app.app_context():
        with db.engine.connect() as conn:

            # ── Student columns ──
            try:
                conn.execute(text("ALTER TABLE student ADD COLUMN pin TEXT"))
                print("✓ Added pin to student")
            except Exception as e:
                print(f"⚠ student pin: {e}")

            try:
                conn.execute(text("ALTER TABLE student ADD COLUMN email VARCHAR(120) UNIQUE"))
                print("✓ Added email to student")
            except Exception as e:
                print(f"⚠ student email: {e}")

            try:
                conn.execute(text("ALTER TABLE student ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 0"))
                print("✓ Added is_verified to student")
            except Exception as e:
                print(f"⚠ student is_verified: {e}")

            # ── Faculty columns ──
            try:
                conn.execute(text("ALTER TABLE faculty ADD COLUMN email VARCHAR(120) UNIQUE"))
                print("✓ Added email to faculty")
            except Exception as e:
                print(f"⚠ faculty email: {e}")

            try:
                conn.execute(text("ALTER TABLE faculty ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 0"))
                print("✓ Added is_verified to faculty")
            except Exception as e:
                print(f"⚠ faculty is_verified: {e}")

            try:
                conn.execute(text("ALTER TABLE faculty ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0"))
                print("✓ Added failed_attempts to faculty")
            except Exception as e:
                print(f"⚠ faculty failed_attempts: {e}")

            try:
                conn.execute(text("ALTER TABLE faculty ADD COLUMN locked_until DATETIME"))
                print("✓ Added locked_until to faculty")
            except Exception as e:
                print(f"⚠ faculty locked_until: {e}")

            # ── Reports columns ──
            try:
                conn.execute(text("ALTER TABLE reports ADD COLUMN borrow_id INTEGER REFERENCES borrow_tracker(borrow_id)"))
                print("✓ Added borrow_id to reports")
            except Exception as e:
                print(f"⚠ reports borrow_id: {e}")

            try:
                conn.execute(text("ALTER TABLE reports ADD COLUMN report_type TEXT NOT NULL DEFAULT 'damaged'"))
                print("✓ Added report_type to reports")
            except Exception as e:
                print(f"⚠ reports report_type: {e}")

            conn.commit()
            print("\nMigration complete!")

if __name__ == '__main__':
    migrate()