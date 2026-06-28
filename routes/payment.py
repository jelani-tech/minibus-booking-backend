

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
            return jsonify({'error': 'booking_id is required'}), 400

        booking = booking_repository.get(booking_id)
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        if str(booking['customer_id']) != str(customer_id):
            return jsonify({'error': 'Unauthorized'}), 403
        if booking['booking_status'] != 'pending':
            return jsonify({'error': 'Booking is not pending payment'}), 400

        existing_payment = payment_repository.get_for_booking(booking_id)
        if existing_payment and existing_payment['status'] in ('paid', 'completed'):
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
    reference = data.get('reference')
    status = data.get('status','pending').lower()
    logger.info(f"Payment webhook received : {reference, status}")
    try:
        if not reference:
            return jsonify({'error': 'reference is missing'}), 400

        payment = payment_repository.update_status_by_reference(
            provider_reference=reference,
            status=status,
        )
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404

        db.session.commit()

        return jsonify({'message': 'Webhook processed successfully'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@payment_bp.route('/status/<uuid:booking_id>', methods=['GET'])
@jwt_required()
def get_payment_status(booking_id):
    try:
        customer_id = get_jwt_identity()
        booking = booking_repository.get(booking_id)

        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        if str(booking['customer_id']) != str(customer_id):
            return jsonify({'error': 'Unauthorized'}), 403

        payment = payment_repository.get_for_booking(booking_id)

        if not payment:
            return jsonify({'error': 'Payment not found'}), 404

        return jsonify({'payment': payment_row_to_api(payment)}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

