from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config
from database import init_db
from routes.auth import auth_bp
from routes.trip import trip_bp
from routes.booking import booking_bp
from routes.payment import payment_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize JWT Manager
    jwt = JWTManager(app)
    
    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Initialize database
    init_db(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(trip_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(payment_bp)
    
    @app.route('/')
    def index():
        return {'message': 'Minibus Booking API', 'status': 'running'}, 200
    
    @app.route('/health', methods=['GET'])
    def health():
        return {'status': 'healthy'}, 200
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=8000)

