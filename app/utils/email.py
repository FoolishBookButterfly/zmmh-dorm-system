# app/utils/email.py -- temp-password + notification mailer (spec 5.1, 5.12)
# CS50x map: CS50x never sent email. Dev = print to console (no Gmail needed yet).
# Prod later = Flask-Mail via Gmail App Password (MAIL_* in config.py, Step 6).
from flask import current_app  # read MAIL_SUPPRESS_SEND / MAIL_* without importing app
from flask_mail import Message  # email object Flask-Mail sends
from app import mail  # the Mail() handle from factory (app/__init__.py)

def send_temp_password(to_email, username, temp_password):
    """Email username + temp password. Dev prints to console; prod sends via Flask-Mail."""
    subject = "Your ZmMH account is ready"
    body = ("Hi!\n\nYour ZmMH Dormitory account:\n" + "Username: " + username + "\n" + "Temporary password: " + temp_password + "\n\n" + "Log in and change it immediately (forced at first login).\n")
    # Console fallback: if MAIL_SUPPRESS_SEND is True (dev default), just print.
    # Q1 answer: no Gmail App Password yet, so Step 6 sets MAIL_SUPPRESS_SEND=True locally.
    if current_app.config.get("MAIL_SUPPRESS_SEND", True):
        print("[DEV EMAIL] To: " + to_email + " | " + subject + " | username=" + username + " temp=" + temp_password)
        return True
    # Prod path: real send via Flask-Mail (needs MAIL_SERVER/USERNAME/PASSWORD in env)
    msg = Message(subject=subject, recipients=[to_email], body=body)
    mail.send(msg)
    return True

def send_reset_link(to_email, reset_url):
    """Email password-reset link (expires in 1 hour, Step 4). Same dev/prod split."""
    subject = "Reset your ZmMH password"
    body = "Click within 1 hour:\n" + reset_url + "\n\nIgnore if you did not ask.\n"
    if current_app.config.get("MAIL_SUPPRESS_SEND", True):
        print("[DEV EMAIL] To: " + to_email + " | " + subject + " | " + reset_url)
        return True
    msg = Message(subject=subject, recipients=[to_email], body=body)
    mail.send(msg)
    return True
