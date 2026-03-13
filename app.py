from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from database.models import db, BorrowTracker, Student, Office, Faculty, Category, Inventory, EquipmentApprover, Reports, Itemkind
from sqlalchemy import func, or_
from forms import StudentForm, LoginForm, SignupForm, BorrowForm, InventoryForm, OfficeForm, CategoryForm, FacultyForm, StudentFollowUpForm
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta, date
from functools import wraps
from dotenv import load_dotenv
import os
import io
import csv
import zipfile

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

db.init_app(app)

with app.app_context():
    db.create_all()

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'faculty' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('admin'))
        return f(*args, **kwargs)
    return decorated

# Routes for admin and student interfaces/landing page
@app.route('/')
def index():
    return render_template('index.html')

######################Admin login#########################
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'faculty' in session:
        return redirect(url_for('admin_dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        faculty = Faculty.query.filter_by(username=form.username.data).first()
        if faculty and check_password_hash(faculty.password, form.password.data):
            session['faculty'] = {
                'id': faculty.faculty_id,
                'name': faculty.faculty_nm,
                'username': faculty.username
            }
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('admin-login.html', form=form)

@app.route('/admin/logout')
def admin_logout():
    session.pop('faculty', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('admin'))

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

        office = Office.query.first()
        if not office:
            office = Office(office_nm="Default Office", office_loc="Main Building")
            db.session.add(office)
            db.session.commit()

        hashed_password = generate_password_hash(form.password.data)
        new_faculty = Faculty(
            username=form.username.data,
            password=hashed_password,
            faculty_nm=form.username.data,
            office_id=office.office_id
        )
        db.session.add(new_faculty)
        db.session.commit()
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('admin'))

    return render_template('admin-signup.html', form=form)

@app.route('/admin/profile/edit', methods=['POST'])
@admin_required
def edit_profile():
    faculty_id = session['faculty']['id']
    fac = Faculty.query.get_or_404(faculty_id)

    faculty_nm = request.form.get('faculty_nm', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    # Check username not taken by someone else
    existing = Faculty.query.filter_by(username=username).first()
    if existing and existing.faculty_id != faculty_id:
        flash('Username already taken.', 'danger')
        return redirect(request.referrer or url_for('admin_dashboard'))

    if password:
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(request.referrer or url_for('admin_dashboard'))
        fac.password = generate_password_hash(password)

    fac.faculty_nm = faculty_nm
    fac.username = username
    db.session.commit()

    # Update session
    session['faculty'] = {
        'id': fac.faculty_id,
        'name': fac.faculty_nm,
        'username': fac.username
    }

    flash('Profile updated successfully.', 'success')
    return redirect(request.referrer or url_for('admin_dashboard'))

#########################Admin dashboard and management pages#########################
#helper function to check for overdue items and update their status
def check_overdue():
    today = date.today()
    # Update status to 'overdue' for items past return date and still not returned
    BorrowTracker.query.filter( BorrowTracker.status.in_(['approved', 'borrowed']),
                               BorrowTracker.return_date < today).update({'status': 'overdue'}, 
                               synchronize_session=False)
    
    # items not available when borrow date is today
    due_today = BorrowTracker.query.filter( BorrowTracker.status.in_(['approved', 'borrowed']),
                                            BorrowTracker.borrow_date <= today
                                            ).all()
    for record in due_today:
        record.inventory.is_available = False
    
    db.session.commit()

@app.route('/admin/dashboard', methods=['GET', 'POST'])
@admin_required
def admin_dashboard():
    check_overdue()  # Ensure overdue items are updated before showing dashboard stats

    total_items = Inventory.query.count()
    pending_count = BorrowTracker.query.filter_by(status='pending').count()
    overdue_count = BorrowTracker.query.filter_by(status='overdue').count()

    recent_requests = (
        BorrowTracker.query
        .options(
            joinedload(BorrowTracker.student),
            joinedload(BorrowTracker.inventory)
        )
        .filter(BorrowTracker.status == 'pending')
        .order_by(BorrowTracker.request_date.desc())
        .limit(5)
        .all()
    )

    recent_activities = (
    BorrowTracker.query
    .options(
        joinedload(BorrowTracker.student),
        joinedload(BorrowTracker.inventory)
    )
    .order_by(BorrowTracker.request_date.desc())
    .limit(10)
    .all()
    )

    return render_template(
        'admin-dashboard.html',
        total_items=total_items,
        pending_count=pending_count,
        overdue_count=overdue_count,
        recent_requests=recent_requests,
        recent_activities=recent_activities
    )

@app.route('/admin/borrowed-items', methods=['GET', 'POST'])
@admin_required
def borrowed_items():
    from sqlalchemy.orm import joinedload, contains_eager

    q = request.args.get('q', '').strip()

    if q:
        items = (
            BorrowTracker.query
            .join(BorrowTracker.student)
            .options(
                contains_eager(BorrowTracker.student),
                joinedload(BorrowTracker.inventory)
            )
            .filter(BorrowTracker.status.in_(['approved', 'borrowed', 'overdue']))
            .filter(
                or_(
                    Student.student_nm.ilike(f"%{q}%"),
                    Student.student_number.ilike(f"%{q}%")
                )
            )
            .all()
        )
    else:
        items = (
            BorrowTracker.query
            .options(
                joinedload(BorrowTracker.student),
                joinedload(BorrowTracker.inventory)
            )
            .filter(BorrowTracker.status.in_(['approved', 'borrowed', 'overdue']))
            .all()
        )

    return render_template('borrowed-items.html', items=items, q=q)

@app.route('/admin/borrowed-items/return/<int:borrow_id>', methods=['POST'])
@admin_required
def mark_returned(borrow_id):
    borrow = BorrowTracker.query.get_or_404(borrow_id)
    borrow.status = 'returned'
    borrow.inventory.is_available = True
    db.session.commit()
    flash('Item marked as returned.', 'success')
    return redirect(url_for('borrowed_items'))

@app.route('/admin/inventory', methods=['GET', 'POST'])
@admin_required
def inventory():
    add_form = InventoryForm()
    office_list = Office.query.all()
    itemkind_list = Itemkind.query.all()

    if add_form.validate_on_submit():
        cat_name = add_form.category.data.strip()
        category = Category.query.filter_by(category_nm=cat_name).first()
        if not category:
            category = Category(category_nm=cat_name)
            db.session.add(category)
            db.session.commit()

        office = Office.query.first()
        if not office:
            office = Office(office_nm="Default Office", office_loc="Main Building")
            db.session.add(office)
            db.session.commit()

        itemkind_nm = add_form.itemkind.data.strip() if add_form.itemkind.data else None
        itemkind = None
        if itemkind_nm:
            itemkind = Itemkind.query.filter_by(itemkind_nm=itemkind_nm).first()
            if not itemkind:
                itemkind = Itemkind(itemkind_nm=itemkind_nm)
                db.session.add(itemkind)
                db.session.commit()

        new_inv = Inventory(
            inventory_nm=add_form.name.data.strip(),
            inventory_desc=add_form.desc.data.strip() if add_form.desc.data else None,
            inventory_condition=add_form.condition.data.strip(),
            serial_number=add_form.serial.data.strip(),
            office_id=office.office_id,
            category_id=category.category_id,
            itemkind_id=itemkind.itemkind_id if itemkind else None
        )

        db.session.add(new_inv)
        db.session.commit()
        flash('Inventory item added.', 'success')
        return redirect(url_for('inventory'))

    q = request.args.get('q', '').strip()

    if q:
        inv_query = Inventory.query.outerjoin(Category)
        inv_query = inv_query.filter(
            or_(
                Inventory.inventory_nm.ilike(f"%{q}%"),
                Inventory.serial_number.ilike(f"%{q}%"),
                Category.category_nm.ilike(f"%{q}%")
            )
        )
        inventories = inv_query.all()
    else:
        inventories = Inventory.query.all()

    items = []
    for inv in inventories:
        items.append({
            'id': inv.inventory_id,
            'name': inv.inventory_nm,
            'category': inv.category.category_nm if inv.category else '',
            'desc': inv.inventory_desc,
            'office': inv.office.office_nm if inv.office else '',
            'condition': inv.inventory_condition,
            'serial': inv.serial_number,
            'available': inv.is_available,
            'status': 'Available' if inv.is_available else 'Borrowed',
            'itemkind_id': inv.itemkind_id or '',
            'itemkind': next((k.itemkind_nm for k in itemkind_list if k.itemkind_id == inv.itemkind_id), 'N/A')
        })

    return render_template('manage-inventory.html',
                            items=items,
                            add_form=add_form,
                            q=q, 
                            office_list=office_list, 
                            itemkind_list=itemkind_list)

@app.route('/admin/inventory/edit/<int:item_id>', methods=['POST'])
@admin_required
def edit_inventory(item_id):
    form = InventoryForm()
    if form.validate_on_submit():
        inv = Inventory.query.get_or_404(item_id)
        inv.inventory_nm = form.name.data.strip()
        inv.inventory_condition = form.condition.data.strip()
        inv.serial_number = form.serial.data.strip()
        inv.inventory_desc = form.desc.data.strip() if form.desc.data else None

        cat_name = form.category.data.strip()
        category = Category.query.filter_by(category_nm=cat_name).first()
        if not category:
            category = Category(category_nm=cat_name)
            db.session.add(category)
            db.session.commit()
        inv.category_id = category.category_id
        inv.office_id = form.office.data

        # Handle itemkind
        itemkind_nm = form.itemkind.data.strip() if form.itemkind.data else None
        if itemkind_nm:
            itemkind = Itemkind.query.filter_by(itemkind_nm=itemkind_nm).first()
            if not itemkind:
                itemkind = Itemkind(itemkind_nm=itemkind_nm)
                db.session.add(itemkind)
                db.session.commit()
            inv.itemkind_id = itemkind.itemkind_id
        else:
            inv.itemkind_id = None

        db.session.commit()
        flash('Inventory item updated.', 'success')
    else:
        flash('Failed to update item.', 'danger')

    return redirect(url_for('inventory'))

@app.route('/admin/inventory/delete/<int:item_id>', methods=['POST'])
@admin_required
def delete_inventory(item_id):
    inv = Inventory.query.get_or_404(item_id)
    BorrowTracker.query.filter_by(inventory_id=inv.inventory_id).delete()
    db.session.delete(inv)
    db.session.commit()
    flash('Inventory item deleted.', 'success')
    return redirect(url_for('inventory'))

from sqlalchemy.orm import joinedload



@app.route('/admin/requests')
@admin_required
def requests():
    q = request.args.get('q', '').strip()

    if q:
        from sqlalchemy.orm import contains_eager
        pending_requests = (
            BorrowTracker.query
            .join(BorrowTracker.student)
            .options(
                contains_eager(BorrowTracker.student),
                joinedload(BorrowTracker.inventory)
            )
            .filter(BorrowTracker.status == 'pending')
            .filter(
                or_(
                    Student.student_nm.ilike(f"%{q}%"),
                    Student.student_number.ilike(f"%{q}%")
                )
            )
            .all()
        )
    else:
        pending_requests = (
            BorrowTracker.query
            .options(
                joinedload(BorrowTracker.student),
                joinedload(BorrowTracker.inventory)
            )
            .filter(BorrowTracker.status == 'pending')
            .all()
        )

    return render_template('manage-request.html', requests=pending_requests, q=q)

@app.route('/admin/requests/approve/<int:borrow_id>', methods=['POST'])
@admin_required
def approve_request(borrow_id):
    borrow = BorrowTracker.query.get_or_404(borrow_id)

    if borrow.status != 'pending':
        flash('Request already processed.', 'warning')
        return redirect(url_for('requests'))

    borrow.status = 'approved'
    borrow.approve_date = datetime.now(timezone.utc)
    borrow.remarks = request.form.get('remarks', '').strip() or borrow.remarks

    borrow_date = request.form.get('borrow_date')
    return_date = request.form.get('return_date')

    if borrow_date:
        borrow.borrow_date = datetime.strptime(borrow_date, '%Y-%m-%d').date()
    if return_date:
        borrow.return_date = datetime.strptime(return_date, '%Y-%m-%d').date()

    # Only mark unavailable if borrow date is today or already passed
    today = date.today()
    if borrow.borrow_date and borrow.borrow_date <= today:
        borrow.inventory.is_available = False

    db.session.commit()
    flash('Request approved.', 'success')
    return redirect(url_for('requests'))

@app.route('/admin/requests/reject/<int:borrow_id>', methods=['POST'])
@admin_required
def reject_request(borrow_id):
    borrow = BorrowTracker.query.get_or_404(borrow_id)
    if borrow.status != 'pending':
        flash('Request already processed.', 'warning')
        return redirect(url_for('requests'))

    borrow.status = 'rejected'
    borrow.remarks = request.form.get('remarks', '').strip() or borrow.remarks
    db.session.commit()
    flash('Request rejected.', 'info')
    return redirect(url_for('requests'))

@app.route('/admin/reports', methods=['GET', 'POST'])
@admin_required
def reports():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    query = BorrowTracker.query

    if date_from:
        query = query.filter(BorrowTracker.request_date >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(BorrowTracker.request_date <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))

    total_borrows = query.count()
    damage_reports = Reports.query.count()

    most_borrowed = (
        db.session.query(Inventory.inventory_nm, func.count(BorrowTracker.inventory_id).label('borrow_count'))
        .join(BorrowTracker, BorrowTracker.inventory_id == Inventory.inventory_id)
        .group_by(Inventory.inventory_nm)
        .order_by(func.count(BorrowTracker.inventory_id).desc())
        .first()
    )

    today = datetime.now(timezone.utc).date()
    days = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
    daily_counts = []
    max_count = 1

    for day in days:
        count = BorrowTracker.query.filter(func.date(BorrowTracker.request_date) == day).count()
        daily_counts.append({'day': day.strftime('%a'), 'count': count})
        if count > max_count:
            max_count = count

    for d in daily_counts:
        d['height'] = int((d['count'] / max_count) * 100) if max_count > 0 else 0

    # Equipment quantity summary
    itemkind_summary = []
    for kind in Itemkind.query.all():
        total = Inventory.query.filter_by(itemkind_id=kind.itemkind_id).count()
        available = Inventory.query.filter_by(itemkind_id=kind.itemkind_id, is_available=True).count()
        itemkind_summary.append({
            'name': kind.itemkind_nm,
            'total': total,
            'available': available,
            'borrowed': total - available
        })

    return render_template(
        'reports.html',
        total_borrows=total_borrows,
        most_borrowed=most_borrowed.inventory_nm if most_borrowed else 'N/A',
        damage_reports=damage_reports,
        daily_counts=daily_counts,
        date_from=date_from,
        date_to=date_to,
        itemkind_summary=itemkind_summary
    )



@app.route('/admin/reports/export')
@admin_required
def export_csv():
    # ── Borrow Records CSV ──
    borrow_output = io.StringIO()
    borrow_writer = csv.writer(borrow_output)
    borrow_writer.writerow(['Borrow ID', 'Student Name', 'Student Number', 'Faculty In Charge', 'Contact Number', 'Item', 'Status', 'Request Date', 'Borrow Date', 'Return Date', 'Remarks'])

    records = BorrowTracker.query.options(
        joinedload(BorrowTracker.student),
        joinedload(BorrowTracker.inventory)
    ).all()

    for r in records:
        borrow_writer.writerow([
            r.borrow_id,
            r.student.student_nm if r.student else 'N/A',
            r.student.student_number if r.student else 'N/A',
            r.faculty_incharge or 'N/A',
            r.contact_number or 'N/A',
            r.inventory.inventory_nm if r.inventory else 'N/A',
            r.status,
            r.request_date.strftime('%Y-%m-%d') if r.request_date else '',
            r.borrow_date.strftime('%Y-%m-%d') if r.borrow_date else '',
            r.return_date.strftime('%Y-%m-%d') if r.return_date else '',
            r.remarks or ''
        ])

    # ── Inventory CSV ──
    inventory_output = io.StringIO()
    inventory_writer = csv.writer(inventory_output)
    inventory_writer.writerow(['Inventory ID', 'Name', 'Category', 'Equipment Group', 'Description', 'Office', 'Condition', 'Serial Number', 'Status'])

    for inv in Inventory.query.all():
        inventory_writer.writerow([
            inv.inventory_id,
            inv.inventory_nm,
            inv.category.category_nm if inv.category else 'N/A',
            inv.itemkind.itemkind_nm if inv.itemkind else 'N/A',
            inv.inventory_desc or '',
            inv.office.office_nm if inv.office else 'N/A',
            inv.inventory_condition,
            inv.serial_number,
            'Available' if inv.is_available else 'Borrowed'
        ])

    # ── Equipment Quantity CSV ──
    itemkind_output = io.StringIO()
    itemkind_writer = csv.writer(itemkind_output)
    itemkind_writer.writerow(['Equipment Group', 'Total Units', 'Available', 'Borrowed'])

    for kind in Itemkind.query.all():
        total = Inventory.query.filter_by(itemkind_id=kind.itemkind_id).count()
        available = Inventory.query.filter_by(itemkind_id=kind.itemkind_id, is_available=True).count()
        itemkind_writer.writerow([
            kind.itemkind_nm,
            total,
            available,
            total - available
        ])

    # ── Zip all three ──
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('borrow_records.csv', borrow_output.getvalue())
        zip_file.writestr('inventory.csv', inventory_output.getvalue())
        zip_file.writestr('equipment_quantity.csv', itemkind_output.getvalue())

    zip_buffer.seek(0)
    return Response(
        zip_buffer,
        mimetype='application/zip',
        headers={'Content-Disposition': 'attachment; filename=reports.zip'}
    )

@app.route('/admin/office', methods=['GET', 'POST'])
@admin_required
def office():
    form = OfficeForm()
    faculty_list = Faculty.query.all()

    if form.validate_on_submit():
        new_office = Office(
            office_nm=form.name.data.strip(),
            office_loc=form.location.data.strip()
        )
        db.session.add(new_office)
        db.session.commit()
        flash('Office added.', 'success')
        return redirect(url_for('office'))

    q = request.args.get('q', '').strip()

    if q:
        offices = Office.query.filter(
            or_(
                Office.office_nm.ilike(f"%{q}%"),
                Office.office_loc.ilike(f"%{q}%")
            )
        ).all()
    else:
        offices = Office.query.all()

    return render_template('manage-office.html', add_form=form, q=q, faculty_list=faculty_list, offices=offices)

@app.route('/admin/office/edit/<int:office_id>', methods=['POST'])
@admin_required
def edit_office(office_id):
    form = OfficeForm()
    if form.validate_on_submit():
        off = Office.query.get_or_404(office_id)
        off.office_nm = form.name.data.strip()
        off.office_loc = form.location.data.strip()
        db.session.commit()
        flash('Office updated.', 'success')
    else:
        flash('Failed to update office.', 'danger')
    return redirect(url_for('office'))

@app.route('/admin/office/delete/<int:office_id>', methods=['POST'])
@admin_required
def delete_office(office_id):
    off = Office.query.get_or_404(office_id)
    assigned_count = Inventory.query.filter_by(office_id=off.office_id).count()

    if assigned_count > 0:
        flash('Cannot delete office with assigned inventory.', 'danger')
        return redirect(url_for('office'))

    db.session.delete(off)
    db.session.commit()
    flash('Office deleted.', 'success')
    return redirect(url_for('office'))

@app.route('/admin/office/assign/<int:office_id>', methods=['POST'])
@admin_required
def assign_office_head(office_id):
    faculty_id = request.form.get('faculty_id')

    if not faculty_id:
        flash("Please select a faculty member.", "error")
        return redirect(url_for('office'))

    existing_record = EquipmentApprover.query.filter_by(office_id=office_id).first()
    if existing_record:
        existing_record.faculty_id = faculty_id
    else:
        new_head = EquipmentApprover(office_id=office_id, faculty_id=faculty_id)
        db.session.add(new_head)

    try:
        db.session.commit()
        flash("Office head assigned successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash("Error assigning office head.", "error")

    return redirect(url_for('office'))

@app.route('/admin/faculty', methods=['GET', 'POST'])
@admin_required
def faculty():
    form = FacultyForm()

    if form.validate_on_submit():
        existing_user = Faculty.query.filter_by(username=form.username.data.strip()).first()
        if existing_user:
            flash('Username already exists', 'danger')
            return redirect(url_for('faculty'))

        office_name = form.office.data.strip()
        office = Office.query.filter_by(office_nm=office_name).first()
        if not office:
            office = Office(office_nm=office_name, office_loc='')
            db.session.add(office)
            db.session.commit()

        new_faculty = Faculty(
            faculty_nm=form.name.data.strip(),
            username=form.username.data.strip(),
            password=generate_password_hash(form.password.data.strip()),
            office_id=office.office_id
        )
        db.session.add(new_faculty)
        db.session.commit()
        flash('Faculty added.', 'success')
        return redirect(url_for('faculty'))

    q = request.args.get('q', '').strip()

    if q:
        faculties = Faculty.query.join(Office).filter(
            or_(
                Faculty.faculty_nm.ilike(f"%{q}%"),
                Faculty.username.ilike(f"%{q}%"),
                Office.office_nm.ilike(f"%{q}%")
            )
        ).all()
    else:
        faculties = Faculty.query.all()

    items = []
    for f in faculties:
        items.append({
            'id': f.faculty_id,
            'name': f.faculty_nm,
            'username': f.username,
            'office': f.office.office_nm if f.office else ''
        })

    return render_template('manage-faculty.html', items=items, add_form=form, q=q)

@app.route('/admin/faculty/edit/<int:faculty_id>', methods=['POST'])
@admin_required
def edit_faculty(faculty_id):
    form = FacultyForm()

    if form.validate_on_submit():
        fac = Faculty.query.get_or_404(faculty_id)
        fac.faculty_nm = form.name.data.strip()
        fac.username = form.username.data.strip()

        if form.password.data and form.password.data.strip():
            fac.password = generate_password_hash(form.password.data.strip())

        office_name = form.office.data.strip()
        office = Office.query.filter_by(office_nm=office_name).first()
        if not office:
            office = Office(office_nm=office_name, office_loc='')
            db.session.add(office)
            db.session.commit()

        fac.office_id = office.office_id
        db.session.commit()
        flash('Faculty updated.', 'success')
    else:
        flash('Failed to update faculty.', 'danger')

    return redirect(url_for('faculty'))

@app.route('/admin/category', methods=['GET', 'POST'])
@admin_required
def category():
    form = CategoryForm()
    return render_template('manage-category.html')

#########################Student dashboard and borrowing routes#########################

@app.route('/student/information', methods=['GET', 'POST'])
def student_information():
    if 'student' in session:
        flash('Student information already provided.', 'info')
        return redirect(url_for('student_dashboard'))

    form = StudentForm()

    if form.validate_on_submit():
        student_number = form.id_number.data.strip()
        student = Student.query.filter_by(student_number=student_number).first()

        if not student:
            student = Student(
                student_nm=form.name.data.strip(),
                student_number=student_number,
                student_course=form.course.data.strip(),
                student_year=form.year.data.strip()
            )
            db.session.add(student)
            db.session.commit()

        session['student'] = {
            'id': student.student_id,
            'name': student.student_nm,
            'number': student.student_number,
            'course': student.student_course,
            'year': student.student_year
        }

        flash('Student information saved.', 'success')
        return redirect(url_for('student_dashboard'))

    return render_template('student-information.html', form=form)

@app.route('/student/myrequests', methods=['GET', 'POST'])
def student_requests():
    requests = []
    student = None
    searched = False

    if request.method == 'POST':
        student_number = request.form.get('student_number', '').strip()
        searched = True
        student = Student.query.filter_by(student_number=student_number).first()

        if student:
            requests = (
                BorrowTracker.query
                .options(joinedload(BorrowTracker.inventory))
                .filter_by(student_id=student.student_id)
                .order_by(BorrowTracker.request_date.desc())
                .all()
            )

    return render_template('student-requests.html', requests=requests, student=student, searched=searched)

@app.route('/student/dashboard', methods=['GET', 'POST'])
def student_dashboard():
    if 'student' not in session:
        flash('Please enter your information first.', 'warning')
        return redirect(url_for('student_information'))

    student = session['student']
    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category', 'all')

    inventories = Inventory.query.join(Category)  # join once

    if category_filter != 'all':
        inventories = inventories.filter(Category.category_nm == category_filter)

    if search:
        search_pattern = f"%{search}%"
        inventories = inventories.filter(
            or_(
                Inventory.inventory_nm.ilike(search_pattern),
                Inventory.serial_number.ilike(search_pattern),
                Inventory.inventory_condition.ilike(search_pattern),
                Category.category_nm.ilike(search_pattern)
            )
        )

    inventories = inventories.all()
    items = []

    for inv in inventories:
        active_borrow = BorrowTracker.query.filter(
        BorrowTracker.inventory_id == inv.inventory_id,
        BorrowTracker.status.in_(['approved', 'borrowed', 'overdue'])
        ).order_by(BorrowTracker.request_date.desc()).first()

        items.append({
            'id': inv.inventory_id,
            'name': inv.inventory_nm,
            'category': inv.category.category_nm if inv.category else '',
            'desc': inv.inventory_desc or '',
            'serial': inv.serial_number,
            'condition': inv.inventory_condition,
            'office': inv.office.office_nm if inv.office else 'N/A',
            'available': inv.is_available,
            'return_date': active_borrow.return_date.strftime('%b %d, %Y') if active_borrow and active_borrow.return_date else None,
        })

    return render_template(
        'student-dashboard.html',
        items=items,
        current_category=category_filter,
        search_query=search,
        student=student
    )

@app.route('/student/borrow', methods=['GET', 'POST'])
def student_borrow():
    if 'student' not in session:
        return redirect(url_for('student_information'))

    student = session['student']
    form = BorrowForm()
    form.student_id.data = student['number']

    inventory_id = request.args.get('inventory_id') or form.inventory_id.data
    inventory_item = Inventory.query.get(inventory_id) if inventory_id else None

    if inventory_item:
        form.inventory_id.data = inventory_item.inventory_id

    if form.validate_on_submit():
        inventory_item = Inventory.query.get(form.inventory_id.data)

        if not inventory_item:
            flash('Inventory not found.', 'danger')
            return render_template('student-borrow.html', form=form, inventory=None, student=student)

        if not inventory_item.is_available:
            flash('Item is currently unavailable.', 'danger')
            return redirect(url_for('student_dashboard'))

        approver_id = None
        if inventory_item.office.approver_config:
            approver_id = inventory_item.office.approver_config.faculty_id

        borrow_record = BorrowTracker(
            student_id=student['id'],
            inventory_id=inventory_item.inventory_id,
            status='pending',
            remarks=form.remarks.data.strip() if form.remarks.data else None,
            borrow_date=form.borrow_date.data,
            return_date=form.return_date.data,
            faculty_incharge=form.faculty_incharge.data.strip() if form.faculty_incharge.data else None,
            contact_number=form.contact_number.data.strip() if form.contact_number.data else None,
            approved_by=approver_id
        )

        db.session.add(borrow_record)
        db.session.commit()

        return redirect(url_for('student_dashboard'))

    return render_template('student-borrow.html', form=form, inventory=inventory_item, student=student)

@app.route('/student/borrow/bulk', methods=['GET', 'POST'])
def student_borrow_bulk():
    if 'student' not in session:
        return redirect(url_for('student_information'))

    student = session['student']
    form = BorrowForm()

    if request.method == 'POST':
        inventory_ids = request.form.getlist('inventory_ids')
        faculty_incharge = request.form.get('faculty_incharge', '').strip()
        borrow_date = request.form.get('borrow_date')
        return_date = request.form.get('return_date')
        remarks = request.form.get('remarks', '').strip()

        borrow_date_obj = datetime.strptime(borrow_date, '%Y-%m-%d').date() if borrow_date else None
        return_date_obj = datetime.strptime(return_date, '%Y-%m-%d').date() if return_date else None

        borrowed = []
        skipped = []

        for inv_id in inventory_ids:
            inventory_item = Inventory.query.get(inv_id)
            if not inventory_item or not inventory_item.is_available:
                skipped.append(inv_id)
                continue

            approver_id = None
            if inventory_item.office and inventory_item.office.approver_config:
                approver_id = inventory_item.office.approver_config.faculty_id

            borrow_record = BorrowTracker(
                student_id=student['id'],
                inventory_id=inventory_item.inventory_id,
                status='pending',
                remarks=remarks or None,
                approved_by=approver_id,
                faculty_incharge=faculty_incharge or None,
                contact_number=form.contact_number.data.strip() if form.contact_number.data else None,
                borrow_date=borrow_date_obj,
                return_date=return_date_obj
            )
            db.session.add(borrow_record)
            borrowed.append(inventory_item.inventory_nm)

        db.session.commit()

        if borrowed:
            flash(f'Borrow requests submitted for: {", ".join(borrowed)}.', 'success')
        if skipped:
            flash(f'{len(skipped)} item(s) were skipped (unavailable).', 'warning')

        return redirect(url_for('student_dashboard'))

    # GET — receive inventory_ids from cart via query string
    inventory_ids = request.args.getlist('inventory_ids')
    inventories = Inventory.query.filter(Inventory.inventory_id.in_(inventory_ids), Inventory.is_available == True).all()

    if not inventories:
        flash('No available items to borrow.', 'warning')
        return redirect(url_for('student_cart'))

    return render_template('student-borrow-bulk.html', inventories=inventories, student=student, form=form)

@app.route('/student/cart', methods=['GET', 'POST'])
def student_cart():
    if 'student' not in session:
        return redirect(url_for('student_information'))

    student = session['student']
    
    return render_template('student-cart.html', student=student)

@app.route('/student/logout')
def student_logout():
    session.pop('student', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('student_information'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)