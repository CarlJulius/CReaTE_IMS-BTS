import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import app
from database.models import db

def migrate():
    with app.app_context():
        with db.engine.connect() as conn:
            from sqlalchemy import text

            # SQLite doesn't support ADD CONSTRAINT or ENUM
            # Use simple types instead

            # Add borrow_id column
            try:
                conn.execute(text("""
                    ALTER TABLE reports 
                    ADD COLUMN borrow_id INTEGER REFERENCES borrow_tracker(borrow_id)
                """))
                print("✓ Added borrow_id to reports")
            except Exception as e:
                print(f"⚠ borrow_id: {e}")

            # Add report_type column
            # SQLite has no ENUM — use TEXT with a default instead
            try:
                conn.execute(text("""
                    ALTER TABLE reports 
                    ADD COLUMN report_type TEXT NOT NULL DEFAULT 'damaged'
                """))
                print("✓ Added report_type to reports")
            except Exception as e:
                print(f"⚠ report_type: {e}")

            # SQLite doesn't support MODIFY COLUMN at all
            # The 'lost' condition will still work since SQLite 
            # doesn't enforce enums — it stores whatever string you give it
            print("✓ Skipping inventory_condition enum update (SQLite ignores enum constraints)")

            conn.commit()
            print("Migration complete!")

if __name__ == '__main__':
    migrate()