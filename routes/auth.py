from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError

from application.api_serializers import customer_row_to_api
from infrastructure.supabase_write_repositories import (
    SupabaseAuthRepository,
    SupabaseCustomerRepository,
)
from models.public import db

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

auth_repository = SupabaseAuthRepository()
customer_repository = SupabaseCustomerRepository()


@auth_bp.route('/register', methods=['POST'])
def register():
    """Inscription d'un nouveau client via l'application mobile.

    Flux :
    1. Valider les champs requis (phone, password, name).
    2. Créer l'entrée dans auth.users avec le mot de passe hashé.
    3. Créer / mettre à jour le profil dans public.customers en liant auth_user_id.
    4. Retourner le profil et le JWT.
    """
    try:
        data = request.get_json() or {}

        phone = data.get('phone', '').strip()
        password = data.get('password', '').strip()
        name = data.get('name', '').strip()

        if not phone or not password or not name:
            return jsonify({'error': 'Les champs phone, password et name sont obligatoires'}), 400

        if len(password) < 6:
            return jsonify({'error': 'Le mot de passe doit contenir au moins 6 caractères'}), 400

        # 1. Vérifier si un compte auth existe déjà pour ce numéro
        existing_auth = auth_repository.find_by_phone(phone)
        if existing_auth:
            return jsonify({'error': 'Un compte existe déjà pour ce numéro de téléphone'}), 409

        # 2. Créer l'entrée auth.users (avec mot de passe hashé via bcrypt)
        auth_user = auth_repository.create(phone=phone, password=password)

        # 3. Créer / mettre à jour le profil public.customers en liant auth_user_id
        customer = customer_repository.create_or_update(
            name=name,
            phone=phone,
            email=data.get('email'),
            auth_user_id=auth_user['id'],
        )
        db.session.commit()

        # 4. Générer le JWT à partir de l'ID customer (logique métier inchangée)
        access_token = create_access_token(identity=str(customer['id']))

        return jsonify({
            'message': 'Inscription réussie',
            'user': customer_row_to_api(customer),
            'access_token': access_token,
        }), 201

    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Ce numéro de téléphone est déjà utilisé'}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """Connexion d'un client existant.

    Flux :
    1. Valider les champs requis (phone, password).
    2. Vérifier le mot de passe via auth.users (bcrypt).
    3. Récupérer le profil public.customers lié.
    4. Retourner le profil et le JWT.
    """
    try:
        data = request.get_json() or {}

        phone = data.get('phone', '').strip()
        password = data.get('password', '').strip()

        if not phone or not password:
            return jsonify({'error': 'Les champs phone et password sont obligatoires'}), 400

        # 1. Vérifier le mot de passe dans auth.users
        auth_user = auth_repository.verify_password(phone, password)
        if not auth_user:
            # Réponse générique pour ne pas indiquer si le compte existe ou non
            return jsonify({'error': 'Identifiants invalides'}), 401

        # 2. Récupérer le profil customer lié
        customer = customer_repository.find_by_auth_user_id(auth_user['id'])
        if not customer:
            # Edge case : auth.users existe mais pas de customer (ne devrait pas arriver)
            return jsonify({'error': 'Profil client introuvable'}), 404

        # 3. Générer le JWT
        access_token = create_access_token(identity=str(customer['id']))

        return jsonify({
            'message': 'Connexion réussie',
            'user': customer_row_to_api(customer),
            'access_token': access_token,
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Retourne le profil du client authentifié (via JWT)."""
    try:
        customer_id = get_jwt_identity()
        customer = customer_repository.get(customer_id)

        if not customer:
            return jsonify({'error': 'Utilisateur introuvable'}), 404

        return jsonify({'user': customer_row_to_api(customer)}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
