# app/utils/decorators.py -- ONE central permission check for every page (spec section 7)
# CS50x map: CS50x had a single login_required in helpers.py. Here every route needs
# @login_required (logged in?) PLUS @permission_required("finance.view") (allowed?).
from datetime import datetime, timezone  # to ignore expired PermissionGrants (naive UTC both sides)
from functools import wraps  # preserves route names so Flask routing still works
from flask import abort  # 403 page on deny
from flask_login import current_user  # the logged-in User (was session["user_id"] in CS50x)
from app import db  # commit the AuditLog deny row
# Exact 1.1 model names -- DO NOT rename (later phases import these too)
from app.roster.models import AuditLog, PermissionGrant, Residency, RoleAssignment, SchoolYear
SUPERADMIN_ROLE = "Super-admin"  # the one role that bypasses every check (spec section 3)

def _active_year():
    """Return the current SchoolYear row, or None if none is active."""
    return SchoolYear.query.filter_by(is_active=True).first()

def _active_assignments(user):
    """All ACTIVE RoleAssignments for this user's person in the ACTIVE year (roles stack)."""
    if user is None or getattr(user, "person_id", None) is None:
        return []
    year = _active_year()
    if year is None:
        return []
    res_ids = [r.id for r in Residency.query.filter_by(person_id=user.person_id, school_year_id=year.id).all()]
    if not res_ids:
        return []
    return RoleAssignment.query.filter(RoleAssignment.residency_id.in_(res_ids), RoleAssignment.school_year_id == year.id, RoleAssignment.is_active.is_(True)).all()

def has_permission(user, permission):
    """True if user may do permission (e.g. role.assign). Super-admin always True."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    assignments = _active_assignments(user)
    for a in assignments:
        if a.role is not None and a.role.name == SUPERADMIN_ROLE:
            return True
    granted_by_role = any(a.role is not None and a.role.permissions and permission in a.role.permissions for a in assignments)
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC matches DateTime columns
    res_ids = list(set(a.residency_id for a in assignments))
    allow_override = False
    deny_override = False
    if res_ids:
        grants = PermissionGrant.query.filter(PermissionGrant.residency_id.in_(res_ids), PermissionGrant.permission == permission).all()
        for g in grants:
            if g.expires_at is not None and g.expires_at <= now:
                continue
            if g.allow:
                allow_override = True
            else:
                deny_override = True
    if deny_override:
        return False
    return granted_by_role or allow_override

def permission_required(permission):
    """Route decorator: 403 + audit unless current_user has permission. Use AFTER @login_required."""
    def decorator(route):
        @wraps(route)
        def wrapper(*args, **kwargs):
            if not getattr(current_user, "is_authenticated", False):
                abort(401)
            if has_permission(current_user, permission):
                return route(*args, **kwargs)
            db.session.add(AuditLog(actor_id=getattr(current_user, "id", None), action="auth.forbidden", table_name=None, record_id=None, reason="denied " + permission + " for user " + str(getattr(current_user, 'id', '?'))))
            db.session.commit()
            abort(403)
        return wrapper
    return decorator
