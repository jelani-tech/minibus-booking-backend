from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required

from application.api_serializers import customer_row_to_api
from infrastructure.supabase_write_repositories import SupabaseCustomerRepository
from models.public import db

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
customer_repository = SupabaseCustomerRepository()


def is_development_auth_enabled() -> bool:
    return current_app.config.get("APP_ENV") == "development" or current_app.debug


@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json() or {}

        if not data.get('phone') or not data.get('password') or not data.get('name'):
            return jsonify({'error': 'Phone, password, and name are required'}), 400

        customer = customer_repository.create_or_update(
            name=data['name'],
            phone=data['phone'],
            email=data.get('email'),
        )
        db.session.commit()

        access_token = create_access_token(identity=str(customer['id']))

        return jsonify({
            'message': 'User registered successfully',
            'user': customer_row_to_api(customer),
            'access_token': access_token
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json() or {}

        phone = data.get('phone')
        password = data.get('password')

        if not phone or not password:
            return jsonify({'error': 'Username/Phone and password are required'}), 400

        customer = customer_repository.find_by_phone(phone)
        if not customer:
            return jsonify({'error': 'Invalid credentials'}), 401

        if not is_development_auth_enabled():
            return jsonify({
                'error': 'Password login is not configured for Supabase customers yet'
            }), 501

        access_token = create_access_token(identity=str(customer['id']))

        return jsonify({
            'message': 'Login successful',
            'user': customer_row_to_api(customer),
            'access_token': access_token
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    try:
        customer_id = get_jwt_identity()
        customer = customer_repository.get(customer_id)

        if not customer:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({'user': customer_row_to_api(customer)}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
