from app import app, db
from sqlalchemy import text

with app.app_context():
    with db.engine.connect() as conn:
        conn.execute(text('ALTER TABLE borrow_tracker ADD COLUMN contact_number VARCHAR(11)'))
        conn.commit()
        print('Done!')