from flask import Flask, render_template, request, redirect, url_for, flash
from database.models import db, BorrowTracker, Student, Office, Faculty, Category, Inventory
from sqlalchemy import func, or_
from forms import StudentForm, LoginForm, SignupForm, BorrowForm, InventoryForm, OfficeForm, CategoryForm, FacultyForm
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, UTC
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
            BorrowTracker.status == 'approved'
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

@app.route('/admin/requests')
def requests():
    pending_requests = BorrowTracker.query.filter_by(status='pending').all()
    return render_template('manage-request.html', requests=pending_requests)

from datetime import datetime

@app.route('/admin/requests/approve/<int:borrow_id>', methods=['POST'])
def approve_request(borrow_id):
    borrow = BorrowTracker.query.get_or_404(borrow_id)

    if borrow.status != 'pending':
        flash('Request already processed.', 'warning')
        return redirect(url_for('requests'))

    inventory = borrow.inventory

    if inventory.Quantity >= borrow.borrow_quantity:
        inventory.Quantity -= borrow.borrow_quantity
        borrow.status = 'approved'
        borrow.approve_date = datetime.now(timezone.utc)
        db.session.commit()
        flash('Request approved.', 'success')
    else:
        flash('Not enough stock.', 'danger')

    return redirect(url_for('requests'))

@app.route('/admin/requests/reject/<int:borrow_id>', methods=['POST'])
def reject_request(borrow_id):
    borrow = BorrowTracker.query.get_or_404(borrow_id)

    if borrow.status != 'pending':
        flash('Request already processed.', 'warning')
        return redirect(url_for('requests'))

    borrow.status = 'rejected'
    db.session.commit()

    flash('Request rejected.', 'info')
    return redirect(url_for('requests'))

@app.route('/admin/reports', methods = ['GET', 'POST'])
def reports():
    return render_template('reports.html')

@app.route('/admin/office', methods = ['GET', 'POST'])
def office():
    form = OfficeForm()

    # handle add form submission
    if form.validate_on_submit():
        new_office = Office(Office_nm=form.name.data.strip(), office_loc=form.location.data.strip())
        db.session.add(new_office)
        db.session.commit()
        flash('Office added.', 'success')
        return redirect(url_for('office'))

    # handle optional search
    q = request.args.get('q', '').strip()
    if q:
        offices = Office.query.filter(or_(Office.Office_nm.ilike(f"%{q}%"), Office.office_loc.ilike(f"%{q}%"))).all()
    else:
        offices = Office.query.all()

    items = []
    for off in offices:
        items.append({
            'id': off.Office_id,
            'name': off.Office_nm,
            'location': off.office_loc
        })

    return render_template('manage-office.html', items=items, add_form=form, q=q)


@app.route('/admin/office/edit/<int:office_id>', methods=['POST'])
def edit_office(office_id):
    form = OfficeForm()
    if form.validate_on_submit():
        off = Office.query.get_or_404(office_id)
        off.Office_nm = form.name.data.strip()
        off.office_loc = form.location.data.strip()
        db.session.commit()
        flash('Office updated.', 'success')
    else:
        flash('Failed to update office. Check input.', 'danger')
    return redirect(url_for('office'))


@app.route('/admin/office/delete/<int:office_id>', methods=['POST'])
def delete_office(office_id):
    off = Office.query.get_or_404(office_id)
    # Prevent deletion if there are inventories assigned to this office
    assigned_count = Inventory.query.filter_by(Office_id=off.Office_id).count()
    if assigned_count > 0:
        flash('Cannot delete office with assigned inventory.', 'danger')
        return redirect(url_for('office'))

    db.session.delete(off)
    db.session.commit()
    flash('Office deleted.', 'success')
    return redirect(url_for('office'))

@app.route('/admin/faculty', methods = ['GET', 'POST'])
def faculty():
    form = FacultyForm()

    # handle add form submission
    if form.validate_on_submit():
        existing_user = Faculty.query.filter_by(username=form.username.data.strip()).first()
        if existing_user:
            flash('Username already exists', 'danger')
            return redirect(url_for('faculty'))

        # find or create office by name
        office_name = form.office.data.strip()
        office = Office.query.filter_by(Office_nm=office_name).first()
        if not office:
            office = Office(Office_nm=office_name, office_loc='')
            db.session.add(office)
            db.session.commit()

        new_faculty = Faculty(
            Faculty_nm=form.name.data.strip(),
            username=form.username.data.strip(),
            password=generate_password_hash(form.password.data.strip()),
            Office_id=office.Office_id
        )
        db.session.add(new_faculty)
        db.session.commit()
        flash('Faculty added.', 'success')
        return redirect(url_for('faculty'))

    # handle optional search
    q = request.args.get('q', '').strip()
    if q:
        faculties = Faculty.query.join(Office).filter(or_(Faculty.Faculty_nm.ilike(f"%{q}%"), Faculty.username.ilike(f"%{q}%"), Office.Office_nm.ilike(f"%{q}%"))).all()
    else:
        faculties = Faculty.query.all()

    items = []
    for f in faculties:
        items.append({
            'id': f.Faculty_id,
            'name': f.Faculty_nm,
            'username': f.username,
            'office': f.office.Office_nm if getattr(f, 'office', None) else ''
        })

    return render_template('manage-faculty.html', items=items, add_form=form, q=q)



@app.route('/admin/faculty/edit/<int:faculty_id>', methods=['POST'])
def edit_faculty(faculty_id):
    form = FacultyForm()
    if form.validate_on_submit():
        fac = Faculty.query.get_or_404(faculty_id)
        fac.Faculty_nm = form.name.data.strip()
        fac.username = form.username.data.strip()
        if form.password.data and form.password.data.strip():
            fac.password = generate_password_hash(form.password.data.strip())

        office_name = form.office.data.strip()
        office = Office.query.filter_by(Office_nm=office_name).first()
        if not office:
            office = Office(Office_nm=office_name, office_loc='')
            db.session.add(office)
            db.session.commit()

        fac.Office_id = office.Office_id
        db.session.commit()
        flash('Faculty updated.', 'success')
    else:
        flash('Failed to update faculty. Check input.', 'danger')
    return redirect(url_for('faculty'))




@app.route('/admin/category', methods = ['GET', 'POST'])
def category():
    form = CategoryForm()
    return render_template('manage-category.html')

#################################################end of dashboard(admin) ####################################################


############################################for student dashboard ####################################################


@app.route('/student/information', methods=['GET', 'POST'])
def student_information():
    form = StudentForm()
    if form.validate_on_submit():
        new_student = Student(
            Student_nm=form.name.data.strip(),
            Student_number=form.student_id.data.strip(),
            student_course=form.course.data.strip(),
            student_year=form.year.data.strip()
        )
        db.session.add(new_student)
        db.session.commit()
        flash('Student added successfully.', 'success')
        return redirect(url_for('student_information'))

    return render_template('student-information.html', form=form)

@app.route('/student/dashboard', methods=['GET', 'POST'])
def student_dashboard():
    # Get filters from query parameters
    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category', 'all')

    # Start query
    inventories = Inventory.query

    # Apply category filter
    if category_filter != 'all':
        inventories = inventories.join(Inventory.category).filter(Inventory.category.has(Category_nm=category_filter))

    # Apply search filter
    if search:
        search_pattern = f"%{search}%"
        inventories = inventories.filter(
            or_(
                Inventory.Inventory_nm.ilike(search_pattern),
                Inventory.Serial_number.ilike(search_pattern),
                Inventory.Inventory_condition.ilike(search_pattern),
                Inventory.category.has(Category.Category_nm.ilike(search_pattern))
            )
        )

    inventories = inventories.all()

    # Build items list
    items = []
    for inventory in inventories:
        approved_qty = db.session.query(func.coalesce(func.sum(BorrowTracker.borrow_quantity),0)).filter(
            BorrowTracker.InventoryID == inventory.InventoryID,
            BorrowTracker.status == 'approved'
        ).scalar() or 0
        
        available = inventory.Quantity - approved_qty

        items.append({
            'id': inventory.InventoryID,
            'name': inventory.Inventory_nm,
            'category': inventory.category.Category_nm if getattr(inventory, 'category', None) else '',
            'desc': f"serial: {inventory.Serial_number}, condition: {inventory.Inventory_condition}",
            'available': available > 0,
            'quantity': available
        })

    # Stats for hero section
    total_items = len(items)
    available_items = sum(1 for i in items if i['available'])
    categories = set(i['category'] for i in items)

    return render_template(
        'student-dashboard.html',
        items=items,
        total_items=total_items,
        available_items=available_items,
        categories=len(categories),
        current_category=category_filter,
        search_query=search
    )


@app.route('/student/borrow', methods=['GET', 'POST'])
def student_borrow():
    form = BorrowForm()

    inventory_id = request.args.get('inventory_id')

    inventory_item = None
    if inventory_id:
        inventory_item = Inventory.query.get(inventory_id)
        if inventory_item:
            form.inventory_id.data = inventory_item.InventoryID

    if form.validate_on_submit():

        student = Student.query.filter_by(
            Student_number=form.student_id.data.strip()
        ).first()

        if not student:
            flash('Student not found.', 'danger')
            return render_template('student-borrow.html',
                                   form=form,
                                   inventory=inventory_item)

        inventory_item = Inventory.query.get(form.inventory_id.data)

        if not inventory_item:
            flash('Inventory not found.', 'danger')
            return render_template('student-borrow.html',
                                   form=form,
                                   inventory=None)

        # Create request (PENDING)
        borrow_record = BorrowTracker(
            borrow_quantity=form.quantity.data,
            Student_id=student.Student_id,
            InventoryID=inventory_item.InventoryID,
            status='pending'
        )

        db.session.add(borrow_record)
        db.session.commit()

        flash('Borrow request submitted! Waiting for approval.', 'success')
        return redirect(url_for('student_dashboard'))

    return render_template('student-borrow.html',
                           form=form,
                           inventory=inventory_item)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)