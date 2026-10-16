# app/auth/routes.py — AUTH blueprint (mini-app for login/logout)
# CS50x map: CS50x put /login in app.py. Blueprints let us split 12 modules
# (auth, roster, violations, finance...) each with own routes.py, registered in factory.
from flask import Blueprint  # Blueprint = "mini Flask app" mounted onto the main app

# Create the blueprint: name "auth", import name __name__, URL prefix none (routes as written)
# login_manager.login_view = "auth.login" in factory points here (blueprint_name.route_name)
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login")
def login():
    """Dummy login page — proves factory + blueprint wiring works. Full login in Phase 1."""
    return "Login page \u2014 Phase 0.2 done"
