# config.py -- Dev vs Prod settings, read from environment (.env locally, Render env vars in prod)
# CS50x map: CS50x had app.config["SESSION..."] inline in app.py; here we split per-environment
# so local SQLite and Render Postgres use the same code with different URLs.
import os  # os.getenv() reads .env (via python-dotenv) and Render env vars


class DevConfig:
    """Local development: SQLite file, debugger-friendly, emails print to console."""

    # Secret for Flask sessions + Flask-WTF CSRF tokens
    # NEVER hardcode prod secret -- read from env, fallback only for local first-run
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    # SQLite file zmmh.db in project root (CS50x finance.db equivalent)
    # DATABASE_URL=sqlite:///zmmh.db in .env
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///zmmh.db")

    # Silence warning; we don't need event signals
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Salt mixed into password-reset tokens (Step 4 serializer); dev default is fine
    SECURITY_PASSWORD_SALT = os.getenv("SECURITY_PASSWORD_SALT", "zmmh-reset-dev")

    # Dev mail: DON'T send -- Step 2 email.py prints to console when True (your Q1: no Gmail yet)
    MAIL_SUPPRESS_SEND = True
    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")  # unused while suppressed
    MAIL_PORT = int(os.getenv("MAIL_PORT", "25"))
    MAIL_USE_TLS = False
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "zmmh@localhost")


class ProdConfig:
    """Render production: Postgres URL from Render env, DEBUG off, real Gmail when configured."""

    SECRET_KEY = os.getenv("SECRET_KEY")  # Must be set on Render -- no fallback (fail fast if missing)
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")  # Render Postgres, e.g. postgresql://...
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECURITY_PASSWORD_SALT = os.getenv("SECURITY_PASSWORD_SALT", "zmmh-reset")

    # Prod mail: set MAIL_* env on Render + Gmail App Password to actually send;
    # leave MAIL_SUPPRESS_SEND=True to keep console-print behavior while testing.
    MAIL_SUPPRESS_SEND = os.getenv("MAIL_SUPPRESS_SEND", "False").lower() == "true"
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "zmmh@localhost")
