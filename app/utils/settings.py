# app/utils/settings.py -- read API for editable settings (Phases 2-7 call these, never hardcode).
# CS50x map: like CS50x helpers.usd() but the number lives in the Setting TABLE, not the code.
from app import db  # ORM handle
from app.roster.models import Setting  # exact 1.1 model name -- DO NOT rename


def get_setting(key, default=None):
    """Raw string value for a key, or default when the row is missing (settings not seeded yet)."""
    row = Setting.query.filter_by(key=key).first()
    if row is None or row.value is None or row.value == "":
        return default
    return row.value


def get_int_setting(key, default=0):
    """Integer value for a key (weights, margins, fees). Returns default on missing/garbage."""
    raw = get_setting(key)
    if raw is None:
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


def get_choice_setting(key, choices, default=None):
    """Choice value constrained to the allowed list (e.g. missing_sem1_rule)."""
    raw = get_setting(key)
    if raw in choices:
        return raw
    return default if default is not None else choices[0]
