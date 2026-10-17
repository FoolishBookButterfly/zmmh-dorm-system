# app/roster/forms.py -- Phase 1.3 Step 3: forms for assigning roles + per-person grants
# CS50x map: CS50x used request.form.get + manual checks. Flask-WTF gives CSRF + validation free.
from flask_wtf import FlaskForm  # base: CSRF token via form.hidden_tag()
from wtforms import SelectMultipleField, StringField, RadioField, DateField, SubmitField, HiddenField, SelectField, IntegerField, BooleanField, TextAreaField  # field types
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError  # rules per field
from flask_wtf.file import FileField, FileAllowed, FileRequired  # upload validators (import page)
from wtforms.widgets import ListWidget, CheckboxInput  # render a multi-select as a stack of checkboxes


class MultiCheckboxField(SelectMultipleField):
    """SelectMany rendered as tick-boxes (one <input checkbox> per role, not a dropdown)."""
    widget = ListWidget(prefix_label=False)  # label AFTER the box
    option_widget = CheckboxInput()  # each choice = a checkbox


class RoleForm(FlaskForm):
    """Tick/untick roles for ONE occupant (roles STACK -- permissions add up, spec section 3)."""
    # choices are set in the route: form.roles.choices = [(role.name, role.name) for role in roles]
    roles = MultiCheckboxField("Roles", validators=[], default=[])
    save_roles = SubmitField("Save roles")  # unique name -> route checks request.form.get("save_roles")


# Suggestions shown in the grant textbox (datalist). New perms get added here as phases ship.
KNOWN_PERMISSIONS = [
    "roster.view", "roster.export", "roster.view_private", "roster.edit", "role.assign",
    "finance.view", "finance.edit", "finance.receipts", "finance.expenses",
    "violations.view", "violations.log", "violations.confirm",
    "events.view", "events.edit", "events.attendance",
    "cleaning.view", "cleaning.edit",
    "evaluation.view", "evaluation.enter", "evaluation.lock", "evaluation.release",
    "settings.view", "audit.view", "tickets.view", "announcements.post",
    "disputes.review", "clearance.edit", "clearance.room_inspect",
]


class GrantForm(FlaskForm):
    """One extra allow/deny for this person, optional expiry (PermissionGrant, Plate 2B)."""
    permission = StringField("Permission", validators=[DataRequired(), Length(max=80)])  # pick from datalist or type
    allow = RadioField("Effect", choices=[("1", "Allow (extra)"), ("0", "Deny (blocks even if a role allows)")], default="1")
    expires = DateField("Expires (optional, empty = forever)", validators=[Optional()], format="%Y-%m-%d")
    add_grant = SubmitField("Add grant")  # unique name -> route checks request.form.get("add_grant")


class RevokeGrantForm(FlaskForm):
    """Tiny per-row form: revoke = DELETE that grant row (grants are overrides, not history)."""
    grant_id = HiddenField(validators=[DataRequired()])  # which grant to remove (hidden input)
    revoke = SubmitField("Revoke")  # unique name -> route checks request.form.get("revoke")

class RoomForm(FlaskForm):
    """Edit ONE room: name is unique, capacity >= 1. Lowering below occupancy is blocked in the route."""
    name = StringField("Room name", validators=[DataRequired(), Length(max=80)])
    capacity = IntegerField("Beds", validators=[DataRequired(), NumberRange(min=1, message="Capacity must be at least 1.")])
    save_room = SubmitField("Save room")  # unique name -> route checks request.form.get("save_room")


class AssignmentForm(FlaskForm):
    """Assign ONE occupant to a room for a semester; tick = this semester's Big Brod (unique per room)."""
    # choices injected by the route (active-year residencies + semester list)
    residency_id = SelectField("Occupant", coerce=int, validators=[DataRequired()])  # value = Residency.id
    semester_id = SelectField("Semester", coerce=int, validators=[DataRequired()])  # value = Semester.id
    is_big_brod = BooleanField("Big Brod (the one stayer for this room)")
    move_reason = TextAreaField("Reason (required when moving/unticking, audited)", validators=[Length(max=255)])
    save_assignment = SubmitField("Assign")  # unique name -> route checks request.form.get("save_assignment")


def _csv_ext(form, field):
    """Extra guard: filename must end .csv (FileAllowed checks content type; this checks the tail)."""
    if field.data and not field.data.filename.lower().endswith(".csv"):
        raise ValidationError("File must end in .csv.")


class ImportForm(FlaskForm):
    """Upload the roster CSV (name,email,birthday,address,contact_number,emergency_contact,course_year,room).
    Server parses with csv module; route does dry-run preview BEFORE any commit."""
    file = FileField("Roster CSV", validators=[FileRequired(), FileAllowed(["csv"], "CSV only."), _csv_ext])
    preview = SubmitField("Preview import")  # unique name -> route checks request.form.get("preview")


class CommitImportForm(FlaskForm):
    """Second step: carries CSRF + the staging token so COMMIT is CSRF-validated too."""
    stage_token = HiddenField("staged file token", validators=[DataRequired()])
    commit = SubmitField("Commit import")  # unique name -> route checks request.form.get("commit")


class SettingsSaveForm(FlaskForm):
    """CSRF-only carrier for the grouped settings posts.
    Flask-WTF provides csrf_token automatically; no need to redefine it.
    The route reads named inputs directly (save_form.validate_on_submit()) which
    still runs CSRF validation. The template includes {{ save_form.csrf_token }}.
    """
    pass

