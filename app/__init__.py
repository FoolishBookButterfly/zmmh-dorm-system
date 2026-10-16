# app/__init__.py — FACTORY: create_app() builds and returns the Flask app
# CS50x map: CS50x did everything in one app.py. Factory lets us create MANY app
# instances (dev, test, prod) from one function — required for migrations + tests.
import os  # to check FLASK_ENV (development vs production)
from flask import Flask  # the Flask class (we instantiate INSIDE the function, not globally)
from flask_sqlalchemy import SQLAlchemy  # ORM: db.Model + db.session instead of cs50.SQL
from flask_migrate import Migrate  # migrations: change tables without deleting data
from flask_login import LoginManager  # login: current_user + @login_required vs session["user_id"]
from flask_mail import Mail  # email: temp passwords + notifications (spec 5.1)
from dotenv import load_dotenv  # loads .env into os.getenv()

# Load .env BEFORE reading config (so os.getenv sees SECRET_KEY, DATABASE_URL locally)
load_dotenv()

# Extension objects created ONCE globally (no app yet), then init_app(app) inside factory.
# This is the standard factory pattern — extensions wait for the app to exist.
db = SQLAlchemy()  # ORM handle: Person.query..., db.session.add/commit
migrate = Migrate()  # handles `flask db migrate/upgrade`
login_manager = LoginManager()  # handles login sessions + unauthorized redirects
mail = Mail()  # handles Flask-Mail send (configured but unused until Phase 1)


def create_app():
    """Build the Flask app. Called by run.py (app = create_app()) and by tests."""
    # Create the app instance (INSIDE function — no global app = Flask() anywhere)
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

    # Where @login_required sends anonymous users (our dummy login page for now)
    login_manager.login_view = "auth.login"

    # Register blueprints = mini-apps (CS50x had all routes in app.py; we split per module)
    # auth/ handles login/logout now, roster/violations/finance/... later per roadmap
    from app.auth.routes import auth_bp  # noqa: E402 (import after init to avoid cycles)
    app.register_blueprint(auth_bp)

    return app  # factory RETURNS the app — run.py assigns it to `app`
