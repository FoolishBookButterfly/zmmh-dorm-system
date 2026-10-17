# app/roster/routes.py -- Phase 1.3 Step 4: /admin/roles list + edit (assign roles, add/revoke grants)
# CS50x map: CS50x did SELECT/UPDATE by hand; here ORM + AuditLog on every change.
# Access rule: @login_required AND @permission_required("role.assign") = advisers + super-admin ONLY (Plate 2B).
import json  # readable old/new snapshots inside AuditLog
from datetime import datetime, time as dtime  # grant expiry -> end-of-day datetime (valid THROUGH that date)
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required

from app import db  # commit rows
from app.roster.models import Residency, SchoolYear, Role, RoleAssignment, PermissionGrant, AuditLog
from app.roster.forms import RoleForm, GrantForm, RevokeGrantForm, KNOWN_PERMISSIONS
from app.utils.decorators import permission_required  # Step 1 central gate

roster_bp = Blueprint("roster", __name__)  # registered in factory right after auth_bp


def _audit(action, table_name, record_id, old=None, new=None, reason=None):
    """Append-only audit row (never deleted; scores/money changes REQUIRE reason later)."""
    db.session.add(AuditLog(actor_id=current_user.id, action=action, table_name=table_name,
                            record_id=record_id, old_value=old, new_value=new, reason=reason))


def _active_year():
    """Current SchoolYear or None (all role work is scoped to the ACTIVE year, spec section 3)."""
    return SchoolYear.query.filter_by(is_active=True).first()


@roster_bp.route("/admin/roles")
@login_required
@permission_required("role.assign")
def roles():
    """List every occupant of the active year with active-role pills + Edit links."""
    year = _active_year()
    if year is None:
        flash("No active school year -- run seed_roles.py in flask shell first.", "warning")
        return redirect(url_for("auth.me"))
    q = (request.args.get("q") or "").strip()  # optional name filter (?q=juan)
    rows = []
    for res in Residency.query.filter_by(school_year_id=year.id).order_by(Residency.id).all():
        person = res.person
        if q and q.lower() not in (person.name or "").lower():
            continue
        active = sorted(ra.role.name for ra in res.role_assignments
                        if ra.is_active and ra.school_year_id == year.id and ra.role is not None)
        rows.append({"res": res, "person": person, "roles": active})
    return render_template("roster/roles.html", rows=rows, year=year, q=q)


@roster_bp.route("/admin/roles/<int:residency_id>", methods=["GET", "POST"])
@login_required
@permission_required("role.assign")
def role_edit(residency_id):
    """Tick/untick roles (soft-deactivate) + add/revoke grants for ONE occupant."""
    year = _active_year()
    if year is None:
        flash("No active school year.", "warning")
        return redirect(url_for("auth.me"))
    res = Residency.query.get_or_404(residency_id)
    if res.school_year_id != year.id:
        flash("That record belongs to another school year.", "warning")
        return redirect(url_for("roster.roles"))

    # Active role names RIGHT NOW (prefills checkboxes + becomes the audit "old" value)
    active_now = sorted(ra.role.name for ra in res.role_assignments
                        if ra.is_active and ra.school_year_id == year.id and ra.role is not None)

    role_form = RoleForm()
    role_form.roles.choices = [(r.name, r.name) for r in Role.query.order_by(Role.name).all()]  # must set BEFORE validate
    grant_form = GrantForm()
    revoke_form = RevokeGrantForm()

    # ---- A) SAVE ROLES: create/reactivate checked, soft-deactivate unchecked ----
    if request.form.get("save_roles") and role_form.validate_on_submit():
        chosen = sorted(set(role_form.roles.data or []))
        # Lockout guard: you may NEVER remove your own Super-admin (nobody left to assign roles)
        editing_self = current_user.person_id == res.person_id
        if editing_self and "Super-admin" in active_now and "Super-admin" not in chosen:
            flash("Blocked: you cannot remove your own Super-admin role (lockout risk).", "danger")
            return redirect(url_for("roster.role_edit", residency_id=res.id))
        by_name = {ra.role.name: ra for ra in res.role_assignments
                   if ra.school_year_id == year.id and ra.role is not None}
        role_objs = {r.name: r for r in Role.query.all()}
        for name in chosen:
            if name in by_name:
                by_name[name].is_active = True  # reactivate existing row (never duplicates)
                by_name[name].assigned_by = current_user.id  # Plate 2B "Assigned by" pill
            else:
                db.session.add(RoleAssignment(residency_id=res.id, role_id=role_objs[name].id,
                                              school_year_id=year.id, is_active=True,
                                              assigned_by=current_user.id))
        for name in active_now:
            if name not in chosen and name in by_name:
                by_name[name].is_active = False  # SOFT delete: history kept (like temp Evaluator ending)
        _audit("role.assign", "role_assignment", res.id, old=json.dumps(active_now),
               new=json.dumps(chosen), reason="roles edit for residency %d" % res.id)
        db.session.commit()
        flash("Roles saved: " + (", ".join(chosen) if chosen else "none"), "success")
        return redirect(url_for("roster.role_edit", residency_id=res.id))

    # ---- B) ADD GRANT: one extra allow/deny + optional expiry ----
    if request.form.get("add_grant") and grant_form.validate_on_submit():
        perm = grant_form.permission.data.strip()
        allow = grant_form.allow.data == "1"
        expires = None
        if grant_form.expires.data:
            expires = datetime.combine(grant_form.expires.data, dtime.max)  # valid THROUGH end of that day
        db.session.add(PermissionGrant(residency_id=res.id, permission=perm, allow=allow,
                                       expires_at=expires, granted_by=current_user.id))
        _audit("grant.add", "permission_grant", res.id,
               new=json.dumps({"permission": perm, "allow": allow,
                               "expires": expires.isoformat() if expires else None}),
               reason="grant for residency %d" % res.id)
        db.session.commit()
        flash("Grant added: " + perm + (" (allow)" if allow else " (deny)"), "success")
        return redirect(url_for("roster.role_edit", residency_id=res.id))

    # ---- C) REVOKE GRANT: hard-delete (grants are overrides, not history) ----
    if request.form.get("revoke") and revoke_form.validate_on_submit():
        try:
            gid = int(revoke_form.grant_id.data)
        except (TypeError, ValueError):
            gid = 0
        g = PermissionGrant.query.filter_by(id=gid, residency_id=res.id).first()  # scoped to THIS page
        if g is None:
            flash("Grant not found.", "danger")
        else:
            perm_name = g.permission
            _audit("grant.revoke", "permission_grant", res.id,
                   old=json.dumps({"permission": g.permission, "allow": g.allow}),
                   reason="revoked grant %d" % g.id)
            db.session.delete(g)
            db.session.commit()
            flash("Grant revoked: " + perm_name, "success")
        return redirect(url_for("roster.role_edit", residency_id=res.id))

    # ---- D) GET: prefill checkboxes + list current grants ----
    role_form.roles.data = active_now  # checked state for MultiCheckboxField
    grants = PermissionGrant.query.filter_by(residency_id=res.id).order_by(PermissionGrant.id).all()
    return render_template("roster/role_edit.html", res=res, person=res.person, user=res.person.user,
                           role_form=role_form, grant_form=grant_form, revoke_form=revoke_form,
                           grants=grants, active_roles=active_now,
                           known_permissions=KNOWN_PERMISSIONS, year=year)
