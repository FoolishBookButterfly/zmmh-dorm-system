# app/auth/routes.py -- REAL auth (Phase 1.2): login/logout/forced-change/create/forgot/reset
# CS50x map: CS50x did session[user_id] + apology. Here Flask-Login + WTForms + audit on everything.
import secrets  # temp password generation (secrets.token_urlsafe = secure random)
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort  # web helpers (+abort for bootstrap)
from flask_login import login_user, logout_user, login_required, current_user  # session handling
from itsdangerous import URLSafeTimedSerializer  # reset tokens (no new package needed)
from app import db  # commit Person/User/Residency/AuditLog rows
# Exact 1.1 model names -- DO NOT rename
from app.roster.models import Person, User, SchoolYear, Semester, Residency, Role, RoleAssignment, AuditLog  # + Semester/Role/RoleAssignment for /bootstrap
from app.utils.decorators import permission_required  # Step 1 gate (adviser/super-admin only for create)
from app.utils.email import send_temp_password, send_reset_link  # Step 2 mailer (dev console print)
from app.auth.forms import LoginForm, ChangePasswordForm, CreateAccountForm, ForgotForm, ResetForm, BootstrapForm  # Step 3 + bootstrap forms

auth_bp = Blueprint("auth", __name__)  # mini-app mounted in factory

def _reset_serializer():
    """Timed token signer for password resets (1-hour expiry, SECRET_KEY + salt)."""
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=current_app.config.get("SECURITY_PASSWORD_SALT", "zmmh-reset"))

def _derive_username(email):
    """Username from email prefix + dedupe: juan@test.com -> juan, juan2 if taken."""
    base = email.split("@")[0].lower().strip() or "user"
    name, n = base, 1
    while User.query.filter_by(username=name).first() is not None:
        n += 1
        name = base + str(n)
    return name

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Log in with username + password. Forced to change-password if temp."""
    if current_user.is_authenticated and not current_user.must_change_password:
        return redirect(url_for("auth.me"))  # already in: go to proof page
    form = LoginForm()  # WTForms validates + CSRF checks on submit
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip().lower()).first()  # usernames stored lowercase
        # Wrong user, wrong password, or deactivated account all fail the same way (no info leak)
        if user is None or not user.check_password(form.password.data) or not user.is_active:
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html", form=form)
        login_user(user)  # Flask-Login remembers (was session[user_id] = row[id] in CS50x)
        db.session.add(AuditLog(actor_id=user.id, action="user.login", table_name="user", record_id=user.id))
        db.session.commit()
        if user.must_change_password:  # temp password: force change before anything else
            flash("Temporary password -- please set a new one.", "warning")
            return redirect(url_for("auth.change_password"))
        nxt = request.args.get("next")  # Flask-Login passes ?next= for guarded pages
        return redirect(nxt or url_for("auth.me"))
    return render_template("auth/login.html", form=form)

@auth_bp.route("/logout")
@login_required  # must be logged in to log out
def logout():
    """Log out and return to login."""
    uid = current_user.id
    logout_user()  # clears the Flask-Login session
    db.session.add(AuditLog(actor_id=uid, action="user.logout", table_name="user", record_id=uid))
    db.session.commit()
    flash("Logged out.", "success")
    return redirect(url_for("auth.login"))

@auth_bp.route("/me")
@login_required
def me():
    """Profile + authority page until dashboards exist (Phase 6). Renders base.html so the nav shows."""
    from app.utils.decorators import _active_assignments  # SAME helper the nav/can() uses (one source of truth)
    roles = [a.role.name for a in _active_assignments(current_user) if a.role is not None]
    return render_template("auth/me.html", roles=roles)

@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required  # temp users ARE logged in, so they can reach this (before_request exempts it)
def change_password():
    """Change password; clears must_change_password flag."""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current.data):  # must prove old/temp password
            flash("Current password is wrong.", "danger")
            return render_template("auth/change_password.html", form=form)
        current_user.set_password(form.new.data)  # hashes via Werkzeug (same as Finance)
        current_user.must_change_password = False  # done: no more forced redirects
        db.session.add(AuditLog(actor_id=current_user.id, action="password.change", table_name="user", record_id=current_user.id))
        db.session.commit()
        flash("Password changed.", "success")
        return redirect(url_for("auth.me"))
    return render_template("auth/change_password.html", form=form)

@auth_bp.route("/create-account", methods=["GET", "POST"])
@login_required
@permission_required("role.assign")  # ONLY advisers + super-admin (Plate 2B rule, no self-assign)
def create_account():
    """Create Person + User + Residency by email; email username + temp password."""
    form = CreateAccountForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if Person.query.filter_by(email=email).first() is not None:
            flash("Email already has an account.", "danger")
            return render_template("auth/create_account.html", form=form)
        username = _derive_username(email)  # email prefix + dedupe
        temp = secrets.token_urlsafe(6)  # ~8-char secure temp password
        person = Person(name=form.name.data.strip(), email=email)  # permanent human row
        db.session.add(person)
        db.session.flush()  # get person.id without committing yet
        user = User(person_id=person.id, username=username, is_active=True, must_change_password=True)
        user.set_password(temp)  # hashed, never stored plain
        db.session.add(user)
        db.session.flush()  # get user.id so AuditLog.record_id is filled (spec 7 auditability)
        year = SchoolYear.query.filter_by(is_active=True).first()  # occupant needs a yearly record
        if year is not None:
            db.session.add(Residency(person_id=person.id, school_year_id=year.id, status="active"))
        db.session.add(AuditLog(actor_id=current_user.id, action="user.create", table_name="user", record_id=user.id, reason="created " + username + " for " + email))
        db.session.commit()
        send_temp_password(email, username, temp)  # dev: console print (Step 2)
        flash("Created " + username + " -- temp password emailed (dev: see console).", "success")
        return redirect(url_for("auth.create_account"))
    return render_template("auth/create_account.html", form=form)

@auth_bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    """Request reset link by email (always says sent, even if email unknown)."""
    form = ForgotForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        person = Person.query.filter_by(email=email).first()
        if person is not None and person.user is not None:
            token = _reset_serializer().dumps(email)  # signed email, expires in 1h on verify
            send_reset_link(email, url_for("auth.reset", token=token, _external=True))
            db.session.add(AuditLog(action="password.reset.request", table_name="user", record_id=person.user.id, reason="reset for " + email))
            db.session.commit()
        flash("If that email exists, a reset link was sent (dev: see console).", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot.html", form=form)

@auth_bp.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    """Set new password from emailed link (1-hour expiry, bad/expired rejected)."""
    try:
        email = _reset_serializer().loads(token, max_age=3600)  # 3600s = 1 hour (your Q3)
    except Exception:
        flash("Reset link is invalid or expired.", "danger")
        return redirect(url_for("auth.forgot"))
    person = Person.query.filter_by(email=email).first()
    if person is None or person.user is None:
        flash("Reset link is invalid.", "danger")
        return redirect(url_for("auth.forgot"))
    form = ResetForm()
    if form.validate_on_submit():
        person.user.set_password(form.new.data)
        person.user.must_change_password = False  # fresh password counts as changed
        db.session.add(AuditLog(action="password.reset.done", table_name="user", record_id=person.user.id))
        db.session.commit()
        flash("Password reset -- please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset.html", form=form)

@auth_bp.route("/bootstrap", methods=["GET", "POST"])
def bootstrap():
    """ONE-SHOT first account for shell-less hosts (Render free tier). Safe to keep in the codebase:
    refuses (404) FOREVER once ANY user exists, so it can never create a second backdoor account.
    While the DB is empty, one commit creates everything fresh: Person + User (must_change=True),
    SchoolYear 2026-2027 + Sem1/Sem2, Super-admin role, Residency(status active -- you are an occupant)
    + RoleAssignment + AuditLog("bootstrap.create"). Then go to /login (forced change applies)."""
    if User.query.count() > 0:
        abort(404)  # already bootstrapped -> permanently inert, even if this URL leaks
    form = BootstrapForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if Person.query.filter_by(email=email).first() is not None:
            flash("Email already used.", "danger")
            return render_template("auth/bootstrap.html", form=form)
        username = _derive_username(email)  # email prefix + dedupe
        person = Person(name=form.name.data.strip(), email=email)
        db.session.add(person); db.session.flush()  # person.id
        user = User(person_id=person.id, username=username, is_active=True, must_change_password=True)
        user.set_password(form.password.data)  # chosen password = first temp; forced change at login still applies
        db.session.add(user); db.session.flush()  # user.id
        year = SchoolYear(label="2026-2027", is_active=True)
        db.session.add(year); db.session.flush()  # year.id
        db.session.add_all([Semester(school_year_id=year.id, name="Sem 1", is_active=True),
                            Semester(school_year_id=year.id, name="Sem 2")])
        res = Residency(person_id=person.id, school_year_id=year.id, status="active")  # owner IS an occupant
        db.session.add(res); db.session.flush()  # res.id
        role = Role(name="Super-admin", permissions=[], description="Bootstrap account role")
        db.session.add(role); db.session.flush()  # role.id
        db.session.add(RoleAssignment(residency_id=res.id, role_id=role.id, school_year_id=year.id,
                                      is_active=True, assigned_by=user.id))
        db.session.add(AuditLog(actor_id=user.id, action="bootstrap.create", table_name="user",
                                record_id=user.id, reason="first account via /bootstrap"))
        db.session.commit()
        flash("Account created -- log in as " + username + " (password change required next).", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/bootstrap.html", form=form)
