"""Routes de l'application chauffeur.

Pas d'auto-inscription : le compte et le PIN provisoire sont créés par un admin.
Toutes les routes authentifiées exigent un jeton driver-app (cf. routes.guards).
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from loguru import logger

from application.api_serializers import driver_row_to_api
from infrastructure.supabase_auth_repositories import SupabaseDriverRepository
from logger import mask_phone
from models.public import db
from routes.auth_sessions import logout_response, refresh_response
from routes.guards import app_jwt_required, current_session_id, driver_required
from services.auth.audiences import DRIVER_APP
from services.auth.driver_auth_service import DriverAuthService, LoginContext
from services.auth.errors import AuthenticationFailed, PinChangeRejected

driver_bp = Blueprint('driver', __name__, url_prefix='/api/driver')

driver_auth_service = DriverAuthService()
driver_repository = SupabaseDriverRepository()

INVALID_CREDENTIALS_MESSAGE = (
    'Identifiants invalides. En cas de difficulté, contactez le support.'
)


def _client_ip():
    """IP du client ; derrière le proxy de Render, la première de X-Forwarded-For."""
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    return forwarded_for.split(',')[0].strip() or request.remote_addr


@driver_bp.route('/auth/login', methods=['POST'])
def login():
    """Connexion par téléphone + PIN depuis l'appareil enregistré.

    Tout échec d'authentification renvoie le même 401 : la raison exacte n'est
    visible que dans le journal des connexions.
    """
    data = request.get_json(silent=True) or {}
    phone = (data.get('phone') or '').strip()
    pin = (data.get('pin') or '').strip()
    device_id = (data.get('device_id') or '').strip()

    if not phone or not pin or not device_id:
        logger.warning("Driver login rejected: missing required fields (phone/pin/device_id)")
        return jsonify({'error': 'Les champs phone, pin et device_id sont obligatoires'}), 400

    context = LoginContext(
        phone=phone,
        device_id=device_id,
        ip_address=_client_ip(),
        user_agent=request.headers.get('User-Agent'),
    )
    try:
        result = driver_auth_service.login(context, pin)
        db.session.commit()

        logger.info(f"Driver login successful for {mask_phone(phone)} (driver_id={result.driver['id']})")
        return jsonify({
            'message': 'Connexion réussie',
            'driver': driver_row_to_api(result.driver),
            'must_change_pin': result.must_change_pin,
            **result.tokens.to_api(),
        }), 200

    except AuthenticationFailed as error:
        # Commit : le journal et le compteur d'échecs doivent être conservés.
        db.session.commit()
        logger.warning(f"Driver login failed for {mask_phone(phone)}: {error.reason}")
        return jsonify({'error': INVALID_CREDENTIALS_MESSAGE, 'code': 'invalid_credentials'}), 401

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error during driver login for {mask_phone(phone)}: {e}")
        return jsonify({'error': 'Erreur interne'}), 500


@driver_bp.route('/auth/pin', methods=['PUT'])
@app_jwt_required(DRIVER_APP, allow_pending_pin_change=True)
def change_pin():
    """Remplace le PIN (obligatoire au premier login). Retourne un nouvel access
    token, qui ne porte plus l'obligation de changer de PIN."""
    driver_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    current_pin = (data.get('current_pin') or '').strip()
    new_pin = (data.get('new_pin') or '').strip()

    if not current_pin or not new_pin:
        return jsonify({'error': 'Les champs current_pin et new_pin sont obligatoires'}), 400

    try:
        access_token = driver_auth_service.change_pin(
            driver_id=driver_id,
            session_id=current_session_id(),
            current_pin=current_pin,
            new_pin=new_pin,
        )
        db.session.commit()

        logger.info(f"Driver PIN changed (driver_id={driver_id})")
        return jsonify({'message': 'PIN modifié avec succès', 'access_token': access_token}), 200

    except PinChangeRejected as error:
        # Commit : un PIN actuel incorrect compte dans les échecs.
        db.session.commit()
        logger.warning(f"Driver PIN change rejected (driver_id={driver_id}): {error.code}")
        return jsonify({'error': error.message, 'code': error.code}), 400

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error during driver PIN change (driver_id={driver_id}): {e}")
        return jsonify({'error': 'Erreur interne'}), 500


@driver_bp.route('/auth/refresh', methods=['POST'])
def refresh():
    return refresh_response(DRIVER_APP, driver_auth_service.refresh)


@driver_bp.route('/auth/logout', methods=['POST'])
@app_jwt_required(DRIVER_APP, allow_pending_pin_change=True)
def logout():
    return logout_response(DRIVER_APP)


@driver_bp.route('/me', methods=['GET'])
@driver_required
def get_current_driver():
    driver_id = get_jwt_identity()
    try:
        driver = driver_repository.get(driver_id)
        if not driver:
            logger.warning(f"Driver profile lookup failed: driver not found (driver_id={driver_id})")
            return jsonify({'error': 'Chauffeur introuvable'}), 404

        return jsonify({'driver': driver_row_to_api(driver)}), 200

    except Exception as e:
        logger.exception(f"Error fetching driver profile (driver_id={driver_id}): {e}")
        return jsonify({'error': 'Erreur interne'}), 500
