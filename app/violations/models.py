# app/violations/models.py -- Phase 2.1: HRAR violation lifecycle tables.
# CS50x map: each class = one table (was CREATE TABLE + db.execute). Rows = objects.
# Exact names from spec section 9 -- DO NOT rename, Phases 3-5 import these.
# State machine: Logged -> Confirmed/Dismissed -> Under Review -> Confirmed/Dismissed.
# Points count ONLY when Confirmed (Under Review pauses). Never edit points in place.
from datetime import datetime, timezone  # timestamps; naive UTC for SQLite safety
from app import db  # the SQLAlchemy() handle from factory (app/__init__.py)


def _utcnow():
    """Naive UTC now (SQLite-safe, matches Phase 1 model style)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ViolationRule(db.Model):
    """One HRAR rule (e.g. 2.B Sleep-out). Seeded from default_hrar.py (57 rules).

    Codes NEVER change (ViolationRecord.rule_id FKs them). Edits create a
    RuleVersion snapshot row instead of mutating history (spec 5.4).
    Rule 3.B (cleaning absence, confirmation='computed') is catalog-complete
    but NEVER manually logged -- Phase 4 computes it from attendance.
    """

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)  # "2.B" -- stable key
    section = db.Column(db.Integer, nullable=False)  # 1..8 (+9 for H house rules)
    section_title = db.Column(db.String(120), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    severity = db.Column(db.String(30), nullable=True)  # expulsion | 5_points | ...
    points = db.Column(db.Integer, default=0)  # HRAR deduction when Confirmed
    fine_type = db.Column(db.String(40), default="none")  # none|fixed|per_day|...
    fine_amount = db.Column(db.Integer, default=0)  # amount_php (0 when none)
    fine_meta = db.Column(db.JSON, default=dict)  # full fine object (destination_tag/...)
    escalation = db.Column(db.JSON, default=list)  # [{offense: N, actions: [...]}]
    who_can_log = db.Column(db.JSON, default=list)  # adviser|sa|justice_head|...
    is_confidential = db.Column(db.Boolean, default=False)  # advisers+Justice+President only
    confirmation = db.Column(db.String(20), default="adviser")  # auto_48h|adviser|computed
    applies_when = db.Column(db.String(20), default="always")  # always | closed_week
    version = db.Column(db.Integer, default=1)  # bumped on every admin edit
    is_active = db.Column(db.Boolean, default=True)  # False = retired (history kept)
    review_note = db.Column(db.String(10), nullable=True)  # N1..N11 cleanup note
    requires_victim_complaint = db.Column(db.Boolean, default=False)  # 1.D stealing
    penalty_options = db.Column(db.JSON, nullable=True)  # 1.M adviser picks one
    other_penalty = db.Column(db.JSON, nullable=True)  # confiscation/replacement text
    auto_source = db.Column(db.String(30), nullable=True)  # logbook | event_attendance | ...
    note = db.Column(db.Text, nullable=True)


class RuleVersion(db.Model):
    """Snapshot of a ViolationRule BEFORE each admin edit (append-only history)."""

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("violation_rule.id"), nullable=False)
    snapshot = db.Column(db.JSON, nullable=False)  # full rule dict before the change
    changed_by = db.Column(db.Integer, nullable=True)  # user id of the editor
    changed_at = db.Column(db.DateTime, default=_utcnow)
    reason = db.Column(db.String(255), nullable=True)  # why the rule changed (audited)

    rule = db.relationship("ViolationRule", backref="versions")


class ViolationRecord(db.Model):
    """One occupant breaking one rule (Logged -> Confirmed/Dismissed ...).

    offense_count auto = prior Confirmed count for same rule+semester+residency + 1.
    auto_confirm_at set only for minors (points<=3, no escalation, fine<50,
    not confidential) = now + auto_confirm_hours (Setting, default 48).
    fine_charge_id links to Phase 3 Charge once finance lands (NULL stub now).
    """

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("violation_rule.id"), nullable=False)
    residency_id = db.Column(db.Integer, db.ForeignKey("residency.id"), nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey("semester.id"), nullable=False)
    reporter_id = db.Column(db.Integer, nullable=True)  # hidden if anonymous
    is_anonymous = db.Column(db.Boolean, default=False)  # advisers/Justice/President only
    date = db.Column(db.Date, nullable=False)  # when it happened
    time = db.Column(db.Time, nullable=True)
    place = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    photo_path = db.Column(db.String(255), nullable=True)  # Pillow <=1280px uploads/
    offense_count = db.Column(db.Integer, default=1)  # computed at log time
    status = db.Column(db.String(20), default="Logged")  # Logged|Confirmed|...
    confirmed_by = db.Column(db.Integer, nullable=True)  # adviser user id
    confirmed_at = db.Column(db.DateTime, nullable=True)
    auto_confirm_at = db.Column(db.DateTime, nullable=True)  # None = needs adviser
    fine_amount = db.Column(db.Integer, default=0)  # snapshot of fine at log time
    fine_charge_id = db.Column(db.Integer, nullable=True)  # Phase 3 Charge link (stub)
    chosen_penalty = db.Column(db.JSON, nullable=True)  # 1.M: adviser-picked option
    notified_at = db.Column(db.DateTime, nullable=True)  # occupant notified
    created_at = db.Column(db.DateTime, default=_utcnow)

    rule = db.relationship("ViolationRule", backref="records")
    residency = db.relationship("Residency")  # occupant's year-record (person/room live here)


class Dispute(db.Model):
    """Occupant challenges a violation within dispute_days (Setting, default 3).

    Filing moves the record to Under Review (points paused). Reviewer must NOT
    be the reporter or the accused. Deciders: President + advisers.
    """

    id = db.Column(db.Integer, primary_key=True)
    violation_id = db.Column(db.Integer, db.ForeignKey("violation_record.id"), nullable=False)
    filed_by = db.Column(db.Integer, nullable=False)  # disputing occupant user id
    reason = db.Column(db.Text, nullable=False)
    filed_at = db.Column(db.DateTime, default=_utcnow)
    reviewed_by = db.Column(db.Integer, nullable=True)  # decider user id
    decision = db.Column(db.String(20), nullable=True)  # Confirmed | Dismissed
    decision_reason = db.Column(db.Text, nullable=True)
    decided_at = db.Column(db.DateTime, nullable=True)

    violation = db.relationship("ViolationRecord", backref="disputes")


class EscalationFlag(db.Model):
    """Probation / expulsion flag for a residency (adviser DECIDES, system flags)."""

    id = db.Column(db.Integer, primary_key=True)
    residency_id = db.Column(db.Integer, db.ForeignKey("residency.id"), nullable=False)
    type = db.Column(db.String(30), nullable=False)  # probation | expulsion_flag
    reason = db.Column(db.String(255), nullable=False)  # e.g. "2.A offense #3"
    violation_id = db.Column(db.Integer, db.ForeignKey("violation_record.id"), nullable=True)
    resolved = db.Column(db.Boolean, default=False)  # True once adviser acts
    created_at = db.Column(db.DateTime, default=_utcnow)
