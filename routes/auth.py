from datetime import datetime, timedelta, timezone
import secrets

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError

from application.api_serializers import customer_row_to_api
from infrastructure.supabase_write_repositories import (
    SupabaseAuthRepository,
    SupabaseCustomerRepository,
)
from models.public import db
from services.email_service import BrevoEmailService

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

auth_repository = SupabaseAuthRepository()
customer_repository = SupabaseCustomerRepository()
email_service = BrevoEmailService()


def _mask_email(email: str) -> str:
    parts = email.split('@', 1)
    if len(parts) != 2:
        return f"{email[:3]}***"

    local_part, domain = parts
    if len(local_part) <= 2:
        masked_local = f"{local_part}***"
    else:
        masked_local = f"{local_part[:2]}{'*' * (len(local_part) - 2)}"
    return f"{masked_local}@{domain}"


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


@auth_bp.route('/reset-password/request', methods=['POST'])
def request_password_reset():
    """Demande de réinitialisation de mot de passe via l'envoi d'un code OTP par e-mail.

    Flux :
    1. Récupérer le numéro de téléphone.
    2. Trouver l'utilisateur et son profil client lié.
    3. Si le profil a un e-mail configuré, générer un OTP à 6 chiffres.
    4. Enregistrer l'OTP en base avec une validité de 15 minutes.
    5. Envoyer le mail via Brevo.
    6. Retourner l'e-mail masqué à l'application mobile.
    """
    try:
        data = request.get_json() or {}
        phone = data.get('phone', '').strip()

        if not phone:
            return jsonify({'error': 'Le numéro de téléphone est obligatoire'}), 400

        # 1. Vérifier si un compte auth existe
        auth_user = auth_repository.find_by_phone(phone)
        if not auth_user:
            return jsonify({'error': 'Aucun compte associé à ce numéro de téléphone'}), 404

        # 2. Récupérer le profil du client pour extraire l'email
        customer = customer_repository.find_by_auth_user_id(auth_user['id'])
        if not customer or not customer.get('email'):
            return jsonify({
                'error': 'Aucune adresse e-mail n\'est configurée pour ce compte. Veuillez contacter le support.'
            }), 400

        email = customer['email'].strip()
        first_name = customer.get('first_name') or 'Client'
        last_name = customer.get('last_name') or ''
        name = f"{first_name} {last_name}".strip()

        # 3. Générer un code OTP à 6 chiffres avec un générateur cryptographique.
        otp_code = f"{secrets.randbelow(900000) + 100000}"

        # 4. Enregistrer en base avec date d'expiration (+15 min)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        auth_repository.create_password_reset(
            phone=phone,
            email=email,
            otp_code=otp_code,
            expires_at=expires_at
        )

        # 5. Envoyer le mail avec Brevo
        sent = email_service.send_reset_otp_email(
            to_email=email,
            customer_name=name,
            otp_code=otp_code
        )

        if not sent:
            db.session.rollback()
            return jsonify({'error': 'Erreur lors de l\'envoi de l\'e-mail de vérification'}), 500

        db.session.commit()

        return jsonify({
            'message': 'Code de réinitialisation envoyé par e-mail',
            'email': _mask_email(email)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/reset-password/reset', methods=['POST'])
def reset_password():
    """Valide le code OTP et applique le nouveau mot de passe."""
    try:
        data = request.get_json() or {}
        phone = data.get('phone', '').strip()
        otp_code = data.get('otp_code', '').strip()
        new_password = data.get('new_password', '').strip()

        if not phone or not otp_code or not new_password:
            return jsonify({'error': 'Les champs phone, otp_code et new_password sont obligatoires'}), 400

        if len(new_password) < 6:
            return jsonify({'error': 'Le mot de passe doit contenir au moins 6 caractères'}), 400

        # 1. Valider le code OTP actif
        otp_entry = auth_repository.find_active_otp(phone=phone, otp_code=otp_code)
        if not otp_entry:
            return jsonify({'error': 'Code de vérification invalide ou expiré'}), 400

        # 2. Mettre à jour le mot de passe dans auth.users
        password_updated = auth_repository.update_password(phone=phone, password=new_password)
        if not password_updated:
            return jsonify({'error': 'Compte utilisateur introuvable'}), 404

        # 3. Marquer l'OTP comme utilisé
        auth_repository.mark_otp_as_used(otp_entry['id'])
        db.session.commit()

        return jsonify({'message': 'Votre mot de passe a été réinitialisé avec succès'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
