# run.py — the ONLY entry point Render + `flask` CLI use
# CS50x map: CS50x had `app = Flask(__name__)` global in app.py.
# Here we use FACTORY ONLY: create_app() builds the app so tests + prod can make
# separate instances from the same code. NEVER add a global Flask() here.
from app import create_app  # import the factory (defined in app/__init__.py)

# Build one instance for gunicorn (Render runs: gunicorn run:app)
# and for `flask run` locally (FLASK_APP=run.py tells CLI to look for `app` here)
app = create_app()

if __name__ == "__main__":
    # Only runs on `python run.py` (local double-click). `flask run` and gunicorn skip this.
    app.run()
