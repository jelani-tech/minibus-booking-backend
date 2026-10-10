import uuid
from datetime import datetime, timedelta, timezone
import secrets

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.exc import IntegrityError
from loguru import logger

from application.api_serializers import customer_row_to_api
from infrastructure.supabase_write_repositories import (
    SupabaseAuthRepository,
    SupabaseCustomerRepository,
)
from logger import mask_phone
from models.public import db
from routes.auth_sessions import logout_response, refresh_response, token_service
from routes.guards import customer_required
from services.auth.audiences import CUSTOMER_APP
from services.auth.token_service import Principal
from services.email_service import BrevoEmailService

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

auth_repository = SupabaseAuthRepository()
customer_repository = SupabaseCustomerRepository()
email_service = BrevoEmailService()


def _customer_principal(customer):
    return Principal(identity=str(customer['id']), auth_user_id=str(customer['auth_user_id']))


def _resolve_customer_principal(auth_user_id):
    customer = customer_repository.find_by_auth_user_id(auth_user_id)
    return _customer_principal(customer) if customer else None


def _open_customer_session(customer, data):
    return token_service.open_session(
        _customer_principal(customer),
        CUSTOMER_APP,
        device_id=(data.get('device_id') or '').strip() or None,
    )


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
    2. Créer l'entrée dans auth.users avec le mot de passe hashé. Un compte
       chauffeur sans mot de passe est réutilisé : un chauffeur peut devenir
       client avec le même numéro.
    3. Créer / mettre à jour le profil dans public.customers en liant auth_user_id.
    4. Retourner le profil et les jetons.
    """
    phone = ''
    try:
        data = request.get_json() or {}

        phone = data.get('phone', '').strip()
        password = data.get('password', '').strip()
        name = data.get('name', '').strip()

        logger.info(f"Registration attempt for phone {mask_phone(phone)}")

        if not phone or not password or not name:
            logger.warning("Registration rejected: missing required fields (phone/password/name)")
            return jsonify({'error': 'Les champs phone, password et name sont obligatoires'}), 400

        if len(password) < 6:
            logger.warning(f"Registration rejected for {mask_phone(phone)}: password too short")
            return jsonify({'error': 'Le mot de passe doit contenir au moins 6 caractères'}), 400

        # 1. Vérifier si un compte auth existe déjà pour ce numéro
        auth_user = auth_repository.find_by_phone(phone)
        if auth_user and auth_user.get('encrypted_password'):
            logger.warning(f"Registration rejected: account already exists for {mask_phone(phone)}")
            return jsonify({'error': 'Un compte existe déjà pour ce numéro de téléphone.'}), 409

        # 2. Poser le mot de passe (hashé via bcrypt) sur le compte auth.users
        if auth_user:
            auth_repository.update_password(phone=phone, password=password)
        else:
            user_id = str(uuid.uuid4())
            auth_user = auth_repository.create(user_id= user_id, phone=phone, password=password)

        # 3. Créer / mettre à jour le profil public.customers en liant auth_user_id
        customer = customer_repository.create_or_update(
            name=name,
            phone=phone,
            email=data.get('email'),
            auth_user_id=auth_user['id'],
        )

        # 4. Ouvrir la session : access token (identité = ID customer) + refresh token
        tokens = _open_customer_session(customer, data)
        db.session.commit()

        logger.info(f"Registration successful for {mask_phone(phone)} (customer_id={customer['id']})")

        return jsonify({
            'message': 'Inscription réussie',
            'user': customer_row_to_api(customer),
            **tokens.to_api(),
        }), 201

    except IntegrityError as error:
        db.session.rollback()
        logger.warning(f"Registration conflict: phone already in use ({mask_phone(phone)}, {error})")
        return jsonify({'error': 'Un compte existe déjà pour ce numéro de téléphone.'}), 409
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error during registration for {mask_phone(phone)}: {e}")
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """Connexion d'un client existant.

    Flux :
    1. Valider les champs requis (phone, password).
    2. Vérifier le mot de passe via auth.users (bcrypt).
    3. Récupérer le profil public.customers lié.
    4. Retourner le profil et les jetons.
    """
    phone = ''
    try:
        data = request.get_json() or {}

        phone = data.get('phone', '').strip()
        password = data.get('password', '').strip()

        logger.info(f"Login attempt for phone {mask_phone(phone)}")

        if not phone or not password:
            logger.warning("Login rejected: missing required fields (phone/password)")
            return jsonify({'error': 'Les champs phone et password sont obligatoires'}), 400

        # 1. Vérifier le mot de passe dans auth.users
        auth_user = auth_repository.verify_password(phone, password)
        if not auth_user:
            # Réponse générique pour ne pas indiquer si le compte existe ou non
            logger.warning(f"Login failed: invalid credentials for {mask_phone(phone)}")
            return jsonify({'error': 'Identifiants invalides'}), 401

        # 2. Récupérer le profil customer lié
        customer = customer_repository.find_by_auth_user_id(auth_user['id'])
        if not customer:
            # Edge case : auth.users existe mais pas de customer (ne devrait pas arriver)
            logger.error(
                f"Login inconsistency: auth user {auth_user['id']} has no linked customer profile "
                f"(phone {mask_phone(phone)})"
            )
            return jsonify({'error': 'Profil client introuvable'}), 404

        # 3. Ouvrir la session : access token + refresh token
        tokens = _open_customer_session(customer, data)
        db.session.commit()

        logger.info(f"Login successful for {mask_phone(phone)} (customer_id={customer['id']})")

        return jsonify({
            'message': 'Connexion réussie',
            'user': customer_row_to_api(customer),
            **tokens.to_api(),
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error during login for {mask_phone(phone)}: {e}")
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """Échange le refresh token contre une nouvelle paire de jetons."""
    return refresh_response(
        CUSTOMER_APP,
        lambda refresh_token: token_service.rotate(
            refresh_token, CUSTOMER_APP, _resolve_customer_principal
        ),
    )


@auth_bp.route('/logout', methods=['POST'])
@customer_required
def logout():
    """Révoque la session en cours."""
    return logout_response(CUSTOMER_APP)


@auth_bp.route('/me', methods=['GET'])
@customer_required
def get_current_user():
    """Retourne le profil du client authentifié (via JWT)."""
    try:
        customer_id = get_jwt_identity()
        customer = customer_repository.get(customer_id)

        if not customer:
            logger.warning(f"Profile lookup failed: customer not found (customer_id={customer_id})")
            return jsonify({'error': 'Utilisateur introuvable'}), 404

        return jsonify({'user': customer_row_to_api(customer)}), 200

    except Exception as e:
        logger.exception(f"Error fetching current user profile: {e}")
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
    phone = ''
    try:
        data = request.get_json() or {}
        phone = data.get('phone', '').strip()

        logger.info(f"Password reset requested for phone {mask_phone(phone)}")

        if not phone:
            logger.warning("Password reset rejected: phone is required")
            return jsonify({'error': 'Le numéro de téléphone est obligatoire'}), 400

        # 1. Vérifier si un compte auth existe
        auth_user = auth_repository.find_by_phone(phone)
        if not auth_user:
            logger.warning(f"Password reset rejected: no account for {mask_phone(phone)}")
            return jsonify({'error': 'Aucun compte associé à ce numéro de téléphone'}), 404

        # 2. Récupérer le profil du client pour extraire l'email
        customer = customer_repository.find_by_auth_user_id(auth_user['id'])
        if not customer or not customer.get('email'):
            logger.warning(
                f"Password reset rejected: no email configured for {mask_phone(phone)}"
            )
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
            logger.error(
                f"Password reset failed: could not send OTP email to {_mask_email(email)} "
                f"for {mask_phone(phone)}"
            )
            return jsonify({'error': 'Erreur lors de l\'envoi de l\'e-mail de vérification'}), 500

        db.session.commit()

        logger.info(
            f"Password reset OTP sent to {_mask_email(email)} for {mask_phone(phone)}"
        )

        return jsonify({
            'message': 'Code de réinitialisation envoyé par e-mail',
            'email': _mask_email(email)
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error during password reset request for {mask_phone(phone)}: {e}")
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/reset-password/reset', methods=['POST'])
def reset_password():
    """Valide le code OTP et applique le nouveau mot de passe."""
    phone = ''
    try:
        data = request.get_json() or {}
        phone = data.get('phone', '').strip()
        otp_code = data.get('otp_code', '').strip()
        new_password = data.get('new_password', '').strip()

        logger.info(f"Password reset confirmation attempt for {mask_phone(phone)}")

        if not phone or not otp_code or not new_password:
            logger.warning("Password reset rejected: missing required fields (phone/otp_code/new_password)")
            return jsonify({'error': 'Les champs phone, otp_code et new_password sont obligatoires'}), 400

        if len(new_password) < 6:
            logger.warning(f"Password reset rejected for {mask_phone(phone)}: password too short")
            return jsonify({'error': 'Le mot de passe doit contenir au moins 6 caractères'}), 400

        # 1. Valider le code OTP actif
        otp_entry = auth_repository.find_active_otp(phone=phone, otp_code=otp_code)
        if not otp_entry:
            logger.warning(f"Password reset rejected for {mask_phone(phone)}: invalid or expired OTP")
            return jsonify({'error': 'Code de vérification invalide ou expiré'}), 400

        # 2. Mettre à jour le mot de passe dans auth.users
        password_updated = auth_repository.update_password(phone=phone, password=new_password)
        if not password_updated:
            logger.error(f"Password reset failed for {mask_phone(phone)}: account not found during update")
            return jsonify({'error': 'Compte utilisateur introuvable'}), 404

        # 3. Marquer l'OTP comme utilisé
        auth_repository.mark_otp_as_used(otp_entry['id'])
        db.session.commit()

        logger.info(f"Password reset successful for {mask_phone(phone)}")

        return jsonify({'message': 'Votre mot de passe a été réinitialisé avec succès'}), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error during password reset for {mask_phone(phone)}: {e}")
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/update', methods=['PUT'])
@customer_required
def update_profile():
    """Updates the authenticated customer's profile (name, phone, email).

    Flow:
    1. Validate that at least one of the fields (phone, email, name) is provided.
    2. If the phone number changes, check it isn't already used by another
       account, then update it in auth.users (login) and public.customers.
    3. Update the name and/or email in public.customers.
    4. Return the updated profile.
    """
    customer_id = get_jwt_identity()
    try:
        data = request.get_json() or {}
        phone = (data.get('phone') or '').strip() or None
        email = (data.get('email') or '').strip() or None
        name = (data.get('name') or '').strip() or None

        if not phone and not email and not name:
            logger.warning(f"Profile update rejected for customer_id={customer_id}: no field provided")
            return jsonify({'error': 'Au moins un des champs phone, email ou name est requis'}), 400

        customer = customer_repository.get(customer_id)
        if not customer:
            logger.warning(f"Profile update rejected: customer not found (customer_id={customer_id})")
            return jsonify({'error': 'Utilisateur introuvable'}), 404

        if phone and phone != customer.get('phone'):
            existing = customer_repository.find_by_phone(phone)
            if existing and str(existing['id']) != str(customer_id):
                logger.warning(f"Profile update rejected for {customer_id}: phone {mask_phone(phone)} already in use")
                return jsonify({'error': 'Ce numéro de téléphone est déjà utilisé par un autre compte'}), 409

            if customer.get('auth_user_id') and customer.get('phone'):
                auth_repository.update_phone(old_phone=customer['phone'], new_phone=phone)

        updated_customer = customer_repository.update_profile(
            customer_id=customer_id,
            name=name,
            phone=phone,
            email=email,
        )
        db.session.commit()

        logger.info(f"Profile updated for customer_id={customer_id}")

        return jsonify({
            'message': 'Profil mis à jour avec succès',
            'user': customer_row_to_api(updated_customer),
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error during updating profile for {customer_id}: {e} ")
        return jsonify({'error': str(e)}), 500