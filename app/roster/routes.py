# app/roster/routes.py -- Phase 1.3 Step 4: /admin/roles list + edit (assign roles, add/revoke grants)
# CS50x map: CS50x did SELECT/UPDATE by hand; here ORM + AuditLog on every change.
# Access rule: @login_required AND @permission_required("role.assign") = advisers + super-admin ONLY (Plate 2B).
import json  # readable old/new snapshots inside AuditLog
from datetime import datetime, time as dtime  # grant expiry -> end-of-day datetime (valid THROUGH that date)
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required

from app import db  # commit rows
from app.roster.models import Residency, SchoolYear, Role, RoleAssignment, PermissionGrant, AuditLog
from app.roster.models import Person, User, Semester, Room, RoomAssignment  # Step 3b: roster + rooms + import
from app.roster.forms import RoleForm, GrantForm, RevokeGrantForm, KNOWN_PERMISSIONS
from app.roster.forms import RoomForm, AssignmentForm, ImportForm, CommitImportForm, SettingsSaveForm  # Step 3b + 1.5: forms
from app.roster.models import Setting  # 1.5: settings screen reads/writes Setting rows
from app.roster.default_settings import SETTINGS as SETTINGS_META  # 1.5: labels/types/bounds come from the catalog
from app.utils.decorators import permission_required, has_permission  # Step 1 central gate

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

# ---------- Phase 1.4 Step 3b: rooms, assignments, import/export (below) ----------

import csv  # roster CSV parsing (stdlib: no new dependency)
import io as _io  # decode the uploaded file bytes to text
import os  # staging folder paths (module level so helpers share it)
from datetime import date as _date  # joined_at/left_at stamps; joined today for manual adds
from flask import Response, send_file  # CSV download responses


def _occupants(year_id, include_inactive=False):
    """Active-year residencies, excluding staff anchors (advisers are not counted as occupants)."""
    q = Residency.query.filter_by(school_year_id=year_id)
    if not include_inactive:
        q = q.filter(Residency.status != "staff")
    return q.order_by(Residency.id).all()


def _room_fill(room, semester_id, year_id):
    """Assignments in this room for one semester with active occupants (None slots = vacancies)."""
    rows = RoomAssignment.query.filter_by(room_id=room.id, semester_id=semester_id).all()
    out = []
    for a in rows:
        res = Residency.query.get(a.residency_id)
        if res is None or res.school_year_id != year_id or res.status == "staff":
            continue
        out.append({"assignment": a, "person": res.person, "residency": res})
    return out


def _current_big_brod(room_id, semester_id, year_id):
    """The single Big Brod for a room+semester, or None (enforced unique below)."""
    for a in RoomAssignment.query.filter_by(room_id=room_id, semester_id=semester_id, is_big_brod=True).all():
        res = Residency.query.get(a.residency_id)
        if res is not None and res.school_year_id == year_id and res.status != "staff":
            return a
    return None

@roster_bp.route("/roster/rooms")
@login_required
@permission_required("roster.view")
def rooms():
    """20 rooms with occupancy bars for the active semester; vacancies shown, not errored."""
    year = _active_year()
    if year is None:
        flash("No active school year.", "warning")
        return redirect(url_for("auth.me"))
    sem = Semester.query.filter_by(school_year_id=year.id, is_active=True).first()
    if sem is None:
        flash("No active semester.", "warning")
        return redirect(url_for("auth.me"))
    cards = []
    for room in Room.query.order_by(Room.name).all():
        fill = _room_fill(room, sem.id, year.id)
        big = _current_big_brod(room.id, sem.id, year.id)
        cards.append({"room": room, "filled": len(fill),
                      "vacancy": max(0, room.capacity - len(fill)),
                      "big_brod": big.residency.person.name if big and big.residency else None})
    return render_template("roster/rooms.html", cards=cards, year=year, sem=sem)

@roster_bp.route("/roster/rooms/<int:room_id>", methods=["GET", "POST"])
@login_required
@permission_required("roster.view")
def room_detail(room_id):
    """One room: occupants, edit capacity (roster.edit), assign with Big Brod uniqueness guard."""
    from flask import abort as _abort
    from app.utils.decorators import has_permission
    year = _active_year()
    if year is None:
        flash("No active school year.", "warning")
        return redirect(url_for("auth.me"))
    room = Room.query.get_or_404(room_id)
    semesters = Semester.query.filter_by(school_year_id=year.id).order_by(Semester.id).all()
    sem = Semester.query.filter_by(school_year_id=year.id, is_active=True).first() or (semesters[0] if semesters else None)
    if sem is None:
        flash("No semesters in this year.", "warning")
        return redirect(url_for("roster.rooms"))

    room_form = RoomForm(obj=room)
    a_form = AssignmentForm()
    a_form.residency_id.choices = [(r.id, r.person.name) for r in _occupants(year.id)]
    a_form.semester_id.choices = [(s.id, s.name) for s in semesters]
    if request.method == "GET":
        a_form.semester_id.data = sem.id

    if request.form.get("save_room") and room_form.validate_on_submit():
        if not has_permission(current_user, "roster.edit"):
            _abort(403)
        filled = len(_room_fill(room, sem.id, year.id))
        if room_form.capacity.data < filled:
            flash("Blocked: capacity %d is below current occupancy %d." % (room_form.capacity.data, filled), "danger")
        else:
            _audit("room.edit", "room", room.id, old=json.dumps({"name": room.name, "capacity": room.capacity}),
                   new=json.dumps({"name": room_form.name.data.strip(), "capacity": room_form.capacity.data}),
                   reason="room edit %s" % room.name)
            room.name = room_form.name.data.strip()
            room.capacity = room_form.capacity.data
            db.session.commit()
            flash("Room saved.", "success")
        return redirect(url_for("roster.room_detail", room_id=room.id))

    if request.form.get("save_assignment") and a_form.validate_on_submit():
        if not has_permission(current_user, "roster.edit"):
            _abort(403)
        res = Residency.query.get(a_form.residency_id.data)
        target_sem = Semester.query.get(a_form.semester_id.data)
        if res is None or target_sem is None or res.school_year_id != year.id:
            flash("Invalid occupant or semester.", "danger")
            return redirect(url_for("roster.room_detail", room_id=room.id))
        existing = RoomAssignment.query.filter_by(residency_id=res.id, semester_id=target_sem.id).first()
        reason = (a_form.move_reason.data or "").strip()
        if existing is not None and existing.room_id != room.id and not reason:
            flash("Reason required: this moves %s from another room." % res.person.name, "danger")
            return redirect(url_for("roster.room_detail", room_id=room.id))
        if a_form.is_big_brod.data:
            other = _current_big_brod(room.id, target_sem.id, year.id)
            if other is not None and other.residency_id != res.id:
                flash("Blocked: %s is already Big Brod here. Untick them first (with reason)." % other.residency.person.name, "danger")
                return redirect(url_for("roster.room_detail", room_id=room.id))
        if len(_room_fill(room, target_sem.id, year.id)) >= room.capacity and (existing is None or existing.room_id != room.id):
            flash("Blocked: %s is full (%d/%d)." % (room.name, room.capacity, room.capacity), "danger")
            return redirect(url_for("roster.room_detail", room_id=room.id))
        if existing is None:
            db.session.add(RoomAssignment(residency_id=res.id, room_id=room.id, semester_id=target_sem.id,
                                          is_big_brod=bool(a_form.is_big_brod.data), move_reason=reason or None))
            if res.status == "former":
                res.status = "active"
                res.left_at = None
            if res.joined_at is None:
                res.joined_at = _date.today()
            _audit("room.assign", "room_assignment", res.id,
                   new=json.dumps({"room": room.name, "semester": target_sem.name, "big_brod": bool(a_form.is_big_brod.data)}),
                   reason=reason or "assigned %s" % res.person.name)
        else:
            _audit("room.assign", "room_assignment", res.id,
                   old=json.dumps({"room": Room.query.get(existing.room_id).name, "big_brod": existing.is_big_brod}),
                   new=json.dumps({"room": room.name, "big_brod": bool(a_form.is_big_brod.data)}),
                   reason=reason or "updated %s" % res.person.name)
            existing.room_id = room.id
            existing.is_big_brod = bool(a_form.is_big_brod.data)
            existing.move_reason = reason or existing.move_reason
        db.session.commit()
        flash("Assigned %s to %s." % (res.person.name, room.name), "success")
        return redirect(url_for("roster.room_detail", room_id=room.id))

    fill = _room_fill(room, sem.id, year.id)
    return render_template("roster/room_detail.html", room=room, year=year, sem=sem, semesters=semesters,
                           fill=fill, room_form=room_form, a_form=a_form)


def _parse_roster_csv(file_storage):
    """Parse the uploaded CSV into (rows, errors). Never touches the DB: dry-run safe."""
    try:
        raw = file_storage.read()
    finally:
        try:
            file_storage.seek(0)
        except Exception:
            pass
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    want = ["name", "email", "birthday", "address", "contact_number", "emergency_contact", "course_year", "room"]
    missing = [c for c in want if c not in (reader.fieldnames or [])]
    if missing:
        return [], ["Missing columns: " + ", ".join(missing)]
    rows, errors = [], []
    seen_file = set()
    for i, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        email = (row.get("email") or "").strip().lower()
        room = (row.get("room") or "").strip()
        bday = (row.get("birthday") or "").strip()
        if not name:
            errors.append("Row %d: blank name, skipped." % i)
            continue
        if not email or "@" not in email:
            errors.append("Row %d (%s): bad email, skipped." % (i, name))
            continue
        if email in seen_file:
            errors.append("Row %d (%s): duplicate email in file, skipped." % (i, email))
            continue
        seen_file.add(email)
        parsed_bday = None
        if bday:
            try:
                parsed_bday = _date.fromisoformat(bday)
            except ValueError:
                errors.append("Row %d (%s): birthday must be YYYY-MM-DD, kept blank." % (i, name))
        rows.append({"row": i, "name": name, "email": email, "birthday": parsed_bday,
                     "address": (row.get("address") or "").strip() or None,
                     "contact_number": (row.get("contact_number") or "").strip() or None,
                     "emergency_contact": (row.get("emergency_contact") or "").strip() or None,
                     "course_year": (row.get("course_year") or "").strip() or None,
                     "room": room or None})
    return rows, errors


@roster_bp.route("/roster/import", methods=["GET", "POST"])
@login_required
@permission_required("roster.edit")
def roster_import():
    """CSV import in two posted steps: PREVIEW parses and stages the file server-side
    (private instance folder, random token, 15-minute expiry), then COMMIT reads the
    staged file and writes. Re-classifies at commit so nothing stale is trusted."""
    import secrets as _secrets
    import_form = ImportForm()
    commit_form = CommitImportForm()
    year = _active_year()
    if year is None:
        flash("No active school year.", "warning")
        return redirect(url_for("auth.me"))
    sem = Semester.query.filter_by(school_year_id=year.id, is_active=True).first()
    preview, errors, summary, stage_token = None, [], None, None

    def _classify(rows):
        by_room, new_rows, skip_rows = {}, [], []
        for r in rows:
            if r["room"]:
                by_room.setdefault(r["room"], []).append(r["name"])
            person = Person.query.filter_by(email=r["email"]).first()
            if person is None:
                new_rows.append(r)
            else:
                res = Residency.query.filter_by(person_id=person.id, school_year_id=year.id).first()
                skip_rows.append({"name": r["name"], "email": r["email"],
                                  "state": "already in %s" % year.label if res else "exists, no %s record" % year.label})
        unknown = sorted(rm for rm in by_room if Room.query.filter_by(name=rm).first() is None)
        return by_room, new_rows, skip_rows, unknown

    def _stage_dir():
        d = os.path.join(os.getcwd(), "instance", "import_staging")
        os.makedirs(d, exist_ok=True)
        return d

    def _sweep_staging(max_age_min=15):
        try:
            import time as _time
            for fn in os.listdir(_stage_dir()):
                fp = os.path.join(_stage_dir(), fn)
                try:
                    if _time.time() - os.path.getmtime(fp) > max_age_min * 60:
                        os.remove(fp)
                except OSError:
                    pass
        except OSError:
            pass

    if request.form.get("preview") and import_form.validate_on_submit():
        f = import_form.file.data
        rows, errors = _parse_roster_csv(f)
        by_room, new_rows, skip_rows, unknown = _classify(rows)
        if unknown:
            errors.append("Unknown rooms (fix before commit): " + ", ".join(unknown))
        _sweep_staging()
        f.seek(0)
        stage_token = _secrets.token_hex(16)
        staged_path = os.path.join(_stage_dir(), stage_token + ".csv")
        with open(staged_path, "wb") as fh:
            fh.write(f.read())
        summary = {"new": len(new_rows), "skipped": len(skip_rows), "errors": len(errors), "by_room": by_room}
        preview = {"new": new_rows, "skipped": skip_rows}

    if request.form.get("commit") and commit_form.validate_on_submit():
        stage_token = (commit_form.stage_token.data or "").strip()
        staged_path = os.path.join(_stage_dir(), stage_token + ".csv") if stage_token else None
        if not stage_token or not staged_path or not os.path.isfile(staged_path):
            flash("Staged file expired (15 min) or missing. Re-run preview.", "danger")
            return redirect(url_for("roster.roster_import"))
        with open(staged_path, "rb") as fh:
            from werkzeug.datastructures import FileStorage as _FS
            staged_file = _FS(stream=fh, filename="staged.csv")
            rows, errors = _parse_roster_csv(staged_file)
        by_room, new_rows, skip_rows, unknown = _classify(rows)
        if unknown or not new_rows:
            flash("Commit blocked: unknown rooms or nothing new. Re-run preview after fixing the file.", "danger")
            return redirect(url_for("roster.roster_import"))
        created, placed = 0, 0
        for r in new_rows:
            person = Person(name=r["name"], email=r["email"], birthday=r["birthday"], address=r["address"],
                            contact_number=r["contact_number"], emergency_contact=r["emergency_contact"],
                            course_year=r["course_year"])
            db.session.add(person)
            db.session.flush()
            res = Residency(person_id=person.id, school_year_id=year.id, status="active", joined_at=_date.today())
            db.session.add(res)
            db.session.flush()
            created += 1
            if r["room"] and sem is not None:
                room = Room.query.filter_by(name=r["room"]).first()
                if room is not None and len(_room_fill(room, sem.id, year.id)) < room.capacity:
                    db.session.add(RoomAssignment(residency_id=res.id, room_id=room.id, semester_id=sem.id,
                                                  is_big_brod=False, move_reason="roster import"))
                    placed += 1
            _audit("roster.import", "person", person.id, new=json.dumps({"name": r["name"], "room": r["room"]}),
                   reason="CSV import into %s" % year.label)
        db.session.commit()
        try:
            os.remove(staged_path)
        except OSError:
            pass
        flash("Imported %d occupants (%d placed in rooms)." % (created, placed), "success")
        return redirect(url_for("roster.roster_import"))

    return render_template("roster/import.html", year=year, sem=sem, import_form=import_form,
                           commit_form=commit_form, preview=preview, errors=errors, summary=summary,
                           stage_token=stage_token)


@roster_bp.route("/roster/export")
@login_required
@permission_required("roster.export")
def roster_export():
    """CSV download of the active-year roster. Every export is audit-logged (privacy rule)."""
    year = _active_year()
    if year is None:
        flash("No active school year.", "warning")
        return redirect(url_for("auth.me"))
    sem = Semester.query.filter_by(school_year_id=year.id, is_active=True).first()
    buf = _io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["name", "email", "birthday", "address", "contact_number", "emergency_contact",
                     "course_year", "room", "status", "joined_at"])
    for res in _occupants(year.id):
        p = res.person
        room_name = ""
        if sem is not None:
            for a in RoomAssignment.query.filter_by(residency_id=res.id, semester_id=sem.id).all():
                room_name = a.room.name if a.room else ""
        writer.writerow([p.name, p.email, res.person.birthday.isoformat() if res.person.birthday else "",
                         p.address or "", p.contact_number or "", p.emergency_contact or "",
                         p.course_year or "", room_name, res.status,
                         res.joined_at.isoformat() if res.joined_at else ""])
    _audit("roster.export", "person", None, new=json.dumps({"year": year.label}),
           reason="CSV export by %s" % current_user.username)
    db.session.commit()
    buf.seek(0)
    return send_file(_io.BytesIO(buf.getvalue().encode("utf-8-sig")), mimetype="text/csv",
                     as_attachment=True, download_name="roster-%s.csv" % year.label)


@roster_bp.route("/roster/remove/<int:residency_id>", methods=["POST"])
@login_required
@permission_required("roster.edit")
def roster_remove(residency_id):
    """Soft-remove a mid-year leaver: status=former + left_at. History, payments, roles kept (spec 5.2)."""
    year = _active_year()
    if year is None:
        flash("No active school year.", "warning")
        return redirect(url_for("auth.me"))
    res = Residency.query.get_or_404(residency_id)
    if res.school_year_id != year.id or res.status == "staff":
        flash("Cannot remove this record.", "danger")
        return redirect(url_for("roster.rooms"))
    _audit("roster.remove", "residency", res.id, old=json.dumps({"status": res.status}),
           new=json.dumps({"status": "former"}), reason="soft-remove %s" % res.person.name)
    res.status = "former"
    res.left_at = _date.today()
    db.session.commit()
    flash("Removed %s (history kept)." % res.person.name, "success")
    return redirect(url_for("roster.rooms"))


@roster_bp.route("/roster/restore/<int:residency_id>", methods=["POST"])
@login_required
@permission_required("roster.edit")
def roster_restore(residency_id):
    """Undo a soft-remove: status back to active, left_at cleared (re-join counted from today)."""
    year = _active_year()
    if year is None:
        flash("No active school year.", "warning")
        return redirect(url_for("auth.me"))
    res = Residency.query.get_or_404(residency_id)
    if res.school_year_id != year.id or res.status != "former":
        flash("Nothing to restore.", "warning")
        return redirect(url_for("roster.rooms"))
    _audit("roster.restore", "residency", res.id, old=json.dumps({"status": "former"}),
           new=json.dumps({"status": "active"}), reason="restore %s" % res.person.name)
    res.status = "active"
    res.left_at = None
    if res.joined_at is None:
        res.joined_at = _date.today()
    db.session.commit()
    flash("Restored %s." % res.person.name, "success")
    return redirect(url_for("roster.rooms"))

# ---------- Phase 1.5 Step 2: /admin/settings (view+edit = settings.view: Adviser + super-admin) ----------

# Validation guard-rails (percentages for w_* keys; explicit ranges for the rest).
# These bound INPUTS -- the domain values themselves live in the Setting TABLE (spec section 7).
_INT_BOUNDS = {"quorum_min": (1, 13), "cutoff_failed": (1, 100), "cap_retained": (1, 130),
               "cap_waitlisted": (1, 130), "danger_margin": (0, 50), "dispute_days": (1, 60),
               "maintenance_fee": (0, 1000000)}


def _bounds(key):
    if key in _INT_BOUNDS:
        return _INT_BOUNDS[key]
    if key.startswith("w_"):  # every weight share is a percentage
        return (0, 100)
    return (0, 1000000)


# Ordered groups from the catalog (insertion order of SETTINGS): Evaluation weights, Status rules, ...
_SETTINGS_GROUPS = {}
for _k, _m in SETTINGS_META.items():
    _SETTINGS_GROUPS.setdefault(_m["group"], []).append(_k)


@roster_bp.route("/admin/settings", methods=["GET", "POST"])
@login_required
@permission_required("settings.view")
def settings_page():
    """Editable settings screen (spec section 7: values live HERE, never hardcoded).
    Gate = settings.view for BOTH view and edit (hall decision: 70/37/10 accessible to advisers too).
    Every change writes one AuditLog row per key (old -> new, auto reason). All-or-nothing per group."""
    save_form = SettingsSaveForm()
    current = {row.key: row.value for row in Setting.query.all()}
    missing = [k for k in SETTINGS_META if k not in current]

    if request.form.get("save_group") and save_form.validate_on_submit():
        group = request.form["save_group"]
        if group not in _SETTINGS_GROUPS:
            flash("Unknown settings group.", "danger")
            return redirect(url_for("roster.settings_page"))
        updates, errors = [], []
        for key in _SETTINGS_GROUPS[group]:
            meta = SETTINGS_META[key]
            raw = (request.form.get(key) or "").strip()
            if meta["type"] == "int":
                try:
                    num = int(raw)
                except ValueError:
                    errors.append("%s: whole number required." % meta["label"])
                    continue
                lo, hi = _bounds(key)
                if not (lo <= num <= hi):
                    errors.append("%s: must be between %d and %d." % (meta["label"], lo, hi))
                    continue
                updates.append((key, str(num), meta["label"]))
            else:  # choice
                if raw not in meta["choices"]:
                    errors.append("%s: invalid option." % meta["label"])
                    continue
                updates.append((key, raw, meta["label"]))
        if errors:  # all-or-nothing: nothing saved when any field is bad
            flash("Not saved -- " + " ".join(errors), "danger")
            return redirect(url_for("roster.settings_page"))
        changed = 0
        for key, new_val, label in updates:
            row = Setting.query.filter_by(key=key).first()
            if row is None:  # upsert: partial-seeded DBs fill in on first save
                db.session.add(Setting(key=key, value=new_val, description=label))
                _audit("setting.create", "setting", None, new=new_val, reason="settings upsert: %s" % key)
                changed += 1
            elif row.value != new_val:
                _audit("setting.edit", "setting", row.id, old=row.value, new=new_val,
                       reason="settings edit: %s" % key)
                row.value = new_val
                changed += 1
        db.session.commit()
        flash("Saved %d change(s) in %s." % (changed, group), "success")
        return redirect(url_for("roster.settings_page"))

    return render_template("roster/settings.html", groups=_SETTINGS_GROUPS, meta=SETTINGS_META,
                           current=current, missing=missing, save_form=save_form)



