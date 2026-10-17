# app/roster/models.py — Phase 1.1: people, years, rooms, roles, settings, audit
# CS50x map: each class = one table (was CREATE TABLE + db.execute). Rows = objects.
# Exact names from spec section 9 — DO NOT rename, later phases import these.
from datetime import datetime, timezone  # timestamps; timezone= for deprecated utcnow() replacement
from flask_login import UserMixin  # gives User is_authenticated/is_active/get_id for Flask-Login
from app import db  # the SQLAlchemy() handle from factory (app/__init__.py)
from werkzeug.security import generate_password_hash, check_password_hash  # CS50x hash helpers, same as Finance


class Person(db.Model):
    """Permanent human across ALL years (Juan Dela Cruz forever). Residency = him in one year."""

    id = db.Column(db.Integer, primary_key=True)  # row id, auto-increments
    name = db.Column(db.String(120), nullable=False)  # full name, required
    email = db.Column(db.String(120), unique=True, nullable=False)  # login contact, no dupes
    birthday = db.Column(db.Date, nullable=True)  # private: only President/Secretary/Advisers see
    address = db.Column(db.String(255), nullable=True)  # private field
    contact_number = db.Column(db.String(40), nullable=True)  # phone
    emergency_contact = db.Column(db.String(255), nullable=True)  # private field
    course_year = db.Column(db.String(120), nullable=True)  # e.g. "BS CS 2"
    photo_path = db.Column(db.String(255), nullable=True)  # optional photo file path
    cannot_reapply = db.Column(db.Boolean, default=False)  # True if Failed/Expelled (blocks re-add)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))  # naive UTC (SQLite-safe)

    # One person -> one login (User) + many year-records (Residency)
    user = db.relationship("User", backref="person", uselist=False, cascade="all, delete-orphan")
    residencies = db.relationship("Residency", backref="person", lazy=True, cascade="all, delete-orphan")


class User(db.Model, UserMixin):
    """Login account 1:1 with Person. Flask-Login uses this for current_user + @login_required."""

    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), unique=True, nullable=False)  # 1:1 link
    username = db.Column(db.String(80), unique=True, nullable=False)  # emailed by adviser
    password_hash = db.Column(db.String(255), nullable=False)  # NEVER store plain password
    is_active = db.Column(db.Boolean, default=True)  # False = deactivated (never delete accounts)
    must_change_password = db.Column(db.Boolean, default=True)  # True forces /change-password at first login

    def set_password(self, raw):  # CS50x generate_password_hash, same as Finance
        """Hash and store a new password."""
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):  # CS50x check_password_hash
        """True if raw matches stored hash."""
        return check_password_hash(self.password_hash, raw)


class SchoolYear(db.Model):
    """One school year, e.g. 2026-2027. Only one active at a time. First year has no history."""

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(20), unique=True, nullable=False)  # "2026-2027"
    is_active = db.Column(db.Boolean, default=False)  # True for current year

    semesters = db.relationship("Semester", backref="school_year", lazy=True, cascade="all, delete-orphan")
    residencies = db.relationship("Residency", backref="school_year", lazy=True)


class Semester(db.Model):
    """Sem 1 / Sem 2 inside a SchoolYear. Offenses, absences, points reset each semester."""

    id = db.Column(db.Integer, primary_key=True)
    school_year_id = db.Column(db.Integer, db.ForeignKey("school_year.id"), nullable=False)
    name = db.Column(db.String(20), nullable=False)  # "Sem 1" or "Sem 2"
    is_active = db.Column(db.Boolean, default=False)  # True for current semester


class Residency(db.Model):
    """Person IN one SchoolYear: roles, status, scores for that year. Person lives on, Residency is yearly."""

    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=False)
    school_year_id = db.Column(db.Integer, db.ForeignKey("school_year.id"), nullable=False)
    status = db.Column(db.String(30), default="active")  # active/staff/Retained/Waitlisted/Recommended/Failed/Expelled/Graduating (staff = NON-OCCUPANT staff e.g. adviser: roles anchor only, never ranked/counted. Super-admin MAY be an occupant)

    room_assignments = db.relationship("RoomAssignment", backref="residency", lazy=True, cascade="all, delete-orphan")
    role_assignments = db.relationship("RoleAssignment", backref="residency", lazy=True, cascade="all, delete-orphan")
    permission_grants = db.relationship("PermissionGrant", backref="residency", lazy=True, cascade="all, delete-orphan")


class Room(db.Model):
    """Fixed dorm room (20 rooms, 120 beds; Melbourne largest with 12). Capacity editable."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)  # "Melbourne"
    capacity = db.Column(db.Integer, nullable=False)  # beds, e.g. 12

    assignments = db.relationship("RoomAssignment", backref="room", lazy=True)


class RoomAssignment(db.Model):
    """Who sleeps where, per semester. Only one Big Brod stays per room across semesters."""

    id = db.Column(db.Integer, primary_key=True)
    residency_id = db.Column(db.Integer, db.ForeignKey("residency.id"), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey("semester.id"), nullable=False)
    is_big_brod = db.Column(db.Boolean, default=False)  # True = the one stayer; warn if >1 per room
    move_reason = db.Column(db.String(255), nullable=True)  # admin must give reason when moving (audited)
    semester = db.relationship("Semester", backref="room_assignments")


class Role(db.Model):
    """Named bundle of permissions (President, SA, Treasurer...). Permissions add up when stacked."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)  # "Treasurer"
    permissions = db.Column(db.JSON, default=list)  # e.g. ["finance.view", "finance.edit"]
    description = db.Column(db.String(255), nullable=True)


class RoleAssignment(db.Model):
    """Gives one Residency one Role for one year. A person can hold several at once (stack)."""

    id = db.Column(db.Integer, primary_key=True)
    residency_id = db.Column(db.Integer, db.ForeignKey("residency.id"), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("role.id"), nullable=False)
    school_year_id = db.Column(db.Integer, db.ForeignKey("school_year.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True)  # False ends temp roles (e.g. Evaluator after release)
    assigned_by = db.Column(db.Integer, nullable=True)  # user id of adviser/super-admin who assigned
    role = db.relationship("Role", backref="assignments")


class PermissionGrant(db.Model):
    """One extra allow/deny for one person, optionally expiring. Overrides/adds to role perms."""

    id = db.Column(db.Integer, primary_key=True)
    residency_id = db.Column(db.Integer, db.ForeignKey("residency.id"), nullable=False)
    permission = db.Column(db.String(80), nullable=False)  # e.g. "roster.view_private"
    allow = db.Column(db.Boolean, default=True)  # True = grant, False = revoke
    expires_at = db.Column(db.DateTime, nullable=True)  # None = no expiry
    granted_by = db.Column(db.Integer, nullable=True)  # adviser/super-admin user id


class Setting(db.Model):
    """Editable values that live in DB, NOT in code (spec section 7): weights, margins, fees."""

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)  # e.g. "danger_margin"
    value = db.Column(db.String(255), nullable=False)  # stored as string, parsed by code
    description = db.Column(db.String(255), nullable=True)


class AuditLog(db.Model):
    """Append-only trail: who changed what, when, why. NEVER delete or edit rows here."""

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, nullable=True)  # user id who acted
    action = db.Column(db.String(80), nullable=False)  # e.g. "role.assign", "payment.record"
    table_name = db.Column(db.String(80), nullable=True)  # which table changed
    record_id = db.Column(db.Integer, nullable=True)  # which row changed
    old_value = db.Column(db.Text, nullable=True)  # JSON before
    new_value = db.Column(db.Text, nullable=True)  # JSON after
    reason = db.Column(db.String(255), nullable=True)  # required for scores/money changes
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))  # naive UTC
