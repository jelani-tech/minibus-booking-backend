from flask import Blueprint, request, jsonify
from models.public import db, User
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        # Validation
        if not data.get('phone') or not data.get('password') or not data.get('name'):
            return jsonify({'error': 'Phone, password, and name are required'}), 400
        
        # Check if user already exists
        if User.query.filter_by(phone=data['phone']).first():
            return jsonify({'error': 'User with this phone number already exists'}), 400
        
        # Create new user
        user = User(
            name=data['name'],
            phone=data['phone'],
            email=data.get('email'),
            created_at=datetime.utcnow()
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        # Generate token
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
            'message': 'User registered successfully',
            'user': user.to_dict(),
            'access_token': access_token
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        username = data.get('username')
        phone = data.get('phone')
        password = data.get('password')

        if not (username or phone) or not password:
            return jsonify({'error': 'Username/Phone and password are required'}), 400
        
        user = None
        if username:
            user = User.query.filter_by(username=username).first()
        elif phone:
            user = User.query.filter_by(phone=phone).first()
        
        if not user or not user.check_password(password):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict(),
            'role': user.role,
            'access_token': access_token
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({'user': user.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

