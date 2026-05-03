from models.public import db
from config import Config


def init_db(app):
    """Attach SQLAlchemy to the app.

    Supabase owns the physical schema in normal development and production.
    Legacy schema creation is kept behind a flag for old local environments.
    """
    app.config.from_object(Config)
    db.init_app(app)

    if not app.config.get("LEGACY_SCHEMA_BOOTSTRAP"):
        return

    with app.app_context():
        try:
            db.session.execute(db.text("CREATE SCHEMA IF NOT EXISTS clients"))
            db.session.execute(db.text("CREATE SCHEMA IF NOT EXISTS partners"))
            db.session.execute(db.text("CREATE SCHEMA IF NOT EXISTS public"))
            db.session.commit()
        except Exception as e:
            print(f"Schema creation warning: {e}")
        print("Legacy schemas initialized")
