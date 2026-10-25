# app/auth/routes.py -- REAL auth (Phase 1.2): login/logout/forced-change/create/forgot/reset
# CS50x map: CS50x did session[user_id] + apology. Here Flask-Login + WTForms + audit on everything.
import secrets  # temp password generation (secrets.token_urlsafe = secure random)
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort  # web helpers (+abort for bootstrap)
from flask_login import login_user, logout_user, login_required, current_user  # session handling
from itsdangerous import URLSafeTimedSerializer  # reset tokens (no new package needed)
from app import db  # commit Person/User/Residency/AuditLog rows
# Exact 1.1 model names -- DO NOT rename
from app.roster.models import Person, User, SchoolYear, Semester, Residency, Role, RoleAssignment, Room, AuditLog  # + Room for /seed-rooms
from app.roster.models import Setting  # + Setting for /seed-settings
from app.violations.models import ViolationRule  # + ViolationRule for /seed-hrar (Phase 2.1)
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
            from datetime import date as _date  # local import: mid-year joiners counted only from today
            db.session.add(Residency(person_id=person.id, school_year_id=year.id, status="active", joined_at=_date.today()))
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
        role = Role.query.filter_by(name="Super-admin").first()  # get-or-create: /seed-roles may have seeded it FIRST
        if role is None:
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

@auth_bp.route("/seed-roles")
def seed_roles():
    """ONE-SHOT role-catalog seeder for shell-less hosts (Render free tier). Sibling of /bootstrap.
    Safe to keep forever: 404s once ALL 17 catalog names exist AND their permission bundles
    match the catalog (re-visits self-heal stale bundles, then go inert again).
    Anonymous-safe: it only writes the deterministic Role ROWS the code already defines;
    granting them to anyone still requires login + role.assign via /admin/roles (which auditors see)."""
    from app.roster.default_roles import ROLES  # local import: one catalog for shell + route
    existing = {r.name: r for r in Role.query.all()}
    missing = [n for n in ROLES if n not in existing]
    stale = [n for n in ROLES if n in existing
             and list((existing[n].permissions or [])) != list(ROLES[n])]
    if not missing and not stale:
        abort(404)  # catalog complete and current -> permanently inert
    created, refreshed = [], []
    for name in missing:
        db.session.add(Role(name=name, permissions=ROLES[name], description="Seeded via /seed-roles"))
        created.append(name)
    for name in stale:
        existing[name].permissions = ROLES[name]
        refreshed.append(name)
    db.session.add(AuditLog(actor_id=current_user.id if current_user.is_authenticated else None,
                            action="seed.roles", table_name="role", record_id=None,
                            reason="seeded: " + ", ".join(created)
                                   + ("; refreshed bundles: " + ", ".join(refreshed) if refreshed else "")))
    db.session.commit()
    parts = []
    if created:
        parts.append("Seeded roles: " + ", ".join(created))
    if refreshed:
        parts.append("Refreshed bundles: " + ", ".join(refreshed))
    return "; ".join(parts) + " (%d total)" % Role.query.count()

@auth_bp.route("/seed-rooms")
def seed_rooms():
    """ONE-SHOT room seeder for shell-less hosts (Render free tier). Sibling of /seed-roles.
    Safe to keep forever: 404s once ALL 20 catalog names exist, so it can create nothing twice.
    Creates only deterministic Room ROWS the code already defines; assignments still need
    login + roster.edit via the rooms pages (audited there)."""
    from app.roster.default_rooms import ROOMS  # local import: one catalog for shell + route
    existing = {r.name for r in Room.query.all()}
    missing = [n for n in ROOMS if n not in existing]
    if not missing:
        abort(404)  # catalog complete -> permanently inert
    created = []
    for name in missing:
        db.session.add(Room(name=name, capacity=ROOMS[name]))
        created.append(name)
    db.session.add(AuditLog(actor_id=current_user.id if current_user.is_authenticated else None,
                            action="seed.rooms", table_name="room", record_id=None,
                            reason="seeded: " + ", ".join(created)))
    db.session.commit()
    total = sum(r.capacity for r in Room.query.all())
    return "Seeded rooms: " + ", ".join(created) + " (%d total, %d beds)" % (Room.query.count(), total)

@auth_bp.route("/seed-settings")
def seed_settings():
    """ONE-SHOT settings seeder for shell-less hosts (Render). Sibling of /seed-roles and /seed-rooms.
    Safe to keep forever: 404s once ALL catalog keys exist. Creates only deterministic Setting ROWS
    the code already defines; edits still need login + settings.view via /admin/settings (audited)."""
    from app.roster.default_settings import SETTINGS  # local import: one catalog for shell + route
    existing = {row.key for row in Setting.query.all()}
    missing = [k for k in SETTINGS if k not in existing]
    if not missing:
        abort(404)  # catalog complete -> permanently inert
    created = []
    for key in missing:
        meta = SETTINGS[key]
        db.session.add(Setting(key=key, value=meta["value"], description=meta["label"]))
        created.append(key)
    db.session.add(AuditLog(actor_id=current_user.id if current_user.is_authenticated else None,
                            action="seed.settings", table_name="setting", record_id=None,
                            reason="seeded: " + ", ".join(created)))
    db.session.commit()
    return "Seeded settings: " + ", ".join(created) + " (%d total)" % Setting.query.count()


@auth_bp.route("/seed-hrar")
def seed_hrar():
    """ONE-SHOT HRAR seeder for shell-less hosts (Render). Sibling of /seed-roles.

    Safe to keep forever: 404s once ALL 57 catalog codes exist AND stored fields
    match the catalog (re-visits self-heal drifted rows, then go inert again).
    Also ensures auto_confirm_hours=48 exists.
    Creates only deterministic ViolationRule ROWS the code already defines;
    logging/confirming still needs login + violations.* via the violations pages.
    """
    from app.roster.default_hrar import RULES, SECTION_TITLES  # local import: one catalog
    # Ensure the auto-confirm window setting exists too.
    auto = Setting.query.filter_by(key="auto_confirm_hours").first()
    if auto is None:
        db.session.add(Setting(key="auto_confirm_hours", value="48",
                               description="Auto-confirm window (hours) for minor violations"))
    existing = {r.code: r for r in ViolationRule.query.all()}

    def _fields(code, meta):
        return dict(
            section=meta["section"],
            section_title=SECTION_TITLES.get(meta["section"], ""),
            title=meta["title"], description=meta["description"],
            severity=meta["severity"], points=meta.get("points") or 0,
            fine_type=meta["fine"].get("type", "none"),
            fine_amount=meta["fine"].get("amount_php", 0) or 0,
            fine_meta=meta["fine"], escalation=meta.get("escalation", []),
            who_can_log=meta.get("who_can_log", []),
            is_confidential=bool(meta.get("confidential", False)),
            confirmation=meta.get("confirmation", "adviser"),
            applies_when=meta.get("applies_when", "always"),
            review_note=meta.get("review"),
            requires_victim_complaint=bool(meta.get("requires_victim_complaint", False)),
            penalty_options=meta.get("penalty_options"),
            other_penalty=meta.get("other_penalty"),
            auto_source=meta.get("auto_source"), note=meta.get("note"),
        )

    missing = [c for c in RULES if c not in existing]
    stale = [c for c in RULES if c in existing
             and any(getattr(existing[c], k) != v for k, v in _fields(c, RULES[c]).items())]
    if not missing and not stale and auto is not None:
        abort(404)  # catalog complete and current -> permanently inert
    created, refreshed = [], []
    for code in missing:
        db.session.add(ViolationRule(code=code, **_fields(code, RULES[code])))
        created.append(code)
    for code in stale:
        for k, v in _fields(code, RULES[code]).items():
            setattr(existing[code], k, v)
        refreshed.append(code)
    db.session.add(AuditLog(actor_id=current_user.id if current_user.is_authenticated else None,
                            action="seed.hrar", table_name="violation_rule", record_id=None,
                            reason="seeded: " + ", ".join(created)
                                   + ("; refreshed: " + ", ".join(refreshed) if refreshed else "")))
    db.session.commit()
    parts = []
    if created:
        parts.append("Seeded rules: " + ", ".join(created))
    if refreshed:
        parts.append("Refreshed rules: " + ", ".join(refreshed))
    return "; ".join(parts) + " (%d total)" % ViolationRule.query.count()

