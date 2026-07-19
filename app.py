import hashlib
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


# Secrets requis pour signer les données confiées au client (JWT, et à terme
# sessions/CSRF Flask via SECRET_KEY). En production, l'absence de l'un d'eux
# doit empêcher le démarrage plutôt que de laisser l'app tourner avec une clé
# faible ; en développement, on tolère une valeur de repli avec un avertissement.
REQUIRED_SECRETS = ('SECRET_KEY', 'JWT_SECRET_KEY')


def _require_secrets(app):
    is_prod = app.config.get('APP_ENV') != 'development'
    for key in REQUIRED_SECRETS:
        value = app.config.get(key)
        if not value:
            if is_prod:
                raise RuntimeError(
                    f"{key} n'est pas défini : refus de démarrer en production. "
                    f"Configurez la variable d'environnement {key}."
                )
            # Dev uniquement : repli explicite pour que l'app tourne en local.
            app.config[key] = f"dev-{key.lower()}-not-for-production"
            logger.warning(
                f"{key} non défini : utilisation d'une valeur de développement "
                "(ne jamais utiliser en production)"
            )
        else:
            fingerprint = hashlib.sha256(value.encode()).hexdigest()[:8]
            logger.info(f"{key} chargé (empreinte {fingerprint})")


def _require_payment_provider_config(app):
    """Valide la config du provider de paiement actif au démarrage.

    Les clés JEKO ne sont exigées que si PAYMENT_PROVIDER=jeko (les webhooks des
    deux providers restent actifs, mais seule l'initiation dépend du provider
    actif). En production, une config incomplète empêche le démarrage ; en
    développement, on tolère avec un avertissement.
    """
    is_prod = app.config.get('APP_ENV') != 'development'
    provider = (app.config.get('PAYMENT_PROVIDER') or 'paystack').lower()

    if provider not in ('paystack', 'jeko'):
        raise RuntimeError(
            f"PAYMENT_PROVIDER '{provider}' invalide : valeurs acceptées 'paystack' ou 'jeko'."
        )

    if provider == 'jeko':
        required = (
            'JEKO_API_KEY',
            'JEKO_API_KEY_ID',
            'JEKO_STORE_ID',
            'JEKO_WEBHOOK_SECRET',
            'PAYMENT_PUBLIC_BASE_URL',
        )
        missing = [key for key in required if not app.config.get(key)]
        if missing:
            message = (
                f"PAYMENT_PROVIDER=jeko mais variables manquantes : {', '.join(missing)}."
            )
            if is_prod:
                raise RuntimeError(f"{message} Refus de démarrer en production.")
            logger.warning(message)

    logger.info(f"Payment provider actif pour les initiations : {provider}")


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

    # Après init_db, qui réapplique la config : vérifie les secrets (et pose le
    # repli de dev) une fois que plus aucun from_object ne peut l'écraser.
    _require_secrets(app)
    _require_payment_provider_config(app)

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
    # Serveur de dev uniquement : en production l'app est servie par gunicorn
    # (cf. Dockerfile) et ce bloc n'est jamais exécuté. Le mode debug (débogueur
    # Werkzeug + auto-reload) n'est activé qu'en environnement de développement.
    app = create_app()
    debug = app.config.get('APP_ENV') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=8000)

