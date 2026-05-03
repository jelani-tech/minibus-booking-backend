from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from application.api_serializers import payment_row_to_api
from infrastructure.supabase_write_repositories import (
    SupabaseBookingRepository,
    SupabasePaymentRepository,
)
from models.public import db
from services.mtn_momo import MTNMomoService
from services.orange_money import OrangeMoneyService
from services.wave_payment import WavePaymentService

payment_bp = Blueprint('payment', __name__, url_prefix='/api/payments')
booking_repository = SupabaseBookingRepository()
payment_repository = SupabasePaymentRepository()


def is_mock_payment_enabled() -> bool:
    return current_app.config.get("APP_ENV") == "development" or current_app.debug


@payment_bp.route('/initiate', methods=['POST'])
@jwt_required()
def initiate_payment():
    try:
        customer_id = get_jwt_identity()
        data = request.get_json() or {}

        if not data.get('booking_id') or not data.get('payment_method'):
            return jsonify({'error': 'booking_id and payment_method are required'}), 400

        booking = booking_repository.get(data['booking_id'])
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        if str(booking['customer_id']) != str(customer_id):
            return jsonify({'error': 'Unauthorized'}), 403
        if booking['booking_status'] != 'pending':
            return jsonify({'error': 'Booking is not pending payment'}), 400

        payment_method = data['payment_method'].lower()
        existing_payment = payment_repository.get_for_booking(data['booking_id'])
        if existing_payment and existing_payment['status'] in ('paid', 'completed'):
            return jsonify({'error': 'Payment already completed'}), 400

        provider_reference = f"JELANI-{uuid4()}"
        payment_url = None
        payment_response = {
            "transaction_id": provider_reference,
            "status": "pending",
            "mock": True,
        }

        if not is_mock_payment_enabled():
            if payment_method == 'wave':
                service = WavePaymentService()
            elif payment_method == 'orange_money':
                service = OrangeMoneyService()
            elif payment_method == 'mtn_momo':
                service = MTNMomoService()
            else:
                return jsonify({'error': 'Invalid payment method'}), 400

            payment_response = service.initiate_payment(
                amount=booking['total_price'],
                phone=data.get('phone') or booking['customer_phone'],
                transaction_id=provider_reference,
            )
            provider_reference = payment_response.get('transaction_id') or provider_reference
            payment_url = payment_response.get('payment_url')

        payment = payment_repository.create_or_update(
            booking_id=data['booking_id'],
            customer_id=customer_id,
            amount=booking['total_price'],
            provider=payment_method,
            provider_reference=provider_reference,
            provider_payment_url=payment_url,
            raw_provider_response=payment_response,
        )
        db.session.commit()

        return jsonify({
            'message': 'Payment initiated successfully',
            'payment': payment_row_to_api(payment),
            'payment_url': payment.get('provider_payment_url'),
            'transaction_id': payment.get('provider_reference')
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@payment_bp.route('/webhook', methods=['POST'])
def payment_webhook():
    try:
        data = request.get_json() or {}
        transaction_id = data.get('transaction_id') or data.get('provider_reference')

        if not transaction_id:
            return jsonify({'error': 'transaction_id is required'}), 400

        payment = payment_repository.update_status_by_reference(
            provider_reference=transaction_id,
            status=data.get('status', 'pending').lower(),
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

