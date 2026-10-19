# seed_hrar.py -- Phase 2.1: seed all 57 HRAR rules (idempotent).
# Catalog lives in app/roster/default_hrar.py -- edit THERE, shell + /seed-hrar stay in sync.
# Also ensures auto_confirm_hours=48 exists (used by the log route for minor auto-confirm).
# Run once in flask shell:  exec(open("seed_hrar.py").read())
from app import db  # commit rows (ORM handle from factory)
from app.roster.models import Setting  # exact 1.1 model name -- DO NOT rename
from app.violations.models import ViolationRule  # Phase 2.1 model
from app.roster.default_hrar import RULES, SECTION_TITLES  # single source of truth

# 1) Ensure the auto-confirm window setting exists (minor -> now + 48h).
_auto = Setting.query.filter_by(key="auto_confirm_hours").first()
if _auto is None:
    db.session.add(Setting(key="auto_confirm_hours", value="48",
                           description="Auto-confirm window (hours) for minor violations"))
    print("Created: auto_confirm_hours = 48")
else:
    print("Exists: auto_confirm_hours =", _auto.value)

# 2) Create each missing rule; refresh mutable fields on existing rows so
# catalog edits propagate (codes are stable, so updating in place is safe).
created, updated = 0, 0
for code, meta in RULES.items():
    row = ViolationRule.query.filter_by(code=code).first()
    fields = dict(
        section=meta["section"],
        section_title=SECTION_TITLES.get(meta["section"], ""),
        title=meta["title"], description=meta["description"],
        severity=meta["severity"], points=meta.get("points") or 0,
        fine_type=meta["fine"].get("type", "none"),
        fine_amount=meta["fine"].get("amount_php", 0) or 0,
        fine_meta=meta["fine"], escalation=meta.get("escalation", []),
        who_can_log=meta.get("who_can_log", []),
        is_confidential=bool(meta.get("confidential", False)),
        confirmation=meta.get("confirmation", "adviser"),
        applies_when=meta.get("applies_when", "always"),
        review_note=meta.get("review"),
        requires_victim_complaint=bool(meta.get("requires_victim_complaint", False)),
        penalty_options=meta.get("penalty_options"),
        other_penalty=meta.get("other_penalty"),
        auto_source=meta.get("auto_source"), note=meta.get("note"),
    )
    if row is None:
        db.session.add(ViolationRule(code=code, **fields))
        print("Created:", code, meta["title"][:60])
        created += 1
    else:
        drift = any(getattr(row, k) != v for k, v in fields.items())
        if drift:
            for k, v in fields.items():
                setattr(row, k, v)
            print("Updated:", code)
            updated += 1
        else:
            print("Exists:", code)

db.session.commit()
print("DONE. Rules: %d total (%d created, %d updated)" % (ViolationRule.query.count(), created, updated))
