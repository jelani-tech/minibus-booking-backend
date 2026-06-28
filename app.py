import os
import click
from flask import Flask, current_app
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config
from database import init_db
from routes.auth import auth_bp
from routes.trip import trip_bp
from routes.booking import booking_bp
from routes.payment import payment_bp
from routes.lines import lines_bp

from flask_migrate import Migrate, upgrade
from models.public import db
from loguru import logger
from logger import setup_logging
# Import all models so Flask-Migrate sees them for migrations
import models.clients
import models.partners
import models.vehicles
import models.auth


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    setup_logging(
        logtail_token=os.getenv("LOGTAIL_TOKEN"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )

    # Initialize JWT Manager
    jwt = JWTManager(app)

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {'error': 'Session expired', 'code': 'token_expired'}, 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return {'error': 'Invalid token', 'code': 'invalid_token', 'detail': reason}, 401

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        return {'error': 'Authentication required', 'code': 'missing_token', 'detail': reason}, 401

    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Initialize database and Flask-Migrate
    init_db(app)
    # Multi-schema project (public/clients/partners):
    # include_schemas=True is required so Alembic autogenerate can resolve
    # cross-schema foreign keys (e.g. public.steps -> partners.partners).
    Migrate(app, db, include_schemas=True)

    if app.config.get("AUTO_UPGRADE_DB"):
        with app.app_context():
            migrate_dir = current_app.extensions["migrate"].directory
            if os.path.isdir(migrate_dir):
                try:
                    upgrade()
                    logger.info("Migrations applied successfully")
                except Exception as e:
                    logger.warning(f"Migration warning: {e}")
            else:
                logger.warning("Dossier 'migrations' absent. Première fois : flask db init puis flask db migrate -m 'Initial'")

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(trip_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(lines_bp)

    from routes.vehicles import vehicles_bp
    app.register_blueprint(vehicles_bp)

    @app.route('/')
    def index():
        return {'message': 'Minibus Booking API', 'status': 'running'}, 200

    @app.route('/health', methods=['GET'])
    def health():
        return {'status': 'healthy'}, 200


    @app.after_request
    def log_request(response):
        from flask import request
        logger.info(
            f"{request.method} {request.path} -> {response.status_code}"
        )
        return response

    # ── Log les erreurs non gérées ───────────────────────────────────────────
    @app.errorhandler(Exception)
    def handle_exception(e):
        from flask import request
        logger.exception(f"Erreur non gérée sur {request.path}: {e}")
        return {'error': 'Erreur interne'}, 500


    # ---------------------------------------------------------------------------
    # CLI commands (disponibles via `flask <cmd>`)
    # ---------------------------------------------------------------------------

    @app.cli.command("seed-lines")
    @click.option("--file", default="lines.xlsx", show_default=True, help="Chemin vers le fichier Excel")
    def seed_lines(file):
        """Importe les lignes et arrêts depuis un fichier Excel (local uniquement).

        Usage:
            docker exec minibus_local_backend flask seed-lines
            docker exec minibus_local_backend flask seed-lines --file /app/other.xlsx
        """
        if current_app.config.get("APP_ENV") != "development":
            click.echo("❌ Cette commande n'est disponible qu'en environnement 'development'.", err=True)
            raise SystemExit(1)
        from services.import_lines import import_lines_from_excel
        import_lines_from_excel(file_path=file)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=8000)

