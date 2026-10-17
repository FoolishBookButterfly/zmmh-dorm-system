# seed_roles.py -- Phase 1.3: seed all 17 roles + ensure active SchoolYear (idempotent).
# CS50x map: like manually INSERTing lookup rows once; re-run is safe (prints Created/Exists).
# Bundles live in app/roster/default_roles.py -- edit THERE, both shell and /seed-routes stay in sync.
# Run once in flask shell:  exec(open("seed_roles.py").read())
from app import db  # commit rows (ORM handle from factory)
from app.roster.models import Role, SchoolYear  # exact 1.1 model names -- DO NOT rename
from app.roster.default_roles import ROLES  # single source of truth

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
        print("Exists:", name)

db.session.commit()
print("DONE. Roles in ROLES:", len(ROLES))
