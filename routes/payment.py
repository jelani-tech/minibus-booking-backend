

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from application.api_serializers import payment_row_to_api
from infrastructure.supabase_write_repositories import (
    SupabaseBookingRepository,
    SupabasePaymentRepository,
)
from models.public import db
from services.paystack_service import PaystackService
from loguru import logger


payment_bp = Blueprint('payment', __name__, url_prefix='/api/payments')
booking_repository = SupabaseBookingRepository()
payment_repository = SupabasePaymentRepository()


def is_mock_payment_enabled() -> bool:
    return current_app.config.get("APP_ENV") == "development" or current_app.debug


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
        if existing_payment and existing_payment['status'] in ('paid', 'completed'):
            logger.warning(f"Payment initiation rejected: payment already completed ({log_context})")
            return jsonify({'error': 'Payment already completed'}), 400


        payment_email = booking.get('customer_email')  or data.get('payment_email')

        service = PaystackService()
        payment_response = service.initialize_payment(
            amount=float(booking['total_price']) * 100,
            email=payment_email,
        )
        provider_reference = payment_response.get('reference')
        payment_url = payment_response.get('authorization_url')

        payment = payment_repository.create_or_update(
            booking_id=booking_id,
            customer_id=customer_id,
            amount=booking['total_price'],
            provider='paystack',
            provider_reference=provider_reference,
            provider_payment_url=payment_url,
            raw_provider_response=payment_response,
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
    data = request.get_json() or {}
    data = data.get('data') or {}
    reference = data.get('reference')
    status = data.get('status','pending').lower()
    logger.info(f"Payment webhook received : {reference, status}")
    try:
        if not reference:
            logger.warning("Payment webhook rejected: reference is missing")
            return jsonify({'error': 'reference is missing'}), 400

        payment = payment_repository.update_status_by_reference(
            provider_reference=reference,
            status=status,
        )
        if not payment:
            logger.exception(f"Payment webhook: no payment found for reference {reference}")
            return jsonify({'error': 'Payment not found'}), 404

        db.session.commit()

        logger.info(
            f"Payment webhook processed: reference={reference}, status='{status}', "
            f"booking_id={payment.get('booking_id')}"
        )

        return jsonify({'message': 'Webhook processed successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error processing payment webhook (reference={reference}): {e}")
        return jsonify({'error': str(e)}), 500


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

