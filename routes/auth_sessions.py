"""Réponses HTTP communes aux routes refresh / logout de chaque application."""

from flask import jsonify, request
from loguru import logger

from models.public import db
from routes.guards import current_session_id
from services.auth.errors import InvalidRefreshToken
from services.auth.token_service import TokenService

token_service = TokenService()


def refresh_response(audience, refresh):
    """Exécute `refresh(refresh_token)` et traduit le résultat en réponse HTTP.

    Même en cas d'échec, la transaction est validée : une réutilisation de jeton
    détectée doit révoquer la session pour de bon.
    """
    data = request.get_json(silent=True) or {}
    refresh_token = (data.get('refresh_token') or '').strip()
    if not refresh_token:
        return jsonify({'error': 'Le champ refresh_token est obligatoire'}), 400

    try:
        tokens = refresh(refresh_token)
        db.session.commit()
        return jsonify(tokens.to_api()), 200

    except InvalidRefreshToken as error:
        db.session.commit()
        logger.warning(f"Refresh rejected ({audience}): {error.reason}")
        return jsonify({
            'error': 'Session expirée, veuillez vous reconnecter',
            'code': 'invalid_refresh_token',
        }), 401

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error during token refresh ({audience}): {e}")
        return jsonify({'error': 'Erreur interne'}), 500


def logout_response(audience):
    """Révoque la session du jeton courant (à appeler sous un guard)."""
    session_id = current_session_id()
    try:
        token_service.revoke_session(session_id, 'logout')
        db.session.commit()
        logger.info(f"Logout ({audience}, session_id={session_id})")
        return jsonify({'message': 'Déconnexion réussie'}), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error during logout ({audience}, session_id={session_id}): {e}")
        return jsonify({'error': 'Erreur interne'}), 500
