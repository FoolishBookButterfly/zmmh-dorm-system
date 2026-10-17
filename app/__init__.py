# app/__init__.py -- FACTORY: create_app() builds and returns the Flask app
# CS50x map: CS50x did everything in one app.py. Factory lets us create MANY app
# instances (dev, test, prod) from one function -- required for migrations + tests.
import os  # to check FLASK_ENV (development vs production)
from flask import Flask, redirect, url_for, request  # redirect/url_for for login + force-change guard
from flask_sqlalchemy import SQLAlchemy  # ORM: db.Model + db.session instead of cs50.SQL
from flask_migrate import Migrate  # migrations: change tables without deleting data
from flask_login import LoginManager  # login: current_user + @login_required vs session["user_id"]
from flask_mail import Mail  # email: temp passwords + notifications (spec 5.1)
from dotenv import load_dotenv  # loads .env into os.getenv()
from sqlalchemy import MetaData  # lets us name FK constraints (SQLite batch alters REQUIRE names)

# Load .env BEFORE reading config (so os.getenv sees SECRET_KEY, DATABASE_URL locally)
load_dotenv()

# Naming convention: every ForeignKey gets a predictable name like fk_room_assignment_residency_id_residency
# WHY: SQLite can't ALTER tables; Alembic copies the table instead (batch mode), and batch mode
# crashes with "Constraint must have a name" on anonymous FKs (your 02e534cf81b7 failure).
# CS50x map: CS50x never altered tables (deleted finance.db); we name constraints so alters work.
_naming_convention = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}

# Extension objects created ONCE globally (no app yet), then init_app(app) inside factory.
# This is the standard factory pattern -- extensions wait for the app to exist.
db = SQLAlchemy(metadata=MetaData(naming_convention=_naming_convention))  # ORM handle: Person.query..., db.session.add/commit
migrate = Migrate()  # handles `flask db migrate/upgrade`
login_manager = LoginManager()  # handles login sessions + unauthorized redirects
mail = Mail()  # handles Flask-Mail send (configured but unused until Phase 1)


def create_app():
    """Build the Flask app. Called by run.py (app = create_app()) and by tests."""
    # Create the app instance (INSIDE function -- no global app = Flask() anywhere)
    app = Flask(__name__)

    # Pick config: production on Render (FLASK_ENV=production) else local DevConfig
    # config.py reads SECRET_KEY + DATABASE_URL from env
    if os.getenv("FLASK_ENV") == "production":
        from config import ProdConfig  # import here to avoid circular imports
        app.config.from_object(ProdConfig)
    else:
        from config import DevConfig
        app.config.from_object(DevConfig)

    # Wire extensions to THIS app instance
    db.init_app(app)  # ORM now knows the DB URL
    migrate.init_app(app, db)  # migrations now track db.Model changes
    login_manager.init_app(app)  # login now guards routes
    mail.init_app(app)  # mail ready for Phase 1 temp-password emails

    # Where @login_required sends anonymous users (was redirect to apology in CS50x)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        """Flask-Login calls this per request to turn session id -> User object."""
        from app.roster.models import User  # local import avoids circular import at startup
        try:
            return User.query.get(int(user_id))
        except (TypeError, ValueError):
            return None

    @login_manager.unauthorized_handler
    def _unauth():
        """Anonymous hitting @login_required -> /login?next=<page> (CS50x redirected to /login too)."""
        return redirect(url_for("auth.login", next=request.path))

    # Register blueprints = mini-apps (CS50x had all routes in app.py; we split per module)
    # auth/ handles login/logout now, roster/violations/finance/... later per roadmap
    from app.auth.routes import auth_bp  # noqa: E402 (import after init to avoid cycles)
    app.register_blueprint(auth_bp)

    # Import models so Flask-Migrate sees the tables (no-op at runtime, needed for autogenerate)
    # Phase 1.1: roster models only; later phases add violations/finance/... imports here
    from app.roster import models as roster_models  # noqa: E402,F401

    @app.before_request
    def _force_password_change():
        """Temp-password users must visit /change-password first (spec 5.1). Exempts auth + static."""
        from flask_login import current_user  # local import: factory loads before login context exists
        # Anonymous: Flask-Login's own handler deals with them (don't interfere)
        if not getattr(current_user, "is_authenticated", False):
            return None
        # No forced change needed: let them through
        if not getattr(current_user, "must_change_password", False):
            return None
        # Exempt list: without these the user could never reach the change form (redirect loop)
        allowed = {"auth.login", "auth.logout", "auth.change_password", "auth.forgot", "auth.reset", "static"}
        if request.endpoint in allowed:
            return None
        return redirect(url_for("auth.change_password"))

    # Template helper (Phase 1.3 Step 2): every template can ask can("finance.view") -> bool.
    # Plate 2B rule: Authority tabs/nav links render ONLY when this returns True.
    from flask_login import current_user  # noqa: E402 -- the logged-in User (or AnonymousUser)
    from app.utils.decorators import has_permission  # noqa: E402 -- Step 1 central gate

    @app.context_processor
    def _inject_can():
        """Jinja gets can(permission) -> bool for current_user (False when anonymous)."""
        def can(permission):
            return has_permission(current_user, permission)
        return {"can": can}

    return app  # factory RETURNS the app -- run.py assigns it to `app`
