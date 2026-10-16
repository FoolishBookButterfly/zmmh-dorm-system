# config.py — Dev vs Prod settings, read from environment (.env locally, Render env vars in prod)
# CS50x map: CS50x had app.config["SESSION..."] inline in app.py; here we split per-environment
# so local SQLite and Render Postgres use the same code with different URLs.
import os  # os.getenv() reads .env (via python-dotenv) and Render env vars


class DevConfig:
    """Local development: SQLite file, debugger-friendly."""

    # Secret for Flask sessions + Flask-WTF CSRF tokens
    # NEVER hardcode prod secret — read from env, fallback only for local first-run
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    # SQLite file zmmh.db in project root (CS50x finance.db equivalent)
    # DATABASE_URL=sqlite:///zmmh.db in .env
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///zmmh.db")

    # Silence warning; we don't need event signals
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class ProdConfig:
    """Render production: Postgres URL from Render env, DEBUG off."""

    SECRET_KEY = os.getenv("SECRET_KEY")  # Must be set on Render — no fallback (fail fast if missing)
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")  # Render Postgres, e.g. postgresql://...
    SQLALCHEMY_TRACK_MODIFICATIONS = False
