# seed_roles.py -- Phase 1.3 Step 1: seed all 17 roles + ensure active SchoolYear (idempotent)
# CS50x map: like manually INSERTing lookup rows once; re-run is safe (prints Created/Exists).
# Run once in flask shell:  exec(open("seed_roles.py").read())
from app import db  # commit rows (ORM handle from factory)
from app.roster.models import Role, SchoolYear  # exact 1.1 model names -- DO NOT rename

# Name -> permission bundle (spec section 3).
# IMPORTANT: "Super-admin" must match decorators.py bypass exactly (a.role.name == "Super-admin").
ROLES = {
    "Super-admin": [],  # bypass by NAME in permission_required -- no perms needed
    "Adviser": [
        "roster.view", "roster.export", "roster.view_private", "roster.edit", "role.assign",
        "finance.view", "finance.edit",
        "violations.view", "violations.log", "violations.confirm",
        "events.view", "events.edit", "cleaning.view", "cleaning.edit",
        "evaluation.view", "evaluation.enter", "evaluation.lock", "evaluation.release",
        "settings.view", "audit.view", "tickets.view", "announcements.post", "clearance.edit",
    ],
    "President": ["roster.view", "roster.export", "roster.view_private", "announcements.post", "tickets.view", "disputes.review"],
    "Secretary": ["roster.view", "roster.export", "roster.view_private", "events.view", "events.edit", "evaluation.enter"],
    "Assistant Secretary": ["events.view", "events.attendance"],
    "Treasurer": ["finance.view", "finance.edit", "finance.receipts", "finance.expenses"],
    "Assistant Treasurer": ["finance.view", "finance.edit", "finance.receipts", "finance.expenses"],
    "Auditor": ["finance.view", "audit.view"],  # read-only: no .edit perms anywhere = safe by construction
    "VP Internal": ["announcements.post"],
    "VP External": ["announcements.post"],
    "Justice head": ["violations.log", "tickets.view"],  # logs ALL rules (Sec 5 scope enforced in Phase 2 routes)
    "Kitchen head": ["violations.log", "tickets.view"],
    "IGP head": ["violations.log", "tickets.view"],
    "Repairs head": ["tickets.view"],
    "SA": ["cleaning.view", "cleaning.edit", "tickets.view", "violations.log", "clearance.room_inspect"],
    "Evaluator (temp)": ["evaluation.view"],  # ends by is_active=False at results release (spec 5.3)
    "Occupant": [],  # own-data view is implicit from login + residency, not a permission
}

# 1) Ensure the active school year exists (RoleAssignments attach to residencies in THIS year)
year = SchoolYear.query.filter_by(label="2026-2027").first()
if year is None:
    year = SchoolYear(label="2026-2027", is_active=True)
    db.session.add(year)
    print("Created: SchoolYear 2026-2027")
elif not year.is_active:
    year.is_active = True  # ensure=True means: make sure it IS active
    print("Exists: SchoolYear 2026-2027 (activated)")
else:
    print("Exists: SchoolYear 2026-2027")

# 2) Create each missing role; existing rows are skipped (never duplicates)
for name, perms in ROLES.items():
    role = Role.query.filter_by(name=name).first()
    if role is None:
        db.session.add(Role(name=name, permissions=perms))  # permissions = JSON list column
        print("Created:", name)
    else:
        print("Exists:", name)  # v1: skip; edit bundles manually if you change ROLES later

db.session.commit()
print("DONE. Roles in ROLES:", len(ROLES))
