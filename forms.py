from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length 

class StudentForm(FlaskForm):
    id_number = StringField('ID Number', validators=[DataRequired(), Length(min=1, max=20)])
    name = StringField('Name', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('Submit')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('Login')