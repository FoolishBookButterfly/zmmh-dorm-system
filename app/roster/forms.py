# app/roster/forms.py -- Phase 1.3 Step 3: forms for assigning roles + per-person grants
# CS50x map: CS50x used request.form.get + manual checks. Flask-WTF gives CSRF + validation free.
from flask_wtf import FlaskForm  # base: CSRF token via form.hidden_tag()
from wtforms import SelectMultipleField, StringField, RadioField, DateField, SubmitField, HiddenField  # field types
from wtforms.validators import DataRequired, Length, Optional  # rules per field
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
