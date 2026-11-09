"""Décorateurs d'accès par application.

Chaque jeton porte son application (claim `aud`) : un jeton est refusé sur les
routes d'une autre application, même s'il est valide. La session (claim `sid`)
est vérifiée par le token_in_blocklist_loader enregistré dans app.py.
"""

from functools import wraps

from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt, verify_jwt_in_request

from services.auth.audiences import CUSTOMER_APP, DRIVER_APP


def app_jwt_required(audience, *, allow_pending_pin_change=False):
    """Exige un access token émis pour `audience`.

    Tant qu'un chauffeur n'a pas remplacé son PIN provisoire, seules les routes
    marquées allow_pending_pin_change lui sont ouvertes.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if request.method == 'OPTIONS':
                return current_app.ensure_sync(fn)(*args, **kwargs)

            verify_jwt_in_request()
            claims = get_jwt()

            if claims.get('aud') != audience:
                return jsonify({
                    'error': "Ce jeton n'est pas valable pour cette application",
                    'code': 'invalid_audience',
                }), 401

            if claims.get('must_change_pin') and not allow_pending_pin_change:
                return jsonify({
                    'error': 'Vous devez changer votre PIN avant de continuer',
                    'code': 'pin_change_required',
                }), 403

            return current_app.ensure_sync(fn)(*args, **kwargs)

        return wrapper

    return decorator


customer_required = app_jwt_required(CUSTOMER_APP)
driver_required = app_jwt_required(DRIVER_APP)


def current_session_id():
    return get_jwt()['sid']


def current_auth_user_id():
    return get_jwt()['uid']
