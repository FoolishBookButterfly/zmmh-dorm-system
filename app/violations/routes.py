# app/violations/routes.py -- Phase 2.2 rules admin + Phase 2.3 log form.
# CS50x map: CS50x did SELECT/UPDATE by hand; here ORM + RuleVersion snapshots + AuditLog.
import json  # readable old/new snapshots inside AuditLog + RuleVersion
from datetime import timedelta  # auto_confirm_at = now + auto_confirm_hours
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required

from app import db  # commit rows
from app.violations.models import ViolationRule, RuleVersion, ViolationRecord, _utcnow  # 2.1 models + log model
from app.roster.models import AuditLog, SchoolYear, Residency, RoleAssignment, Person, Semester, Role  # audit + people
from app.violations.forms import RuleForm, LogViolationForm, LOGGER_CHOICES, ESCALATION_ACTIONS
from app.roster.default_hrar import SECTION_TITLES  # section titles for new rules
from app.utils.decorators import permission_required, has_permission  # central gate
from app.utils.settings import get_int_setting  # auto_confirm_hours + dispute_days, NEVER hardcode
from app.utils.photos import save_violation_photo  # Pillow <=1280px
from app.utils.email import send_violation_notice  # occupant notification (dev console print)

violations_bp = Blueprint("violations", __name__, url_prefix="/violations")


def _audit(action, table_name, record_id, old=None, new=None, reason=None):
    """Append-only audit row (scores/money changes REQUIRE reason)."""
    db.session.add(AuditLog(actor_id=current_user.id, action=action, table_name=table_name,
                            record_id=record_id, old_value=old, new_value=new, reason=reason))


def _my_role_names():
    """Role NAMES the current user holds in the active year (HRAR-level filters)."""
    if not getattr(current_user, "is_authenticated", False):
        return set()
    year = SchoolYear.query.filter_by(is_active=True).first()
    if year is None:
        return set()
    res_ids = [r.id for r in Residency.query.filter_by(
        person_id=current_user.person_id, school_year_id=year.id).all()]
    if not res_ids:
        return set()
    assigns = RoleAssignment.query.filter(
        RoleAssignment.residency_id.in_(res_ids),
        RoleAssignment.school_year_id == year.id,
        RoleAssignment.is_active.is_(True)).all()
    return set(a.role.name for a in assigns if a.role is not None)


def _may_see_confidential():
    """True if user may see confidential rules (Decision 7: advisers+Justice+President)."""
    if has_permission(current_user, "violations.confirm"):  # advisers (+super-admin)
        return True
    return bool(_my_role_names() & {"Justice head", "President"})


def _parse_who_can_log(raw):
    """Validate comma role keys -> list. Raises ValueError on unknown key."""
    valid = set(k for k, _ in LOGGER_CHOICES) | {"president"}
    parts = [p.strip().lower() for p in (raw or "").split(",") if p.strip()]
    bad = [p for p in parts if p not in valid]
    if bad:
        raise ValueError("Unknown logger role(s): %s (use: %s)"
                         % (", ".join(bad), ", ".join(sorted(valid))))
    if not parts:
        raise ValueError("Who-may-log needs at least one role key.")
    return parts


def _parse_escalation(raw):
    """Parse 'offense: action, action' lines -> [{offense, actions}]. ValueError on bad lines."""
    ladder = []
    for lineno, line in enumerate((raw or "").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError("Line %d: use 'offense: action, action'." % lineno)
        num, acts = line.split(":", 1)
        try:
            offense = int(num.strip())
        except ValueError:
            raise ValueError("Line %d: offense must be a number." % lineno)
        actions = [a.strip() for a in acts.split(",") if a.strip()]
        bad = [a for a in actions if a not in ESCALATION_ACTIONS]
        if not actions or bad:
            raise ValueError("Line %d: actions from %s." % (lineno, ", ".join(ESCALATION_ACTIONS)))
        ladder.append({"offense": offense, "actions": actions})
    ladder.sort(key=lambda e: e["offense"])
    return ladder


def _escalation_to_text(ladder):
    """Ladder -> edit-box text ('1: warning' per line)."""
    return "\n".join("%d: %s" % (e["offense"], ", ".join(e["actions"])) for e in (ladder or []))


@violations_bp.route("/rules")
@login_required
@permission_required("violations.view")
def rules():
    """HRAR rulebook grouped by section. Confidential rows (1.D, 1.F) show ONLY
    for advisers + Justice head + President (Decision 7) -- others get the count."""
    show_hidden = _may_see_confidential()
    all_rules = ViolationRule.query.order_by(ViolationRule.section, ViolationRule.code).all()
    visible, hidden_count = [], 0
    for r in all_rules:
        if r.is_confidential and not show_hidden:
            hidden_count += 1
            continue
        visible.append(r)
    sections = []
    for sec in sorted(set(r.section for r in visible)):
        rows = [r for r in visible if r.section == sec]
        sections.append({"num": sec, "title": SECTION_TITLES.get(sec, ""), "rows": rows})
    return render_template("violations/rules.html", sections=sections,
                           hidden_count=hidden_count, show_hidden=show_hidden,
                           total=len(all_rules))


@violations_bp.route("/rules/add", methods=["GET", "POST"])
@login_required
@permission_required("violations.confirm")  # advisers (+super-admin) only
def rule_add():
    """Add ONE rule (officer house rules: section 9, code H.N). Codes unique + immutable."""
    form = RuleForm()
    if request.form.get("save_rule") and form.validate_on_submit():
        code = (form.code.data or "").strip()
        if ViolationRule.query.filter_by(code=code).first() is not None:
            flash("Blocked: code '%s' already exists (codes never change)." % code, "danger")
            return redirect(url_for("violations.rule_add"))
        try:
            loggers = _parse_who_can_log(form.who_can_log.data)
            ladder = _parse_escalation(form.escalation_text.data)
        except ValueError as e:
            flash(str(e), "danger")
            return render_template("violations/rule_form.html", form=form, mode="add", rule=None)
        rule = ViolationRule(
            code=code, section=form.section.data, title=form.title.data.strip(),
            section_title=SECTION_TITLES.get(form.section.data, ""),
            description=(form.description.data or "").strip() or None,
            severity=(form.severity.data or "").strip() or None,
            points=form.points.data, fine_type=form.fine_type.data,
            fine_amount=form.fine_amount.data,
            fine_meta={"type": form.fine_type.data, "amount_php": form.fine_amount.data},
            escalation=ladder, who_can_log=loggers,
            is_confidential=bool(form.is_confidential.data),
            confirmation=form.confirmation.data, applies_when=form.applies_when.data,
            is_active=bool(form.is_active.data), version=1)
        db.session.add(rule)
        db.session.flush()  # rule.id for the audit row
        _audit("rule.add", "violation_rule", rule.id,
               new=json.dumps({"code": code, "title": rule.title}),
               reason=form.change_reason.data.strip())
        db.session.commit()
        flash("Rule %s added." % code, "success")
        return redirect(url_for("violations.rules"))
    return render_template("violations/rule_form.html", form=form, mode="add", rule=None)


def _rule_snapshot(rule):
    """Full rule dict for RuleVersion.snapshot (before-image of an edit)."""
    return {"code": rule.code, "section": rule.section, "title": rule.title,
            "description": rule.description, "severity": rule.severity,
            "points": rule.points, "fine_type": rule.fine_type,
            "fine_amount": rule.fine_amount, "fine_meta": rule.fine_meta,
            "escalation": rule.escalation, "who_can_log": rule.who_can_log,
            "is_confidential": rule.is_confidential, "confirmation": rule.confirmation,
            "applies_when": rule.applies_when, "version": rule.version,
            "is_active": rule.is_active}


@violations_bp.route("/rules/<int:rule_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("violations.confirm")
def rule_edit(rule_id):
    """Edit ONE rule: snapshot BEFORE-image into RuleVersion, bump version, audit."""
    rule = ViolationRule.query.get_or_404(rule_id)
    if rule.is_confidential and not _may_see_confidential():
        flash("Confidential rule: advisers, Justice head and President only.", "danger")
        return redirect(url_for("violations.rules"))
    form = RuleForm()
    if request.method == "GET":
        form.code.data = rule.code
        form.section.data = rule.section
        form.title.data = rule.title
        form.description.data = rule.description
        form.severity.data = rule.severity
        form.points.data = rule.points
        form.fine_type.data = rule.fine_type
        form.fine_amount.data = rule.fine_amount
        form.confirmation.data = rule.confirmation
        form.applies_when.data = rule.applies_when
        form.is_confidential.data = rule.is_confidential
        form.who_can_log.data = ", ".join(rule.who_can_log or [])
        form.escalation_text.data = _escalation_to_text(rule.escalation)
        form.is_active.data = rule.is_active
    if request.form.get("save_rule") and form.validate_on_submit():
        if (form.code.data or "").strip() != rule.code:
            flash("Blocked: code never changes (create a new rule instead).", "danger")
            return render_template("violations/rule_form.html", form=form, mode="edit", rule=rule)
        try:
            loggers = _parse_who_can_log(form.who_can_log.data)
            ladder = _parse_escalation(form.escalation_text.data)
        except ValueError as e:
            flash(str(e), "danger")
            return render_template("violations/rule_form.html", form=form, mode="edit", rule=rule)
        before = _rule_snapshot(rule)
        rule.section = form.section.data
        rule.section_title = SECTION_TITLES.get(form.section.data, rule.section_title)
        rule.title = form.title.data.strip()
        rule.description = (form.description.data or "").strip() or None
        rule.severity = (form.severity.data or "").strip() or None
        rule.points = form.points.data
        rule.fine_type = form.fine_type.data
        rule.fine_amount = form.fine_amount.data
        rule.fine_meta = {"type": form.fine_type.data, "amount_php": form.fine_amount.data}
        rule.escalation = ladder
        rule.who_can_log = loggers
        rule.is_confidential = bool(form.is_confidential.data)
        rule.confirmation = form.confirmation.data
        rule.applies_when = form.applies_when.data
        rule.is_active = bool(form.is_active.data)
        rule.version = (rule.version or 1) + 1
        db.session.add(RuleVersion(rule_id=rule.id, snapshot=before,
                                   changed_by=current_user.id,
                                   reason=form.change_reason.data.strip()))
        _audit("rule.edit", "violation_rule", rule.id,
               old=json.dumps(before), new=json.dumps(_rule_snapshot(rule)),
               reason=form.change_reason.data.strip())
        db.session.commit()
        flash("Rule %s saved (v%d)." % (rule.code, rule.version), "success")
        return redirect(url_for("violations.rules"))
    return render_template("violations/rule_form.html", form=form, mode="edit", rule=rule)


@violations_bp.route("/rules/<int:rule_id>/history")
@login_required
@permission_required("violations.view")
def rule_history(rule_id):
    """Version history of ONE rule (append-only snapshots, newest first)."""
    rule = ViolationRule.query.get_or_404(rule_id)
    if rule.is_confidential and not _may_see_confidential():
        flash("Confidential rule: advisers, Justice head and President only.", "danger")
        return redirect(url_for("violations.rules"))
    versions = RuleVersion.query.filter_by(rule_id=rule.id).order_by(RuleVersion.id.desc()).all()
    return render_template("violations/rule_history.html", rule=rule, versions=versions)


# ---------------------------------------------------------------------------
# Phase 2.3: /violations/log -- who-may-log filter + record creation
# ---------------------------------------------------------------------------

#: Role NAME -> who_can_log KEY (matches default_hrar.py role keys).
ROLE_TO_LOGGER_KEY = {
    "Adviser": "adviser", "SA": "sa", "Justice head": "justice_head",
    "Kitchen head": "kitchen_head", "IGP head": "igp_head",
    "Secretary": "secretary", "President": "president",
}
SUPERADMIN_ROLE = "Super-admin"  # bypass by NAME (same as decorators.py)


def _is_super_admin():
    """True if the current user holds Super-admin in ANY year (global bypass)."""
    if not getattr(current_user, "is_authenticated", False):
        return False
    return RoleAssignment.query.join(
        Residency, RoleAssignment.residency_id == Residency.id
    ).filter(Residency.person_id == current_user.person_id,
             RoleAssignment.is_active.is_(True),
             RoleAssignment.role.has(Role.name == SUPERADMIN_ROLE)).count() > 0


def _my_logger_keys():
    """who_can_log KEYS this user's roles map to. Super-admin -> ALL keys.

    Kitchen head -> {kitchen_head} (Sec 5 only), IGP head -> {igp_head}
    (confiscations 2.J/4.E), Justice head/SA/adviser -> their own keys.
    Rules whose who_can_log contains ANY of my keys are loggable by me.
    """
    if _is_super_admin():
        return set(k for k, _ in LOGGER_CHOICES) | {"president"}
    return {ROLE_TO_LOGGER_KEY[name] for name in _my_role_names()
            if name in ROLE_TO_LOGGER_KEY}


def _loggable_rules():
    """ACTIVE, non-computed rules this user may log (confidential only if visible).

    computed (3.B) is excluded: Phase 4 computes it from attendance, never by hand.
    """
    keys = _my_logger_keys()
    may_confidential = _may_see_confidential()
    out = []
    for r in ViolationRule.query.filter_by(is_active=True).order_by(
            ViolationRule.section, ViolationRule.code).all():
        if r.confirmation == "computed":
            continue
        if r.is_confidential and not may_confidential:
            continue
        if keys & set(r.who_can_log or []):
            out.append(r)
    return out


@violations_bp.route("/log", methods=["GET", "POST"])
@login_required
@permission_required("violations.log")  # Justice/Kitchen/IGP heads, SA, Adviser (+super-admin)
def log_violation():
    """Log ONE rule against ONE OR MORE occupants (spec 5.4 / roadmap 2.2).

    Creates ViolationRecord(status=Logged) per occupant with:
      offense_count = prior Confirmed count for same rule+semester+residency + 1
      auto_confirm_at = now + auto_confirm_hours ONLY for minors (Decision 5:
        points<=3, empty escalation, fine<50, not confidential AND the rule is
        marked auto_48h) -- else None (adviser must confirm).
      fine_amount = snapshot of the rule's fine at log time (Phase 3 Charges
        read this; fine_charge_id stays NULL until finance lands).
    Photo saved ONCE (same incident) shared by all records. Each occupant
    notified (dev: console print via send_violation_notice).
    """
    year = SchoolYear.query.filter_by(is_active=True).first()
    if year is None:
        flash("No active school year -- create one first.", "warning")
        return redirect(url_for("auth.me"))
    sem = Semester.query.filter_by(school_year_id=year.id, is_active=True).first()
    if sem is None:
        flash("No active semester -- activate one on the Years page first.", "warning")
        return redirect(url_for("roster.create_school_year"))

    loggable = _loggable_rules()
    rule_choices = [(r.id, "%s - %s (%d pts%s)" % (
        r.code, r.title, r.points,
        ", PHP %d" % r.fine_amount if r.fine_amount else "")) for r in loggable]
    occupants = Residency.query.filter_by(school_year_id=year.id, status="active").join(
        Person, Residency.person_id == Person.id).order_by(Person.name).all()
    occ_choices = [(res.id, "%s (%s)" % (res.person.name, res.person.course_year or "no course"))
                   for res in occupants]

    form = LogViolationForm()
    form.rule_id.choices = rule_choices
    form.occupants.choices = occ_choices
    if request.form.get("log_violation") and form.validate_on_submit():
        # Tamper guard: the posted rule must be in MY loggable set (404 on drift).
        rule = next((r for r in loggable if r.id == form.rule_id.data), None)
        if rule is None:
            flash("Blocked: you may not log that rule (confidential, computed, "
                  "or reserved for another committee).", "danger")
            return redirect(url_for("violations.log_violation"))
        wanted = [res for res in occupants if res.id in set(form.occupants.data)]
        if not wanted:
            flash("Pick at least one valid occupant.", "danger")
            return redirect(url_for("violations.log_violation"))
        try:
            photo_path = save_violation_photo(form.photo.data)  # Pillow <=1280px
        except ValueError as e:
            flash(str(e), "danger")
            return render_template("violations/log.html", form=form,
                                   auto_hours=get_int_setting("auto_confirm_hours", 48))
        now = _utcnow()
        hours = get_int_setting("auto_confirm_hours", 48)  # NEVER hardcode
        dispute_days = get_int_setting("dispute_days", 3)  # NEVER hardcode
        # Minor = Decision 5 AND rule marked auto_48h (adviser-marked rules never
        # auto-confirm even if they look minor -- respects catalog intent).
        is_minor = (rule.confirmation == "auto_48h" and rule.points <= 3
                    and not rule.escalation and rule.fine_amount < 50
                    and not rule.is_confidential)
        created = []
        for res in wanted:
            # offense_count: prior CONFIRMED count, same rule+semester+residency, +1.
            prior = ViolationRecord.query.filter_by(
                rule_id=rule.id, residency_id=res.id,
                semester_id=sem.id, status="Confirmed").count()
            rec = ViolationRecord(
                rule_id=rule.id, residency_id=res.id, semester_id=sem.id,
                reporter_id=None if form.is_anonymous.data else current_user.id,
                is_anonymous=bool(form.is_anonymous.data),
                date=form.date.data, time=form.time.data,
                place=(form.place.data or "").strip() or None,
                notes=(form.notes.data or "").strip() or None,
                photo_path=photo_path, offense_count=prior + 1, status="Logged",
                auto_confirm_at=(now + timedelta(hours=hours)) if is_minor else None,
                fine_amount=rule.fine_amount, notified_at=now)
            db.session.add(rec)
            db.session.flush()  # rec.id for audit
            _audit("violation.log", "violation_record", rec.id,
                   new=json.dumps({"rule": rule.code, "residency_id": res.id,
                                   "offense_count": rec.offense_count,
                                   "auto_confirm": bool(rec.auto_confirm_at)}))
            created.append((rec, res))
        db.session.commit()
        # Notify AFTER commit (email failure must not lose the records).
        for rec, res in created:
            try:
                send_violation_notice(
                    res.person.email, res.person.name, rule.code, rule.title,
                    rule.points, rec.fine_amount,
                    "%s %s" % (rec.date, rec.time or ""), dispute_days)
            except Exception:
                flash("Recorded, but the notice email to %s failed (dev console)." %
                      res.person.email, "warning")
        flash("Logged %s against %d occupant(s)%s." % (
            rule.code, len(created),
            " (minor: auto-confirm in %dh)" % hours if is_minor
            else " (adviser confirm required)"), "success")
        return redirect(url_for("violations.rules"))
    return render_template("violations/log.html", form=form,
                           auto_hours=get_int_setting("auto_confirm_hours", 48))
