# app/roster/default_settings.py -- SINGLE SOURCE OF TRUTH for editable settings (spec section 7:
# "every value marked editable lives in a settings screen, not in code").
# key -> metadata. value = default (string column in Setting; helpers parse).
# type: int | choice. group: card on the settings page. help: shown under the field.
SETTINGS = {
    # -- evaluation: overall 40/60, semester 30/30/25/15, cleaning 40/60, consensus 30/40/20/10 (spec 5.3)
    "w_sem1":          {"value": "40", "label": "Sem 1 weight (%)", "type": "int", "group": "Evaluation weights", "help": "Overall = w_sem1% Sem1 + w_sem2% Sem2."},
    "w_sem2":          {"value": "60", "label": "Sem 2 weight (%)", "type": "int", "group": "Evaluation weights", "help": "Memo check: 0.4 x 96.038 + 0.6 x 96.146 = 96.103."},
    "w_eval":          {"value": "30", "label": "Evaluators score (%)", "type": "int", "group": "Evaluation weights", "help": "Semester = eval + hrar + cleaning + peers = 100."},
    "w_hrar":          {"value": "30", "label": "HRAR score (%)", "type": "int", "group": "Evaluation weights", "help": "HRAR = 100 - confirmed deductions."},
    "w_cleaning":      {"value": "25", "label": "Cleaning score (%)", "type": "int", "group": "Evaluation weights", "help": "Attendance + assessment."},
    "w_peer":          {"value": "15", "label": "Peer score (%)", "type": "int", "group": "Evaluation weights", "help": "Roommate ratings."},
    "w_clean_att":     {"value": "40", "label": "Cleaning attendance share (%)", "type": "int", "group": "Evaluation weights", "help": "Cleaning = att% x attendance + assess% x assessment."},
    "w_clean_assess":  {"value": "60", "label": "Cleaning assessment share (%)", "type": "int", "group": "Evaluation weights", "help": "Should pair to 100 with attendance share."},
    "w_cons_l":        {"value": "30", "label": "Leadership share (%)", "type": "int", "group": "Evaluation weights", "help": "Consensus evaluator score = L + P + R + A = 100."},
    "w_cons_p":        {"value": "40", "label": "Participation share (%)", "type": "int", "group": "Evaluation weights", "help": ""},
    "w_cons_r":        {"value": "20", "label": "Rapport share (%)", "type": "int", "group": "Evaluation weights", "help": ""},
    "w_cons_a":        {"value": "10", "label": "Attitude share (%)", "type": "int", "group": "Evaluation weights", "help": ""},
    "quorum_min":      {"value": "11", "label": "Minimum evaluators present (of 13)", "type": "int", "group": "Evaluation weights", "help": "Decision 4: consensus sheet needs at least this many."},
    "missing_sem1_rule": {"value": "Sem 2 counts in full", "label": "Missing Sem 1 rule", "type": "choice",
             "choices": ["Sem 2 counts in full", "Sem 1 counts as zero"], "group": "Evaluation weights",
             "help": "Decision 1: default matches Memorandum No. 03, s. 2026."},
    # -- status rules (spec 5.3; 70/37/10 editable by advisers AND super-admin per hall decision)
    "cutoff_failed":   {"value": "70", "label": "Failed below", "type": "int", "group": "Status rules", "help": "Overall < this = Failed (permanent re-admission bar)."},
    "cap_retained":    {"value": "37", "label": "Retained seats", "type": "int", "group": "Status rules", "help": "Ranks 1..this = Retained (at or above cutoff)."},
    "cap_waitlisted":  {"value": "10", "label": "Waitlisted seats", "type": "int", "group": "Status rules", "help": "Next this many = Waitlisted; rest Recommended."},
    "danger_margin":   {"value": "3", "label": "In-danger margin", "type": "int", "group": "Status rules", "help": "Decision 3: alert when provisional <= cutoff + margin (70+3 = 73)."},
    # -- violations (decisions 5 + 7)
    "dispute_days":    {"value": "3", "label": "Dispute window (days)", "type": "int", "group": "Violations", "help": "Decision 7: occupant may dispute within this many days of notice."},
    "auto_confirm_hours": {"value": "48", "label": "Auto-confirm window (hours)", "type": "int", "group": "Violations", "help": "Decision 5: minor violations (<=3 pts, no escalation, fine<50, not confidential) become effective after this many hours unless rejected/disputed."},
    # -- finance (spec 1 + 5.5)
    "maintenance_fee": {"value": "700", "label": "Maintenance fee per semester (PHP)", "type": "int", "group": "Finance", "help": "Auto-charged each semester; partial payment allowed."},
}
