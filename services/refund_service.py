from loguru import logger

from infrastructure.supabase_write_repositories import SETTLED_SUCCESS_STATUSES
from models.public import db
from services.jeko_service import JekoDuplicateReferenceError, JekoService


# Montant minimum d'un virement JEKO (en sous-unités).
JEKO_TRANSFER_MIN_CENTS = 500


def _payer_from_raw(raw):
    """Extrait (téléphone, opérateur) du payeur depuis un fragment de réponse JEKO.

    Deux formes possibles selon le canal qui a réglé le paiement :
    - payload webhook : counterpartIdentifier / paymentMethod au niveau racine ;
    - réponse verify : paymentMethod au niveau racine, counterpartIdentifier
      dans l'objet transaction.
    """
    if not isinstance(raw, dict):
        return None, None
    transaction = raw.get('transaction') or {}
    phone = raw.get('counterpartIdentifier') or transaction.get('counterpartIdentifier')
    method = raw.get('paymentMethod') or transaction.get('paymentMethod')
    return phone, method


def _extract_jeko_payer(payment):
    """(téléphone, opérateur) du payeur, depuis les données stockées du paiement,
    avec re-fetch de la payment request JEKO en dernier recours."""
    stored = payment.get('raw_provider_response') or {}
    raw = stored.get('raw') if isinstance(stored.get('raw'), dict) else stored

    phone, method = _payer_from_raw(raw)
    if not phone or not method:
        phone, method = _payer_from_raw(stored)

    if not phone or not method:
        payment_request_id = (
            stored.get('provider_payment_id')
            or (raw.get('transactionDetails') or {}).get('id')
            or raw.get('id')
        )
        if payment_request_id:
            try:
                verification = JekoService().verify_payment(payment_request_id)
                phone, method = _payer_from_raw(verification.get('raw') or {})
            except Exception as e:
                logger.warning(
                    f"Refund: JEKO payer re-fetch failed "
                    f"(payment_request_id={payment_request_id}): {e}"
                )
    return phone, method


def _mark_manual_refund(payment_repository, payment, reason, extra=None):
    refund_data = {'reason': reason}
    if extra:
        refund_data.update(extra)
    payment_repository.mark_refund(payment['id'], 'refund_required', refund_data)
    db.session.commit()
    logger.error(
        f"Refund requires MANUAL processing (reason={reason}, "
        f"payment_id={payment['id']}, booking_id={payment.get('booking_id')}, "
        f"provider={payment.get('provider')}, amount={payment.get('amount')})"
    )
    return {'status': 'manual', 'reason': reason}


def process_refund_for_cancellation(booking, payment_repository):
    """Rembourse (si nécessaire) le paiement d'une réservation qui vient d'être
    annulée. Appelé APRÈS le commit de l'annulation ; fait ses propres commits
    et ne raise jamais : un échec de remboursement ne doit pas dé-annuler.

    Retourne un dict pour la réponse API :
    {'status': 'none'|'initiated'|'completed'|'manual', ...}
    """
    booking_id = booking['booking_id']
    try:
        payment = payment_repository.get_for_booking(booking_id)
        if not payment or (payment.get('status') or '').lower() not in SETTLED_SUCCESS_STATUSES:
            return {'status': 'none'}

        provider = (payment.get('provider') or '').lower()
        if provider != 'jeko':
            return _mark_manual_refund(
                payment_repository, payment, f'{provider or "unknown"}_manual_refund'
            )

        phone, method = _extract_jeko_payer(payment)
        if not phone or not method:
            return _mark_manual_refund(payment_repository, payment, 'payer_unrecoverable')

        amount_cents = int(round(float(payment['amount']) * 100))
        if amount_cents < JEKO_TRANSFER_MIN_CENTS:
            return _mark_manual_refund(
                payment_repository, payment, 'amount_below_transfer_minimum'
            )

        refund_reference = f"RF-{payment['provider_reference']}"
        service = JekoService()
        try:
            contact_id = service.create_beneficiary_contact(
                name=booking.get('customer_full_name') or phone,
                payment_method=method,
                identifier=phone,
            )
            transfer = service.create_transfer(
                amount_cents=amount_cents,
                contact_id=contact_id,
                reference=refund_reference,
                description=(
                    f"Remboursement annulation {booking.get('external_reference') or booking_id}"
                )[:255],
            )
        except JekoDuplicateReferenceError:
            # Virement déjà initié (double annulation / retry) : pas de double
            # paiement, on (re)pose l'état d'attente.
            payment_repository.mark_refund(
                payment['id'], 'refund_pending', {'reference': refund_reference}
            )
            db.session.commit()
            return {'status': 'initiated', 'reference': refund_reference}
        except Exception as e:
            return _mark_manual_refund(
                payment_repository, payment, 'transfer_creation_failed',
                {'error': str(e), 'reference': refund_reference},
            )

        if transfer['status'] == 'success':
            payment_repository.settle_refund_by_reference(
                payment['provider_reference'], 'refunded', transfer['raw']
            )
            db.session.commit()
            logger.info(
                f"Refund completed synchronously (booking_id={booking_id}, "
                f"reference={refund_reference})"
            )
            return {'status': 'completed', 'reference': refund_reference}

        if transfer['status'] == 'failed':
            return _mark_manual_refund(
                payment_repository, payment, 'transfer_failed',
                {'transfer_id': transfer.get('transfer_id'), 'reference': refund_reference},
            )

        payment_repository.mark_refund(
            payment['id'], 'refund_pending',
            {
                'reference': refund_reference,
                'transfer_id': transfer.get('transfer_id'),
                'contact_id': contact_id,
                'payer': {'identifier': phone, 'payment_method': method},
            },
        )
        db.session.commit()
        logger.info(
            f"Refund initiated (booking_id={booking_id}, reference={refund_reference}, "
            f"transfer_id={transfer.get('transfer_id')})"
        )
        return {'status': 'initiated', 'reference': refund_reference}

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Refund processing error (booking_id={booking_id}): {e}")
        try:
            payment = payment_repository.get_for_booking(booking_id)
            if payment and (payment.get('status') or '').lower() in SETTLED_SUCCESS_STATUSES:
                payment_repository.mark_refund(
                    payment['id'], 'refund_required',
                    {'reason': 'refund_processing_error', 'error': str(e)},
                )
                db.session.commit()
        except Exception:
            db.session.rollback()
        return {'status': 'manual', 'reason': 'refund_processing_error'}
