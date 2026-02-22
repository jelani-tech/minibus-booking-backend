import os
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
# Import all models so Flask-Migrate sees them for migrations
import models.transport
import models.clients
import models.partners
import models.common
import models.vehicles


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize JWT Manager
    jwt = JWTManager(app)

    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Initialize database and Flask-Migrate
    init_db(app)
    Migrate(app, db)

    # Apply pending migrations automatically at startup (only if migrations folder exists)
    with app.app_context():
        migrate_dir = current_app.extensions["migrate"].directory
        if os.path.isdir(migrate_dir):
            try:
                upgrade()
                print("Migrations applied successfully")
            except Exception as e:
                print(f"Migration warning: {e}")
        else:
            print("Dossier 'migrations' absent. Première fois : flask db init puis flask db migrate -m 'Initial'")

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
    
    return app

if __name__ == '__main__':
    app = create_app()
    # Import lines from Excel only when starting the server (not for CLI: flask db init, etc.)
    with app.app_context():
        try:
            from services.import_lines import import_lines_from_excel
            import_lines_from_excel()
        except Exception as e:
            print(f"Startup import failed: {e}")
    app.run(debug=True, host='0.0.0.0', port=8000)

