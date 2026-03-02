from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class BorrowTracker(db.Model):
    __tablename__ = 'borrow_tracker'

    Borrow_id = db.Column(db.Integer, primary_key=True)
    Borrow_date = db.Column(db.Date, nullable=False)
    Return_date = db.Column(db.Date, nullable=True)

    borrow_quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default='borrowed', nullable=False)

    Student_id = db.Column(db.Integer, db.ForeignKey('student.Student_id'), nullable=False)
    InventoryID = db.Column(db.Integer, db.ForeignKey('inventory.InventoryID'), nullable=False)

    student = db.relationship('Student', backref='borrow_records')
    inventory = db.relationship('Inventory', backref='borrow_records')


class Student(db.Model):
    __tablename__ = 'student'

    Student_id = db.Column(db.Integer, primary_key=True)
    Student_nm = db.Column(db.String(100), nullable=False)


class Office(db.Model):
    __tablename__ = 'office'

    Office_id = db.Column(db.Integer, primary_key=True)
    Office_nm = db.Column(db.String(100), nullable=False)
    office_loc = db.Column(db.String(100), nullable=False)

    faculties = db.relationship('Faculty', backref='office', lazy=True)
    inventories = db.relationship('Inventory', backref='office', lazy=True)


class Faculty(db.Model):
    __tablename__ = 'faculty'

    Faculty_id = db.Column(db.Integer, primary_key=True)
    Faculty_nm = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

    Office_id = db.Column(db.Integer, db.ForeignKey('office.Office_id'), nullable=False)

    inventories = db.relationship('Inventory', backref='faculty', lazy=True)


class Category(db.Model):
    __tablename__ = 'category'

    Category_id = db.Column(db.Integer, primary_key=True)
    Category_nm = db.Column(db.String(100), nullable=False)

    inventories = db.relationship('Inventory', backref='category', lazy=True)


class Inventory(db.Model):
    __tablename__ = 'inventory'

    InventoryID = db.Column(db.Integer, primary_key=True)
    Inventory_nm = db.Column(db.String(100), nullable=False)

    Quantity = db.Column(db.Integer, nullable=False)
    Inventory_condition = db.Column(db.String(50), nullable=False)
    Serial_number = db.Column(db.String(100), unique=True, nullable=False)

    Faculty_id = db.Column(db.Integer, db.ForeignKey('faculty.Faculty_id'), nullable=False)
    Office_id = db.Column(db.Integer, db.ForeignKey('office.Office_id'), nullable=False)
    Category_id = db.Column(db.Integer, db.ForeignKey('category.Category_id'), nullable=False)