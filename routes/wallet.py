"""Routes du porte-monnaie client (§ 6 de la spec wallet).

Toutes les routes sont sous @jwt_required() et opèrent exclusivement sur le
wallet de get_jwt_identity() : aucun wallet_id, customer_id ou balance n'est
jamais accepté depuis le corps de requête.

Les montants exposés sont des francs entiers, exactement ceux qui sont stockés.
Le ×100 attendu par JEKO et Paystack reste confiné à l'appel provider.
"""

import hashlib
import re
from datetime import datetime
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from loguru import logger

from application.api_serializers import (
    topup_row_to_api,
    wallet_entry_row_to_api,
    wallet_row_to_api,
)
from infrastructure.supabase_write_repositories import (
    TOPUP_REFERENCE_PREFIX,
    SupabaseCustomerRepository,
    SupabaseWalletRepository,
    WalletFrozenError,
)
from models.public import db
from routes.payment import PLACEHOLDER_PAYMENT_EMAIL, build_fallback_payment_email
from services.jeko_service import JEKO_PAYMENT_METHODS, JekoService
from services.paystack_service import PaystackService


wallet_bp = Blueprint('wallet', __name__, url_prefix='/api/wallet')
wallet_repository = SupabaseWalletRepository()
customer_repository = SupabaseCustomerRepository()


TRANSACTIONS_DEFAULT_LIMIT = 20
TRANSACTIONS_MAX_LIMIT = 100
TOPUPS_DEFAULT_LIMIT = 20
TOPUPS_MAX_LIMIT = 100


def error_response(code, message, status, **extra):
    """Réponse d'erreur avec un `code` stable, pour que l'app mobile n'ait
    jamais à interpréter du texte (§ 10)."""
    payload = {'error': message, 'code': code}
    payload.update(extra)
    return jsonify(payload), status


@wallet_bp.before_request
def require_wallet_enabled():
    """Interrupteur maître du déploiement progressif : tant qu'il est à false,
    aucune route wallet n'est exposée (§ 12, étape 1).

    Le préflight CORS passe outre : le bloquer ferait échouer la requête du
    navigateur avant qu'il ne puisse lire le 404.
    """
    if request.method == 'OPTIONS':
        return None
    if not current_app.config.get('WALLET_ENABLED'):
        return error_response('WALLET_DISABLED', 'Wallet is not available', 404)
    return None


def parse_xof_amount(value):
    """Montant en francs entiers, ou None si la valeur n'en est pas un.

    Les bool sont des int en Python : ils sont rejetés explicitement. Un float
    n'est accepté que s'il est entier (le XOF n'a pas de subdivision).
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def normalize_cursor(raw):
    """Valide le curseur de pagination (created_at ISO-8601), ou None.

    Un '+' d'offset non encodé dans la query string arrive décodé en espace :
    on le rattrape plutôt que de renvoyer une erreur sur un curseur que nous
    avons nous-mêmes émis dans `next_before`.
    """
    candidates = [raw.replace('Z', '+00:00')]
    repaired = re.sub(r' (\d{2}:?\d{2})$', r'+\1', raw)
    if repaired != raw:
        candidates.append(repaired)
    for candidate in candidates:
        try:
            datetime.fromisoformat(candidate)
            return candidate
        except ValueError:
            continue
    return None


def parse_limit(raw, default, maximum):
    try:
        limit = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default
    return max(1, min(limit, maximum))


# ---------------------------------------------------------------------------
# GET /api/wallet — solde et statut
# ---------------------------------------------------------------------------

@wallet_bp.route('', methods=['GET'])
@jwt_required()
def get_wallet():
    customer_id = get_jwt_identity()
    try:
        wallet = wallet_repository.get_or_create(customer_id)
        db.session.commit()
        return jsonify({'wallet': wallet_row_to_api(wallet)}), 200
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error fetching wallet (customer_id={customer_id}): {e}")
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# GET /api/wallet/transactions — relevé paginé
# ---------------------------------------------------------------------------

@wallet_bp.route('/transactions', methods=['GET'])
@jwt_required()
def list_transactions():
    customer_id = get_jwt_identity()
    limit = parse_limit(
        request.args.get('limit'), TRANSACTIONS_DEFAULT_LIMIT, TRANSACTIONS_MAX_LIMIT
    )
    before = request.args.get('before')
    if before:
        before = normalize_cursor(before)
        if before is None:
            return error_response(
                'INVALID_CURSOR', "'before' must be an ISO-8601 datetime", 400
            )

    try:
        wallet_repository.get_or_create(customer_id)
        db.session.commit()
        entries, has_more = wallet_repository.list_entries(
            customer_id=customer_id, limit=limit, before=before
        )
        transactions = [wallet_entry_row_to_api(entry) for entry in entries]
        return jsonify({
            'transactions': transactions,
            'next_before': transactions[-1]['created_at'] if transactions and has_more else None,
            'has_more': has_more,
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.exception(
            f"Error listing wallet transactions (customer_id={customer_id}): {e}"
        )
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# POST /api/wallet/topups — démarre un rechargement
# ---------------------------------------------------------------------------

def build_topup_reference(customer_id, idempotency_key=None):
    """Référence émise par nous, préfixée TU-.

    C'est ce préfixe qui aiguille un événement provider vers le règlement d'un
    rechargement plutôt que vers celui d'une réservation. Avec un en-tête
    Idempotency-Key, la référence en est dérivée : rejouer la même requête
    retombe sur le même rechargement au lieu d'en créer un second.
    """
    if idempotency_key:
        digest = hashlib.sha256(
            f"{customer_id}:{idempotency_key}".encode('utf-8')
        ).hexdigest()[:32]
        return f"{TOPUP_REFERENCE_PREFIX}{digest.upper()}"
    return f"{TOPUP_REFERENCE_PREFIX}{uuid4().hex.upper()}"


def topup_callback_url(provider, reference, topup_id):
    """URL de retour de checkout, construite comme celle des paiements.

    Jamais le deep link mobile : JEKO n'accepte que des URLs http(s) en
    successUrl/errorUrl. Le retour arrive donc sur /api/payments/callback, qui
    règle le mouvement puis rebondit vers BOOKING_DEEPLINK_CALLBACK.
    """
    base_url = current_app.config.get('PAYMENT_PUBLIC_BASE_URL') or ''
    return (
        f"{base_url}/api/payments/callback?provider={provider}"
        f"&reference={reference}&topup_id={topup_id}"
    )


def resolve_topup_email(customer_id):
    """Email transmis à Paystack : celui du compte, sinon adresse technique."""
    customer = customer_repository.get(customer_id) or {}
    email = customer.get('email')
    if not email or email == PLACEHOLDER_PAYMENT_EMAIL:
        email = build_fallback_payment_email(customer_id)
    return email


def initiate_topup_checkout(topup, provider, payment_method, customer_id):
    """Ouvre le checkout provider. Retourne (payment_url, raw_response)."""
    callback_url = topup_callback_url(
        provider, topup['provider_reference'], topup['id']
    )
    if provider == 'jeko':
        response = JekoService().initialize_payment(
            amount_cents=int(topup['amount']) * 100,
            reference=topup['provider_reference'],
            payment_method=payment_method,
            success_url=callback_url,
            error_url=callback_url,
        )
        return response.get('payment_url'), response

    response = PaystackService().initialize_payment(
        amount=int(topup['amount']) * 100,
        email=resolve_topup_email(customer_id),
        reference=topup['provider_reference'],
        callback_url=callback_url,
    )
    return response.get('authorization_url'), response


@wallet_bp.route('/topups', methods=['POST'])
@jwt_required()
def create_topup():
    if not current_app.config.get('WALLET_TOPUP_ENABLED'):
        return error_response('WALLET_TOPUP_DISABLED', 'Wallet top-up is not available', 404)

    data = request.get_json(silent=True) or {}
    customer_id = get_jwt_identity()
    idempotency_key = request.headers.get('Idempotency-Key')

    minimum = current_app.config['WALLET_MIN_TOPUP_XOF']
    maximum = current_app.config['WALLET_MAX_TOPUP_XOF']
    amount = parse_xof_amount(data.get('amount'))
    if amount is None or amount <= 0 or amount < minimum or amount > maximum:
        logger.warning(
            f"Top-up rejected: invalid amount {data.get('amount')!r} "
            f"(customer_id={customer_id}, bounds={minimum}-{maximum})"
        )
        return error_response(
            'INVALID_AMOUNT',
            f'amount must be an integer between {minimum} and {maximum} XOF',
            400,
            min_amount=minimum,
            max_amount=maximum,
        )

    provider = (current_app.config.get('PAYMENT_PROVIDER') or 'paystack').lower()
    payment_method = (data.get('payment_method') or '').lower() or None
    if provider == 'jeko' and payment_method not in JEKO_PAYMENT_METHODS:
        logger.warning(
            f"Top-up rejected: invalid payment_method {payment_method!r} "
            f"(customer_id={customer_id})"
        )
        return error_response(
            'INVALID_PAYMENT_METHOD',
            'payment_method is required and must be one of: '
            + ', '.join(JEKO_PAYMENT_METHODS),
            400,
        )

    try:
        rate_limit = current_app.config['WALLET_TOPUP_RATE_LIMIT']
        rate_window = current_app.config['WALLET_TOPUP_RATE_WINDOW_MINUTES']
        if wallet_repository.count_topups_since(
            customer_id=customer_id, minutes=rate_window
        ) >= rate_limit:
            logger.warning(f"Top-up rate limit reached (customer_id={customer_id})")
            return error_response(
                'TOPUP_LIMIT_REACHED',
                'Too many top-up attempts, retry in a few minutes',
                429,
            )

        wallet = wallet_repository.get_or_create(customer_id)
        db.session.commit()
        if wallet['status'] != 'active':
            return error_response('WALLET_FROZEN', 'Wallet is frozen', 409)

        # Plafonds : vérifiés AVANT d'encaisser. Une fois l'argent pris par le
        # provider, le crédit n'est plus refusable (§ 9.1).
        max_balance = current_app.config['WALLET_MAX_BALANCE_XOF']
        if int(wallet['balance']) + amount > max_balance:
            logger.warning(
                f"Top-up rejected: balance cap (customer_id={customer_id}, "
                f"balance={wallet['balance']}, amount={amount}, cap={max_balance})"
            )
            return error_response(
                'TOPUP_LIMIT_REACHED',
                f'Wallet balance cannot exceed {max_balance} XOF',
                429,
                balance=int(wallet['balance']),
                max_balance=max_balance,
            )

        daily_limit = current_app.config['WALLET_DAILY_TOPUP_LIMIT_XOF']
        credited_today = wallet_repository.sum_entries(
            customer_id=customer_id, entry_type='topup', since_hours=24
        )
        if credited_today + amount > daily_limit:
            logger.warning(
                f"Top-up rejected: daily cap (customer_id={customer_id}, "
                f"credited_today={credited_today}, amount={amount}, cap={daily_limit})"
            )
            return error_response(
                'TOPUP_LIMIT_REACHED',
                f'Daily top-up limit of {daily_limit} XOF reached',
                429,
                credited_today=credited_today,
                daily_limit=daily_limit,
            )

        # Rejeu explicite (Idempotency-Key) ou implicite (même montant, même
        # méthode, moins de N minutes) : on rend le checkout déjà ouvert plutôt
        # que d'en ouvrir un second.
        reference = build_topup_reference(customer_id, idempotency_key)
        existing = (
            wallet_repository.get_topup_by_reference(reference)
            if idempotency_key
            else wallet_repository.find_reusable_pending_topup(
                customer_id=customer_id,
                amount=amount,
                provider=provider,
                provider_method=payment_method,
                max_age_minutes=current_app.config['WALLET_TOPUP_REUSE_MINUTES'],
            )
        )
        if existing:
            if str(existing['customer_id']) != str(customer_id):
                return error_response('FORBIDDEN', 'Top-up belongs to another customer', 403)
            logger.info(
                f"Top-up reused (topup_id={existing['id']}, customer_id={customer_id}, "
                f"reference={existing['provider_reference']})"
            )
            return jsonify({
                'topup': topup_row_to_api(existing),
                'payment_url': existing.get('provider_payment_url'),
            }), 201

        topup = wallet_repository.create_topup(
            wallet_id=wallet['id'],
            customer_id=customer_id,
            amount=amount,
            provider=provider,
            provider_method=payment_method,
            provider_reference=reference,
        )
        # Le topup 'pending' est rendu durable AVANT l'appel provider : si
        # celui-ci échoue, la tentative reste tracée et sera expirée par le
        # nettoyage plutôt que de disparaître avec le rollback.
        db.session.commit()

        logger.info(
            f"Top-up created (topup_id={topup['id']}, customer_id={customer_id}, "
            f"amount={amount}, provider={provider}, reference={reference})"
        )

        try:
            payment_url, raw_response = initiate_topup_checkout(
                topup, provider, payment_method, customer_id
            )
        except Exception as e:
            db.session.rollback()
            logger.error(
                f"Top-up checkout failed (topup_id={topup['id']}, "
                f"provider={provider}): {e}"
            )
            return error_response(
                'PROVIDER_UNAVAILABLE', 'Payment provider is unavailable', 503
            )

        if not payment_url:
            logger.error(
                f"Top-up checkout returned no payment_url "
                f"(topup_id={topup['id']}, provider={provider})"
            )
            return error_response(
                'PROVIDER_UNAVAILABLE', 'Payment provider returned no checkout URL', 503
            )

        topup = wallet_repository.attach_provider_checkout(
            topup_id=topup['id'],
            provider_payment_url=payment_url,
            raw_provider_response=raw_response,
        )
        db.session.commit()

        return jsonify({
            'topup': topup_row_to_api(topup),
            'payment_url': payment_url,
        }), 201

    except WalletFrozenError as e:
        db.session.rollback()
        return error_response('WALLET_FROZEN', str(e), 409)
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error creating top-up (customer_id={customer_id}): {e}")
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# GET /api/wallet/topups — historique
# ---------------------------------------------------------------------------

@wallet_bp.route('/topups', methods=['GET'])
@jwt_required()
def list_topups():
    customer_id = get_jwt_identity()
    limit = parse_limit(request.args.get('limit'), TOPUPS_DEFAULT_LIMIT, TOPUPS_MAX_LIMIT)
    try:
        topups = wallet_repository.list_topups(customer_id=customer_id, limit=limit)
        return jsonify({'topups': [topup_row_to_api(topup) for topup in topups]}), 200
    except Exception as e:
        logger.exception(f"Error listing top-ups (customer_id={customer_id}): {e}")
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# GET /api/wallet/topups/<id> — statut d'un rechargement (polling mobile)
# ---------------------------------------------------------------------------

@wallet_bp.route('/topups/<uuid:topup_id>', methods=['GET'])
@jwt_required()
def get_topup(topup_id):
    customer_id = get_jwt_identity()
    try:
        topup = wallet_repository.get_topup(topup_id)
        if not topup:
            return error_response('NOT_FOUND', 'Top-up not found', 404)
        if str(topup['customer_id']) != str(customer_id):
            logger.warning(
                f"Top-up access denied: customer_id={customer_id} does not own "
                f"topup_id={topup_id}"
            )
            return error_response('FORBIDDEN', 'Top-up belongs to another customer', 403)

        # Le solde accompagne le statut : l'app affiche le nouveau solde sans
        # second appel après un rechargement crédité.
        wallet = wallet_repository.get_or_create(customer_id)
        db.session.commit()
        return jsonify({
            'topup': topup_row_to_api(topup),
            'wallet': {
                'balance': int(wallet['balance']),
                'currency': wallet.get('currency'),
            },
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.exception(
            f"Error fetching top-up (topup_id={topup_id}, customer_id={customer_id}): {e}"
        )
        return jsonify({'error': str(e)}), 500
