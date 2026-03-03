from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length 

#form for getting student information
class StudentForm(FlaskForm):
    id_number = StringField('ID Number', validators=[DataRequired(), Length(min=1, max=20)])
    name = StringField('Name', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('Submit')

#login form for faculty/admin
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('Login')

#signup form for faculty/admin
class SignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=50)])
    office = StringField('Office', validators=[DataRequired(), Length(min=1, max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=1, max=100)])
    comfirm_password = PasswordField('Confirm Password', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('Sign Up')

#borrowing form for students to borrow inventory items
class BorrowForm(FlaskForm):
    student_id = StringField('Student ID', validators=[DataRequired(), Length(min=1, max=20)])
    inventory_id = StringField('Inventory ID', validators=[DataRequired(), Length(min=1, max=20)])
    date_borrowed = StringField('Date Borrowed', validators=[DataRequired()])
    submit = SubmitField('Request to Borrow')