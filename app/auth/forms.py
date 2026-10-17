# app/auth/forms.py -- Flask-WTF forms (CSRF + validation built in)
# CS50x map: CS50x used request.form.get + manual checks. WTF does required/length/email for us.
from flask_wtf import FlaskForm  # base class: adds CSRF token automatically
from wtforms import StringField, PasswordField, SubmitField  # field types
from wtforms.validators import DataRequired, Length, Email, EqualTo  # rules per field

class LoginForm(FlaskForm):
    """Username + password login."""
    username = StringField("Username", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")

class ChangePasswordForm(FlaskForm):
    """Forced at first login + later changes. New must match confirm."""
    current = PasswordField("Current password", validators=[DataRequired()])
    new = PasswordField("New password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm = PasswordField("Confirm new", validators=[DataRequired(), EqualTo("new")])
    submit = SubmitField("Change password")

class CreateAccountForm(FlaskForm):
    """Adviser/super-admin creates account by email + name (spec 5.1)."""
    name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField("Create + email temp password")

class ForgotForm(FlaskForm):
    """Request reset link by email."""
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField("Send reset link")

class ResetForm(FlaskForm):
    """Set new password from emailed token link (1 hour expiry)."""
    new = PasswordField("New password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm = PasswordField("Confirm new", validators=[DataRequired(), EqualTo("new")])
    submit = SubmitField("Reset password")
