from flask import Flask, render_template, request, redirect, url_for, flash
from database.models import db, BorrowTracker, Student, Office, Faculty, Category, Inventory
from forms import StudentForm, LoginForm, SignupForm, BorrowForm
from werkzeug.security import generate_password_hash, check_password_hash


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

@app.route('/admin/dashboard')
def admin_dashboard():
    return render_template('admin-dashboard.html')

@app.route('/student')
def student():
    return render_template('student-login.html')

@app.route('/student/dashboard')
def student_dashboard():
    return render_template('student-dashboard.html')



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)