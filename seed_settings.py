# seed_settings.py -- Phase 1.5 Step 1: seed all 20 settings (idempotent).
# Metadata/defaults live in app/roster/default_settings.py -- edit THERE; shell + /seed-settings stay in sync.
# Run once in flask shell:  exec(open("seed_settings.py").read())
from app import db  # commit rows
from app.roster.models import Setting  # exact 1.1 model name
from app.roster.default_settings import SETTINGS  # single source of truth

for key, meta in SETTINGS.items():
    row = Setting.query.filter_by(key=key).first()
    if row is None:
        db.session.add(Setting(key=key, value=meta["value"], description=meta["label"]))
        print("Created:", key, "=", meta["value"])
    else:
        print("Exists:", key, "=", row.value)

db.session.commit()
print("DONE. Settings in SETTINGS:", len(SETTINGS))
