from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length, Regexp, NumberRange, Optional

class StudentForm(FlaskForm):
    id_number = StringField(
        'ID Number',
        validators=[
            DataRequired(),
            Regexp(r'^\d{3}\s*-\s*\d{5}$', message='ID must be like 201 - 00123')
        ]
    )
    name = StringField('Name', validators=[DataRequired(), Length(min=1, max=100)])
    course = StringField('Course', validators=[DataRequired(), Length(min=1, max=50)])
    year = StringField('Year', validators=[DataRequired(), Length(min=1, max=20)])
    submit = SubmitField('Submit')

class StudentFollowUpForm(FlaskForm):
    student_id = StringField(
        'Student ID',
        validators=[
            DataRequired(),
            Regexp(r'^\d{3}\s*-\s*\d{5}$', message='ID must be like 201 - 00123')
        ]
    )
    submit = SubmitField('Submit')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('Login')


class SignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=50)])
    office = StringField('Office', validators=[DataRequired(), Length(min=1, max=100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=1, max=100)])
    comfirm_password = PasswordField('Confirm Password', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('Sign Up')


class BorrowForm(FlaskForm):
    student_id = StringField(
        'Student ID',
        validators=[
            DataRequired(),
            Regexp(r'^\d{3}\s*-\s*\d{5}$', message='ID must be like 201 - 00123')
        ]
    )

    inventory_id = IntegerField(
        'Inventory ID',
        validators=[DataRequired()]
    )

    remarks = StringField(
        'Remarks',
        validators=[Optional(), Length(max=200)]
    )

    submit = SubmitField('Request to Borrow')


class InventoryForm(FlaskForm):
    name = StringField('Item Name', validators=[DataRequired(), Length(min=1, max=100)])
    desc = StringField('Description', validators=[Optional(), Length(max=200)])
    condition = SelectField('Condition', choices=[
        ('functional', 'Functional'),
        ('non-functional', 'Non Functional'),
        ('under-maintenance', 'Under Maintenance'),
        ('under-repair', 'Under Repair')
    ], validators=[DataRequired()])
    serial = StringField('Serial Number', validators=[DataRequired(), Length(min=1, max=100)])
    category = StringField('Category', validators=[DataRequired(), Length(min=1, max=100)])
    office = StringField('Office', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('Add Item')


class OfficeForm(FlaskForm):
    name = StringField('Office Name', validators=[DataRequired(), Length(min=1, max=100)])
    location = StringField('Location', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('Add Office')


class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('Add Category')


class FacultyForm(FlaskForm):
    name = StringField('Faculty Name', validators=[DataRequired(), Length(min=1, max=100)])
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=50)])
    password = PasswordField('Password', validators=[Optional(), Length(min=1, max=100)])
    office = StringField('Office', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('Add Faculty')