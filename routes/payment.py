

import hashlib
import hmac
import json
import re
import unicodedata

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from application.api_serializers import payment_row_to_api
from infrastructure.supabase_write_repositories import (
    REFUND_STATUSES,
    SETTLED_SUCCESS_STATUSES,
    SupabaseBookingRepository,
    SupabasePaymentRepository,
)
from models.public import db
from services.jeko_service import (
    JEKO_PAYMENT_METHODS,
    JekoService,
    normalize_jeko_status,
)
from services.paystack_service import PaystackService
from loguru import logger
from uuid import uuid4


payment_bp = Blueprint('payment', __name__, url_prefix='/api/payments')
booking_repository = SupabaseBookingRepository()
payment_repository = SupabasePaymentRepository()


# Statuts canoniques de payments.status, contrat avec l'app mobile
# (comparaison en minuscules cote mobile).
PAYMENT_STATUS_SUCCESS = 'success'
PAYMENT_STATUS_FAILED = 'failed'
PAYMENT_STATUS_PENDING = 'pending'

# Vocabulaire normalise des statuts provider consommes par
# settle_payment_from_provider : Paystack les renvoie tels quels (webhook et
# Verify API) ; ceux de JEKO sont normalises en amont via normalize_jeko_status.
PROVIDER_SUCCESS_STATUSES = ('success',)
PROVIDER_FAILURE_STATUSES = ('failed', 'abandoned')


def settle_payment_from_provider(reference, provider_data, source):
    """Applique un resultat Paystack (webhook ou Verify) au paiement et au booking.

    Regles communes aux deux canaux, qui peuvent arriver dans n'importe quel ordre :
    - idempotent : une livraison en double ne change rien apres le premier traitement ;
    - un paiement deja en succes n'est jamais retrograde ;
    - le montant et la devise sont verifies avant de confirmer (Paystack exprime
      le montant en sous-unite, cf. le x100 fait a l'initiate) ;
    - paiement + booking mis a jour dans une meme transaction DB.

    Retourne le statut final du paiement, ou None si la reference est inconnue.
    """
    payment = payment_repository.get_by_reference(reference, for_update=True)
    if not payment:
        logger.warning(
            f"Payment settlement ({source}): unknown reference '{reference}', nothing to update"
        )
        return None

    provider_status = (provider_data.get('status') or '').lower()
    if provider_status in PROVIDER_SUCCESS_STATUSES:
        target_status = PAYMENT_STATUS_SUCCESS
    elif provider_status in PROVIDER_FAILURE_STATUSES:
        target_status = PAYMENT_STATUS_FAILED
    else:
        logger.info(
            f"Payment settlement ({source}): non-final provider status '{provider_status}' "
            f"for reference '{reference}', ignored"
        )
        return payment['status']

    current_status = (payment.get('status') or '').lower()
    if current_status in REFUND_STATUSES:
        # Une redelivrance d'evenement de PAIEMENT ne doit jamais ecraser un
        # etat de remboursement (ni son raw_provider_response, qui contient les
        # details du refund).
        logger.info(
            f"Payment settlement ({source}): reference '{reference}' is in refund state "
            f"'{current_status}', delivery ignored"
        )
        return current_status
    if current_status in SETTLED_SUCCESS_STATUSES:
        logger.info(
            f"Payment settlement ({source}): reference '{reference}' already settled as success, "
            f"'{provider_status}' delivery ignored"
        )
        return current_status
    if current_status == target_status:
        logger.info(
            f"Payment settlement ({source}): reference '{reference}' already '{target_status}', "
            "duplicate delivery ignored"
        )
        return current_status

    if target_status == PAYMENT_STATUS_SUCCESS:
        expected_amount = int(round(float(payment['amount']) * 100))
        expected_currency = (payment.get('currency') or 'XOF').upper()
        received_amount = provider_data.get('amount')
        received_currency = (provider_data.get('currency') or '').upper()
        if received_amount != expected_amount or received_currency != expected_currency:
            logger.error(
                f"Payment settlement ({source}): amount mismatch for reference '{reference}' "
                f"(expected {expected_amount} {expected_currency}, "
                f"received {received_amount} {received_currency}), payment NOT confirmed"
            )
            return current_status

    _, booking_updated = payment_repository.settle_by_reference(
        provider_reference=reference,
        payment_status=target_status,
        raw_provider_response=provider_data,
    )
    db.session.commit()
    if not booking_updated and target_status == PAYMENT_STATUS_SUCCESS:
        logger.error(
            f"Payment settlement ({source}): reference '{reference}' settled as success but "
            f"booking {payment.get('booking_id')} is no longer pending — manual refund may be required"
        )
    logger.info(
        f"Payment settlement ({source}): reference '{reference}' settled as '{target_status}' "
        f"(booking_id={payment.get('booking_id')}, booking_updated={booking_updated})"
    )
    return target_status


REFUND_REFERENCE_PREFIX = 'RF-'


def settle_refund_from_provider(reference, provider_data, source):
    """Applique le resultat d'un virement de remboursement JEKO (webhook
    transaction.completed avec transactionType=transfer).

    La reference du virement est deterministe : RF-{reference du paiement}.
    Regles :
    - un paiement deja 'refunded' n'est jamais retrograde ;
    - 'refund_required' + success tardif -> upgrade vers 'refunded' (reprise
      manuelle reussie) ;
    - un statut encore 'success' est accepte (le webhook a gagne la course
      contre mark_refund : le prefixe RF- prouve que le virement vient de nous) ;
    - montant verifie avant de confirmer, mismatch -> refund_required (manuel).

    Retourne le statut final du paiement, ou None si la reference est inconnue.
    """
    if not reference.startswith(REFUND_REFERENCE_PREFIX):
        logger.warning(
            f"Refund settlement ({source}): transfer reference '{reference}' does not "
            f"match the {REFUND_REFERENCE_PREFIX} pattern, ignored"
        )
        return None

    original_reference = reference[len(REFUND_REFERENCE_PREFIX):]
    payment = payment_repository.get_by_reference(original_reference, for_update=True)
    if not payment:
        logger.warning(
            f"Refund settlement ({source}): unknown payment reference "
            f"'{original_reference}', nothing to update"
        )
        return None

    provider_status = (provider_data.get('status') or '').lower()
    if provider_status in PROVIDER_SUCCESS_STATUSES:
        target_status = 'refunded'
    elif provider_status in PROVIDER_FAILURE_STATUSES:
        target_status = 'refund_required'
    else:
        logger.info(
            f"Refund settlement ({source}): non-final transfer status '{provider_status}' "
            f"for reference '{reference}', ignored"
        )
        return payment['status']

    current_status = (payment.get('status') or '').lower()
    if current_status == 'refunded':
        logger.info(
            f"Refund settlement ({source}): reference '{original_reference}' already "
            f"refunded, '{provider_status}' delivery ignored"
        )
        return current_status
    if current_status == target_status:
        logger.info(
            f"Refund settlement ({source}): reference '{original_reference}' already "
            f"'{target_status}', duplicate delivery ignored"
        )
        return current_status

    if target_status == 'refunded':
        expected_amount = int(round(float(payment['amount']) * 100))
        received_amount = provider_data.get('amount')
        if received_amount is not None and received_amount != expected_amount:
            logger.error(
                f"Refund settlement ({source}): amount mismatch for reference "
                f"'{original_reference}' (expected {expected_amount}, received "
                f"{received_amount}), flagged for manual review"
            )
            target_status = 'refund_required'

    _, booking_updated = payment_repository.settle_refund_by_reference(
        original_reference, target_status, provider_data
    )
    db.session.commit()
    if target_status == 'refund_required':
        logger.error(
            f"Refund settlement ({source}): reference '{original_reference}' requires "
            f"MANUAL processing (booking_id={payment.get('booking_id')})"
        )
    logger.info(
        f"Refund settlement ({source}): reference '{original_reference}' settled as "
        f"'{target_status}' (booking_id={payment.get('booking_id')}, "
        f"booking_updated={booking_updated})"
    )
    return target_status


def is_mock_payment_enabled() -> bool:
    return current_app.config.get("APP_ENV") == "development" or current_app.debug


PLACEHOLDER_PAYMENT_EMAIL = 'email@email.com'


def build_fallback_payment_email(customer_id) -> str:
    """Adresse technique stable par utilisateur (un client Paystack unique par compte sans email)."""
    local_part = unicodedata.normalize('NFKD', str(customer_id))
    local_part = local_part.encode('ascii', 'ignore').decode('ascii').lower()
    local_part = re.sub(r'[^a-z0-9._-]+', '-', local_part).strip('-.')
    return f"client-{local_part}@{current_app.config['PAYMENT_EMAIL_DOMAIN']}"


def resolve_payment_email(booking, requested_email, customer_id) -> str:
    """Email transmis a Paystack : compte client, sinon payment_email de la requete, sinon adresse technique."""
    account_email = booking.get('customer_email')
    if account_email == PLACEHOLDER_PAYMENT_EMAIL:
        account_email = None
    if requested_email == PLACEHOLDER_PAYMENT_EMAIL:
        requested_email = None
    return account_email or requested_email or build_fallback_payment_email(customer_id)


def _initiate_paystack(booking, payment_email):
    """Initie un paiement Paystack. Retourne (reference, payment_url, raw_response)."""
    payment_response = PaystackService().initialize_payment(
        amount=float(booking['total_price']) * 100,
        email=payment_email,
    )
    return (
        payment_response.get('reference'),
        payment_response.get('authorization_url'),
        payment_response,
    )


def _initiate_jeko(booking, payment_method):
    """Initie un paiement JEKO. Retourne (reference, payment_url, raw_response).

    La reference est generee par nous (exigence JEKO), nouvelle a chaque
    tentative pour ne jamais declencher le 409 duplicate-reference. L'id de
    payment request JEKO (seule cle de verification acceptee par leur API) est
    conserve dans raw_provider_response['provider_payment_id'].
    """
    reference = f"JEKO-{uuid4().hex.upper()}"
    deeplink = current_app.config.get('BOOKING_DEEPLINK_CALLBACK') or ''
    if deeplink:
        # Retour de checkout directement dans l'app mobile, sans page web
        # intermédiaire. L'app déclenche alors elle-même la vérification via
        # GET /api/payments/callback puis polle le statut : booking_id lui evite
        # d'avoir a retrouver la reservation depuis la reference.
        separator = '&' if '?' in deeplink else '?'
        callback_url = (
            f"{deeplink}{separator}provider=jeko&reference={reference}"
            f"&booking_id={booking['booking_id']}"
        )
    else:
        base_url = current_app.config.get('PAYMENT_PUBLIC_BASE_URL') or ''
        callback_url = f"{base_url}/api/payments/callback?provider=jeko&reference={reference}"
    payment_response = JekoService().initialize_payment(
        amount_cents=int(round(float(booking['total_price']) * 100)),
        reference=reference,
        payment_method=payment_method,
        success_url=callback_url,
        error_url=callback_url,
    )
    return reference, payment_response.get('payment_url'), payment_response


@payment_bp.route('/initiate', methods=['POST'])
@jwt_required()
def initiate_payment():
    data = request.get_json() or {}
    customer_id = get_jwt_identity()
    booking_id = data.get('booking_id')
    log_context = {'customer_id':customer_id, 'booking_id':booking_id}
    logger.info(f"Initiating payment : {log_context}")

    try:
        if not booking_id:
            logger.warning(f"Payment initiation rejected: booking_id missing (customer_id={customer_id})")
            return jsonify({'error': 'booking_id is required'}), 400

        booking = booking_repository.get(booking_id)
        if not booking:
            logger.warning(f"Payment initiation rejected: booking not found ({log_context})")
            return jsonify({'error': 'Booking not found'}), 404
        if str(booking['customer_id']) != str(customer_id):
            logger.warning(
                f"Payment initiation denied: customer_id={customer_id} does not own booking_id={booking_id}"
            )
            return jsonify({'error': 'Unauthorized'}), 403
        if booking['booking_status'] != 'pending':
            logger.warning(
                f"Payment initiation rejected: booking_id={booking_id} status is "
                f"'{booking['booking_status']}', not 'pending'"
            )
            return jsonify({'error': 'Booking is not pending payment'}), 400

        existing_payment = payment_repository.get_for_booking(booking_id)
        if existing_payment and existing_payment['status'] in SETTLED_SUCCESS_STATUSES:
            logger.warning(f"Payment initiation rejected: payment already completed ({log_context})")
            return jsonify({'error': 'Payment already completed'}), 400


        provider_name = (current_app.config.get('PAYMENT_PROVIDER') or 'paystack').lower()
        if provider_name == 'jeko':
            payment_method = (data.get('payment_method') or '').lower()
            if payment_method not in JEKO_PAYMENT_METHODS:
                logger.warning(
                    f"Payment initiation rejected: invalid payment_method "
                    f"'{payment_method}' ({log_context})"
                )
                return jsonify({
                    'error': 'payment_method is required and must be one of: '
                             + ', '.join(JEKO_PAYMENT_METHODS)
                }), 400
            provider_reference, payment_url, raw_response = _initiate_jeko(
                booking, payment_method
            )
        else:
            payment_email = resolve_payment_email(booking, data.get('payment_email'), customer_id)
            provider_reference, payment_url, raw_response = _initiate_paystack(
                booking, payment_email
            )

        payment = payment_repository.create_or_update(
            booking_id=booking_id,
            customer_id=customer_id,
            amount=booking['total_price'],
            provider=provider_name,
            provider_reference=provider_reference,
            provider_payment_url=payment_url,
            raw_provider_response=raw_response,
        )
        db.session.commit()

        logger.info(f'Payment initiated successfully:{log_context}')

        return jsonify({
            'message': 'Payment initiated successfully',
            'payment': payment_row_to_api(payment),
            'payment_url': payment.get('provider_payment_url'),
            'transaction_id': payment.get('provider_reference')
        }), 200

    except Exception as e:
        logger.error(f"Payment failed : {log_context} , error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@payment_bp.route('/webhook', methods=['POST'])
def payment_webhook():
    """Webhook Paystack (public, authentifie par signature HMAC).

    La signature est un HMAC-SHA512 du corps brut avec la cle secrete Paystack,
    transmis dans le header x-paystack-signature. Tout evenement signe recoit un
    200 (y compris reference inconnue ou doublon), sinon Paystack re-essaie en
    boucle.
    """
    raw_body = request.get_data()
    secret_key = current_app.config.get('PAYSTACK_SECRET_KEY') or ''
    signature = request.headers.get('x-paystack-signature') or ''

    if not secret_key:
        logger.error("Payment webhook rejected: PAYSTACK_SECRET_KEY is not configured")
        return jsonify({'error': 'Webhook not configured'}), 401

    expected_signature = hmac.new(
        secret_key.encode('utf-8'), raw_body, hashlib.sha512
    ).hexdigest()
    if not signature or not hmac.compare_digest(expected_signature, signature):
        logger.warning("Payment webhook rejected: missing or invalid x-paystack-signature")
        return jsonify({'error': 'Invalid signature'}), 401

    try:
        payload = json.loads(raw_body) if raw_body else {}
    except ValueError:
        logger.warning("Payment webhook rejected: body is not valid JSON")
        return jsonify({'error': 'Invalid payload'}), 400
    if not isinstance(payload, dict):
        payload = {}

    event = payload.get('event') or ''
    data = payload.get('data') or {}
    reference = data.get('reference')
    status = (data.get('status') or 'pending').lower()
    logger.info(f"Payment webhook received : event={event}, reference={reference}, status={status}")

    try:
        if not reference:
            logger.info(f"Payment webhook ignored: no reference (event={event})")
            return jsonify({'message': 'Event ignored'}), 200

        settle_payment_from_provider(reference, data, source='webhook')
        return jsonify({'message': 'Webhook processed successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error processing payment webhook (reference={reference}): {e}")
        return jsonify({'error': str(e)}), 500


@payment_bp.route('/jeko/webhook', methods=['POST'])
def jeko_payment_webhook():
    """Webhook JEKO (public, authentifie par signature HMAC).

    La signature est un HMAC-SHA256 du corps brut avec le secret webhook JEKO,
    transmis dans le header Jeko-Signature. Evenement unique
    transaction.completed ; la reference (generee par nous a l'initiation) est
    dans transactionDetails.reference et le montant en sous-unites dans
    amount.amount. Tout evenement signe recoit un 200 (y compris reference
    inconnue ou doublon). Reste actif meme si PAYMENT_PROVIDER=paystack, pour
    regler les paiements JEKO en cours.
    """
    raw_body = request.get_data()
    secret_key = current_app.config.get('JEKO_WEBHOOK_SECRET') or ''
    signature = request.headers.get('Jeko-Signature') or ''

    if not secret_key:
        logger.error("JEKO webhook rejected: JEKO_WEBHOOK_SECRET is not configured")
        return jsonify({'error': 'Webhook not configured'}), 401

    expected_signature = hmac.new(
        secret_key.encode('utf-8'), raw_body, hashlib.sha256
    ).hexdigest()
    if not signature or not hmac.compare_digest(expected_signature, signature):
        logger.warning("JEKO webhook rejected: missing or invalid Jeko-Signature")
        return jsonify({'error': 'Invalid signature'}), 401

    try:
        payload = json.loads(raw_body) if raw_body else {}
    except ValueError:
        logger.warning("JEKO webhook rejected: body is not valid JSON")
        return jsonify({'error': 'Invalid payload'}), 400
    if not isinstance(payload, dict):
        payload = {}

    details = payload.get('transactionDetails') or {}
    reference = details.get('reference')
    status = normalize_jeko_status(payload.get('status'))
    transaction_type = (payload.get('transactionType') or 'payment').lower()
    logger.info(
        f"JEKO webhook received : type={transaction_type}, reference={reference}, status={status}"
    )

    try:
        if not reference:
            logger.info("JEKO webhook ignored: no reference")
            return jsonify({'message': 'Event ignored'}), 200

        amount = payload.get('amount') or {}
        normalized = {
            'status': status,
            'amount': int(amount['amount']) if amount.get('amount') is not None else None,
            'currency': amount.get('currency'),
            'reference': reference,
            'raw': payload,
        }
        if transaction_type == 'transfer':
            # Virement sortant = remboursement d'annulation (reference RF-...).
            settle_refund_from_provider(reference, normalized, source='jeko-webhook')
        else:
            settle_payment_from_provider(reference, normalized, source='jeko-webhook')
        return jsonify({'message': 'Webhook processed successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error processing JEKO webhook (reference={reference}): {e}")
        return jsonify({'error': str(e)}), 500


# Page renvoyee au navigateur/WebView apres redirection Paystack ou JEKO. L'app mobile
# detecte la fin du checkout par le chemin /api/payments/callback puis polle le
# statut : le contenu de cette page n'est affiche que brievement.
CALLBACK_HTML = (
    '<!doctype html>'
    '<html lang="fr"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    '<title>JELANI - Paiement</title></head>'
    '<body style="font-family: sans-serif; text-align: center; padding: 48px 16px;">'
    '<p>Votre r&eacute;servation est valid&eacute;e, vous pouvez fermer cette fen&ecirc;tre.</p>'
    '</body></html>'
)


def _verify_and_settle_jeko_callback(reference):
    """Verifie un paiement JEKO au retour du checkout et le regle si necessaire.

    L'API JEKO ne permet la verification que par id de payment request,
    conserve dans raw_provider_response a l'initiation. Une fois le paiement
    regle (par le webhook, qui ecrase raw_provider_response), la verification
    est inutile : on rend simplement la page.
    """
    payment = payment_repository.get_by_reference(reference)
    if not payment:
        logger.warning(f"JEKO callback: unknown reference '{reference}', nothing to verify")
        return
    if (payment.get('status') or '').lower() != PAYMENT_STATUS_PENDING:
        logger.info(
            f"JEKO callback: reference '{reference}' already settled "
            f"as '{payment.get('status')}', skipping verification"
        )
        return
    payment_id = (payment.get('raw_provider_response') or {}).get('provider_payment_id')
    if not payment_id:
        logger.error(
            f"JEKO callback: no provider_payment_id stored for reference "
            f"'{reference}', cannot verify"
        )
        return
    verification = JekoService().verify_payment(payment_id)
    settle_payment_from_provider(reference, verification, source='callback')


@payment_bp.route('/callback', methods=['GET'])
def payment_callback():
    """Redirection navigateur apres le checkout Paystack ou JEKO.

    Paystack : callback URL du dashboard (?trxref=...&reference=...).
    JEKO : successUrl/errorUrl construites a l'initiation
    (?provider=jeko&reference=...).

    Les query params viennent du client : ils ne font pas foi. Le resultat est
    confirme via l'API de verification du provider, puis applique avec les memes
    regles que le webhook. Repond toujours 200.
    """
    reference = request.args.get('reference') or request.args.get('trxref')
    provider = (request.args.get('provider') or 'paystack').lower()
    logger.info(f"Payment callback received (provider={provider}, reference={reference})")
    try:
        if not reference:
            logger.warning("Payment callback without reference, nothing to verify")
        elif provider == 'jeko':
            _verify_and_settle_jeko_callback(reference)
        else:
            verification = PaystackService().verify_payment(reference)
            settle_payment_from_provider(reference, verification, source='callback')
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error processing payment callback (reference={reference}): {e}")

    return CALLBACK_HTML, 200, {'Content-Type': 'text/html; charset=utf-8'}


@payment_bp.route('/status/<uuid:booking_id>', methods=['GET'])
@jwt_required()
def get_payment_status(booking_id):
    customer_id = get_jwt_identity()
    try:
        booking = booking_repository.get(booking_id)

        if not booking:
            logger.warning(f"Payment status check: booking_id={booking_id} not found")
            return jsonify({'error': 'Booking not found'}), 404
        if str(booking['customer_id']) != str(customer_id):
            logger.warning(
                f"Payment status check denied: customer_id={customer_id} does not own booking_id={booking_id}"
            )
            return jsonify({'error': 'Unauthorized'}), 403

        payment = payment_repository.get_for_booking(booking_id)

        if not payment:
            logger.warning(f"Payment status check: no payment found for booking_id={booking_id}")
            return jsonify({'error': 'Payment not found'}), 404

        return jsonify({'payment': payment_row_to_api(payment)}), 200

    except Exception as e:
        logger.exception(f"Error fetching payment status for booking_id={booking_id}: {e}")
        return jsonify({'error': str(e)}), 500

