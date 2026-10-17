# app/roster/default_roles.py -- SINGLE SOURCE OF TRUTH for the 17-role catalog (spec section 3).
# Imported by BOTH seed_roles.py (local shell workflow) and the /seed-roles route (Render, no shell).
# Change a bundle here once and both paths stay in sync. Names NEVER change -- decorators.py
# checks a.role.name == "Super-admin" for the bypass, and role_ids on fresh DBs follow this order.
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
    "Auditor": ["finance.view", "audit.view"],
    "VP Internal": ["announcements.post"],
    "VP External": ["announcements.post"],
    "Justice head": ["violations.log", "tickets.view"],
    "Kitchen head": ["violations.log", "tickets.view"],
    "IGP head": ["violations.log", "tickets.view"],
    "Repairs head": ["tickets.view"],
    "SA": ["cleaning.view", "cleaning.edit", "tickets.view", "violations.log", "clearance.room_inspect"],
    "Evaluator (temp)": ["evaluation.view"],
    "Occupant": [],
}
