# seed_roles.py -- Phase 1.3: seed all 17 roles + ensure active SchoolYear (idempotent).
# CS50x map: like manually INSERTing lookup rows once; re-run is safe (prints Created/Exists).
# Bundles live in app/roster/default_roles.py -- edit THERE, both shell and /seed-routes stay in sync.
# Run once in flask shell:  exec(open("seed_roles.py").read())
from app import db  # commit rows (ORM handle from factory)
from app.roster.models import Role, SchoolYear, Semester  # exact 1.1 model names -- DO NOT rename
from app.roster.default_roles import ROLES  # single source of truth

# 1) Ensure the active school year exists (RoleAssignments attach to residencies in THIS year)
year = SchoolYear.query.filter_by(label="2026-2027").first()
if year is None:
    year = SchoolYear(label="2026-2027", is_active=True)
    db.session.add(year)
    print("Created: SchoolYear 2026-2027")
elif not year.is_active:
    year.is_active = True  # ensure=True
    print("Exists: SchoolYear 2026-2027 (activated)")
else:
    print("Exists: SchoolYear 2026-2027")

# 2) Ensure Semesters 1 and 2 exist (rooms page requires an active semester; spec: 2 semesters/year)
for sem_name in ["Sem 1", "Sem 2"]:
    sem = Semester.query.filter_by(school_year_id=year.id, name=sem_name).first()
    if sem is None:
        sem = Semester(school_year_id=year.id, name=sem_name, is_active=(sem_name == "Sem 1"))
        db.session.add(sem)
        print("Created: %s (is_active=%s)" % (sem_name, sem.is_active))

# 3) Create each missing role; refresh permissions on existing rows (bundles may evolve;
# names are stable, so updating perms here is safe and keeps shell-seeded DBs in sync)
for name, perms in ROLES.items():
    role = Role.query.filter_by(name=name).first()
    if role is None:
        db.session.add(Role(name=name, permissions=perms))  # permissions = JSON list column
        print("Created:", name)
    elif list(role.permissions or []) != list(perms):
        role.permissions = perms
        print("Updated perms:", name)
    else:
        print("Exists:", name)

db.session.commit()
print("DONE. Roles in ROLES:", len(ROLES))
