# app/violations/forms.py -- Phase 2.2 rules admin + Phase 2.3 log form.
# CS50x map: CS50x used request.form.get + manual checks. Flask-WTF gives CSRF + validation free.
from datetime import date as _date  # default violation date = today
from flask_wtf import FlaskForm  # base: CSRF token via form.hidden_tag()
from flask_wtf.file import FileField, FileAllowed  # photo upload (optional)
from wtforms import StringField, TextAreaField, IntegerField, SelectField, BooleanField, SubmitField, DateField, TimeField, HiddenField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, AnyOf
from wtforms.widgets import ListWidget, CheckboxInput  # occupant multi-select as tick-boxes
from wtforms import SelectMultipleField


#: Logger role keys used in who_can_log checkboxes (must match default_hrar.py).
LOGGER_CHOICES = [
    ("adviser", "Adviser"),
    ("sa", "SA"),
    ("justice_head", "Justice head"),
    ("kitchen_head", "Kitchen head"),
    ("igp_head", "IGP head"),
    ("secretary", "Secretary"),
]

#: Confirmation modes: auto_48h = minor (48h auto-confirm), adviser = major,
#: computed = system-calculated (3.B cleaning absence -- never manually logged).
CONFIRMATION_CHOICES = [
    ("auto_48h", "Minor: auto-confirm after 48h"),
    ("adviser", "Major: needs adviser confirm"),
    ("computed", "Computed: system-calculated, never logged by hand"),
]

#: Fine types from the HRAR catalog.
FINE_TYPE_CHOICES = [
    ("none", "No fine"),
    ("fixed", "Fixed amount (PHP)"),
    ("per_day", "Per day (PHP)"),
    ("per_month", "Per month (PHP)"),
    ("per_absence_after_threshold", "Per absence after threshold (PHP)"),
]

#: When the rule applies.
APPLIES_WHEN_CHOICES = [
    ("always", "Always"),
    ("closed_week", "Closed week only"),
]

#: Canonical outcome-code actions for the escalation ladder (HRAR outcome_codes).
ESCALATION_ACTIONS = [
    "warning", "verbal_warning", "probation", "flag_expulsion",
    "confiscation", "no_fan_one_week", "hard_labor", "move_out",
]


class RuleForm(FlaskForm):
    """Add / edit ONE HRAR rule. Code is immutable after creation (stable FK key).

    Escalation ladder entered as text lines "offense: action, action" e.g.
    "1: warning" / "2: probation" / "3: flag_expulsion" (parsed in the route).
    who_can_log entered as comma-separated role keys (validated against LOGGER_CHOICES).
    """

    code = StringField("Code (e.g. 2.B, H.1 -- never changes after creation)",
                       validators=[DataRequired(), Length(max=10)])
    section = IntegerField("Section (1-8 HRAR, 9 = officer house rules)",
                           validators=[DataRequired(), NumberRange(min=1, max=9)])
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    severity = StringField("Severity (expulsion | 5_points | 3_points | 1_point | ...)",
                           validators=[Optional(), Length(max=30)])
    points = IntegerField("HRAR points deducted when Confirmed",
                          validators=[DataRequired(), NumberRange(min=0, max=100)])
    fine_type = SelectField("Fine type", choices=FINE_TYPE_CHOICES, validators=[DataRequired()])
    fine_amount = IntegerField("Fine amount (PHP, 0 = none)",
                               validators=[DataRequired(), NumberRange(min=0, max=100000)])
    confirmation = SelectField("Confirmation mode", choices=CONFIRMATION_CHOICES,
                               validators=[DataRequired()])
    applies_when = SelectField("Applies when", choices=APPLIES_WHEN_CHOICES,
                               validators=[DataRequired()])
    is_confidential = BooleanField("Confidential (advisers + Justice head + President only)")
    who_can_log = StringField("Who may log (comma role keys: adviser, sa, justice_head, ...)",
                              validators=[DataRequired(), Length(max=200)])
    escalation_text = TextAreaField(
        "Escalation ladder (one per line: 'offense: action, action')",
        validators=[Optional(), Length(max=1000)],
        description="e.g. 1: warning / 2: probation / 3: flag_expulsion")
    is_active = BooleanField("Active (untick to retire; history kept)", default=True)
    change_reason = StringField("Reason for this change (audited, required)",
                                validators=[DataRequired(), Length(max=255)])
    save_rule = SubmitField("Save rule")


class LogViolationForm(FlaskForm):
    """Phase 2.3: log ONE rule against ONE OR MORE occupants.

    Choices are injected by the route:
      - rule_id: only ACTIVE, non-computed rules the logger may log (who_can_log)
      - occupants: residencies of the ACTIVE year + active semester (Status=active)
    Photo is optional (Pillow compresses to <=1280px in the route).
    Anonymous hides the reporter from the occupant (visible to advisers/
    Justice head/President only, Decision 7).
    """

    # choices set in the route before render
    rule_id = SelectField("HRAR rule", coerce=int, validators=[DataRequired()])
    occupants = SelectMultipleField("Occupant(s)", coerce=int, validators=[DataRequired()])
    date = DateField("Date it happened", validators=[DataRequired()], format="%Y-%m-%d")
    time = TimeField("Time (optional)", validators=[Optional()])
    place = StringField("Place (e.g. Kitchen, Room Melbourne)", validators=[Optional(), Length(max=120)])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    photo = FileField("Photo (optional, JPG/PNG/WebP, max 1280px)", validators=[
        Optional(), FileAllowed(["jpg", "jpeg", "png", "webp"], "Photo must be JPG, PNG or WebP.")])
    is_anonymous = BooleanField("Report anonymously (reporter hidden from the occupant)")
    log_violation = SubmitField("Log violation")

    def __init__(self, *args, **kwargs):
        """Default date = today (most violations are logged the same day)."""
        super().__init__(*args, **kwargs)
        if not self.date.data:
            self.date.data = _date.today()


class DisputeForm(FlaskForm):
    """Phase 2.5: occupant challenges a Logged/Confirmed violation (reason required)."""
    reason = TextAreaField("Why are you disputing this? (required, audited)",
                           validators=[DataRequired(), Length(max=2000)])
    file_dispute = SubmitField("File dispute")




class ReviewActionForm(FlaskForm):
    """Phase 2.4: adviser Confirm / Dismiss a Logged violation (reason required)."""
    record_id = HiddenField(validators=[DataRequired()])
    reason = TextAreaField("Reason (required, audited)", validators=[DataRequired(), Length(max=500)])
class DisputeDecisionForm(FlaskForm):
    """Phase 2.5: President + advisers decide a disputed violation (reason required)."""
    record_id = HiddenField(validators=[DataRequired()])
    reason = TextAreaField("Decision reason (required, audited)",
                           validators=[DataRequired(), Length(max=500)])
    confirm = SubmitField("Uphold (Confirmed)")
    dismiss = SubmitField("Dismiss")
