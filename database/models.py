from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum
from datetime import datetime, timezone

db = SQLAlchemy()

class BorrowTracker(db.Model):
    __tablename__ = 'borrow_tracker'

    borrow_id = db.Column(db.Integer, primary_key=True)
    
    request_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    approve_date = db.Column(db.DateTime, nullable=True)
    borrow_date = db.Column(db.Date, nullable=True)
    return_date = db.Column(db.Date, nullable=True)
    remarks = db.Column(db.String(200), nullable=True)

    status = db.Column(
        Enum(
            'pending', 'approved', 'rejected', 
            'borrowed', 'returned', 'overdue', 
            name='borrow_status'
        ),
        default='pending',
        nullable=False
    )

    approved_by = db.Column(db.Integer, db.ForeignKey('faculty.faculty_id'), nullable=True, index = True)

    approver = db.relationship('Faculty', foreign_keys=[approved_by], backref='approved_borrows')

    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False, index = True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.inventory_id'), nullable=False, index = True)

    student = db.relationship('Student', backref='borrow_records')
    inventory = db.relationship('Inventory', backref='borrow_records')


class Student(db.Model):
    __tablename__ = 'student'
    student_id = db.Column(db.Integer, primary_key=True)
    student_nm = db.Column(db.String(100), nullable=False)
    student_number = db.Column(db.String(20), unique=True, nullable=False)
    student_year = db.Column(db.String(20), nullable=False)
    student_course = db.Column(db.String(50), nullable=False)


class Office(db.Model):
    __tablename__ = 'office'
    office_id = db.Column(db.Integer, primary_key=True)
    office_nm = db.Column(db.String(100), nullable=False)
    office_loc = db.Column(db.String(100), nullable=False)

    faculties = db.relationship('Faculty', back_populates='office')

    # CHANGED: uselist=False makes this a 1-to-1 relationship in Python
    # renamed to 'approver_config' to avoid confusion with the 'faculties' list
    approver_config = db.relationship('EquipmentApprover', back_populates='office', uselist=False)


class EquipmentApprover(db.Model):
    __tablename__ = 'equipment_approver'
    approver_id = db.Column(db.Integer, primary_key=True)

    # CHANGED: unique=True here ensures an office can only appear ONCE in this table
    office_id = db.Column(db.Integer, db.ForeignKey('office.office_id'), unique=True, nullable=False, index=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty.faculty_id'), nullable=False, index=True)

    office = db.relationship('Office', back_populates='approver_config')
    # Using back_populates for consistency
    faculty = db.relationship('Faculty', back_populates='approver_role')


class Faculty(db.Model):
    __tablename__ = 'faculty'
    faculty_id = db.Column(db.Integer, primary_key=True)
    faculty_nm = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    office_id = db.Column(db.Integer, db.ForeignKey('office.office_id'), nullable=False, index=True)

    office = db.relationship('Office', back_populates='faculties')
    
    # NEW: Link back to the approval role
    # uselist=False because a person is likely the head of only one office (or none)
    approver_role = db.relationship('EquipmentApprover', back_populates='faculty', uselist=False)
    
class Category(db.Model):
    __tablename__ = 'category'
    category_id = db.Column(db.Integer, primary_key=True)
    category_nm = db.Column(db.String(100), nullable=False)


class Inventory(db.Model):
    __tablename__ = 'inventory'

    inventory_id = db.Column(db.Integer, primary_key=True)
    inventory_nm = db.Column(db.String(100), nullable=False)

    inventory_desc = db.Column(db.String(200))
    inventory_condition = db.Column(
        Enum('functional', 'non-functional','under-maintenance','under-repair', name='condition_enum'),
        nullable=False
    )

    serial_number = db.Column(db.String(100), unique=True, nullable=False)

    is_available = db.Column(db.Boolean, default=True, nullable=False)

    office_id = db.Column(db.Integer, db.ForeignKey('office.office_id'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.category_id'), nullable=False, index=True)

    office = db.relationship('Office', backref='inventories')
    category = db.relationship('Category', backref='inventories')

class Reports(db.Model):
    __tablename__ = 'reports'
    report_id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.inventory_id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False, index=True)
    report_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    description = db.Column(db.String(200), nullable=False)

    inventory = db.relationship('Inventory', backref='reports')
    student = db.relationship('Student', backref='reports')


