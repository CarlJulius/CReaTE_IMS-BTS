from flask import Flask, render_template, request, redirect, url_for, flash
from database.models import db, BorrowTracker, Student, Office, Faculty, Category, Inventory
from sqlalchemy import func, or_
from forms import StudentForm, LoginForm, SignupForm, BorrowForm, InventoryForm
from werkzeug.security import generate_password_hash, check_password_hash
import re


app = Flask(__name__)

#database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'


#initialize the database
db.init_app(app)

#create the database tables
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

################################################ for login ####################################################

#route for admin login
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    form = LoginForm()
    if form.validate_on_submit():
        faculty = Faculty.query.filter_by(username=form.username.data).first()
        if faculty and check_password_hash(faculty.password, form.password.data):
            return redirect(url_for('admin_dashboard'))
        else:   
            flash('Invalid username or password', 'danger')

    return render_template('admin-login.html', form=form)

#route for admin signup
@app.route('/admin/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        if form.password.data != form.comfirm_password.data:
            flash('Passwords do not match', 'danger')
            return render_template('admin-signup.html', form=form)

        existing_user = Faculty.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Username already exists', 'danger')
            return render_template('admin-signup.html', form=form)

        hashed_password = generate_password_hash(form.password.data)
        new_faculty = Faculty(username=form.username.data, password=hashed_password, Faculty_nm=form.username.data, Office_id=1)  # Assuming office_id is 1 for simplicity
        db.session.add(new_faculty)
        db.session.commit()
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('admin'))

    return render_template('admin-signup.html', form=form)
##########################################for login end ####################################################


############################################ for dashboard(admin) ####################################################
@app.route('/admin/dashboard', methods = ['GET', 'POST'])
def admin_dashboard():
    return render_template('admin-dashboard.html')

@app.route('/admin/borrowed-items', methods = ['GET', 'POST'])
def borrowed_items():
    return render_template('borrowed-items.html')

@app.route('/admin/inventory', methods = ['GET', 'POST'])
def inventory():
    add_form = InventoryForm()

    # If add form submitted, create new inventory item
    if add_form.validate_on_submit():
        cat_name = add_form.category.data.strip()
        category = Category.query.filter_by(Category_nm=cat_name).first()
        if not category:
            category = Category(Category_nm=cat_name)
            db.session.add(category)
            db.session.commit()

        new_inv = Inventory(
            Inventory_nm=add_form.name.data.strip(),
            Quantity=add_form.quantity.data,
            Inventory_condition=add_form.condition.data.strip(),
            Serial_number=add_form.serial.data.strip(),
            Faculty_id=1,
            Office_id=1,
            Category_id=category.Category_id
        )
        db.session.add(new_inv)
        db.session.commit()
        flash('Inventory item added.', 'success')
        return redirect(url_for('inventory'))

    # handle search query
    q = request.args.get('q', '').strip()
    if q:
        inv_query = Inventory.query.outerjoin(Category)
        # if q is integer, search by ID as well
        if q.isdigit():
            inv_query = inv_query.filter(or_(Inventory.InventoryID == int(q),
                                             Inventory.Inventory_nm.ilike(f"%{q}%"),
                                             Inventory.Serial_number.ilike(f"%{q}%"),
                                             Category.Category_nm.ilike(f"%{q}%")))
        else:
            inv_query = inv_query.filter(or_(Inventory.Inventory_nm.ilike(f"%{q}%"),
                                             Inventory.Serial_number.ilike(f"%{q}%"),
                                             Category.Category_nm.ilike(f"%{q}%")))
        inventories = inv_query.all()
    else:
        # Query all inventory items and compute available stock
        inventories = Inventory.query.all()
    items = []
    for inv in inventories:
        borrowed_qty = db.session.query(func.coalesce(func.sum(BorrowTracker.borrow_quantity), 0)).filter(
            BorrowTracker.InventoryID == inv.InventoryID,
            BorrowTracker.status == 'borrowed'
        ).scalar() or 0

        available = inv.Quantity - borrowed_qty
        items.append({
            'id': inv.InventoryID,
            'name': inv.Inventory_nm,
            'category': inv.category.Category_nm if getattr(inv, 'category', None) else '',
            'condition': inv.Inventory_condition,
            'serial': inv.Serial_number,
            'total': inv.Quantity,
            'available': available,
            'status': 'In Stock' if available > 0 else 'Out of Stock'
        })

    return render_template('manage-inventory.html', items=items, add_form=add_form, q=q)


@app.route('/admin/inventory/edit/<int:item_id>', methods=['POST'])
def edit_inventory(item_id):
    form = InventoryForm()
    if form.validate_on_submit():
        inv = Inventory.query.get_or_404(item_id)
        inv.Inventory_nm = form.name.data.strip()
        inv.Quantity = form.quantity.data
        inv.Inventory_condition = form.condition.data.strip()
        inv.Serial_number = form.serial.data.strip()
        cat_name = form.category.data.strip()
        category = Category.query.filter_by(Category_nm=cat_name).first()
        if not category:
            category = Category(Category_nm=cat_name)
            db.session.add(category)
            db.session.commit()
        inv.Category_id = category.Category_id
        db.session.commit()
        flash('Inventory item updated.', 'success')
    else:
        flash('Failed to update item. Check input.', 'danger')
    return redirect(url_for('inventory'))


@app.route('/admin/inventory/delete/<int:item_id>', methods=['POST'])
def delete_inventory(item_id):
    inv = Inventory.query.get_or_404(item_id)
    # remove associated borrow records first
    BorrowTracker.query.filter_by(InventoryID=inv.InventoryID).delete()
    db.session.delete(inv)
    db.session.commit()
    flash('Inventory item deleted.', 'success')
    return redirect(url_for('inventory'))

@app.route('/admin/requests', methods = ['GET', 'POST'])
def requests():
    return render_template('manage-request.html')

@app.route('/admin/reports', methods = ['GET', 'POST'])
def reports():
    return render_template('reports.html')

@app.route('/admin/office', methods = ['GET', 'POST'])
def office():
    return render_template('manage-office.html')

@app.route('/admin/faculty', methods = ['GET', 'POST'])
def faculty():
    return render_template('manage-faculty.html')

@app.route('/admin/category', methods = ['GET', 'POST'])
def category():
    return render_template('manage-category.html')


############################################for student dashboard ####################################################


@app.route('/student/information', methods=['GET', 'POST'])
def student_information():
    form = StudentForm()
    if form.validate_on_submit():
        # normalize ID to a consistent format like '191 - 00641'
        raw_id = form.id_number.data.strip()
        normalized = re.sub(r'\s*-\s*', ' - ', raw_id)

        # check if a student with this Student_number exists
        student = Student.query.filter_by(Student_number=normalized).first()
        if student:
            student.Student_nm = form.name.data
            flash('Student information updated.', 'success')
        else:
            student = Student(Student_nm=form.name.data, Student_number=normalized)
            db.session.add(student)
            flash('Student added successfully.', 'success')

        db.session.commit()
        return redirect(url_for('student_dashboard'))

    return render_template('student-information.html', form=form)

@app.route('/student/dashboard')
def student_dashboard():
    return render_template('student-dashboard.html')

@app.route('/student/borrow', methods=['GET', 'POST'])
def student_borrow():
    form = BorrowForm()
    if form.validate_on_submit():
        student = Student.query.filter_by(Student_number=form.student_id.data.strip()).first()
        inventory_item = Inventory.query.filter_by(InventoryID=form.inventory_id.data.strip()).first()

        if not student:
            flash('Student not found.', 'danger')
            return render_template('student-borrow.html', form=form)

        if not inventory_item:
            flash('Inventory item not found.', 'danger')
            return render_template('student-borrow.html', form=form)

        if inventory_item.Quantity < 1:
            flash('Item is currently unavailable.', 'warning')
            return render_template('student-borrow.html', form=form)

        borrow_record = BorrowTracker(
            borrow_quantity=1,
            Student_id=student.Student_id,
            InventoryID=inventory_item.InventoryID
        )
        inventory_item.Quantity -= 1

        db.session.add(borrow_record)
        db.session.commit()
        flash('Borrow request submitted successfully!', 'success')
        return redirect(url_for('student_dashboard'))

    return render_template('student-borrow.html', form=form)




if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)