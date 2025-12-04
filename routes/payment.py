from flask import Blueprint, request, jsonify
from models import db, Payment, Booking
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.wave_payment import WavePaymentService
from services.orange_money import OrangeMoneyService
from services.mtn_momo import MTNMomoService

payment_bp = Blueprint('payment', __name__, url_prefix='/api/payments')

@payment_bp.route('/initiate', methods=['POST'])
@jwt_required()
def initiate_payment():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data.get('booking_id') or not data.get('payment_method'):
            return jsonify({'error': 'booking_id and payment_method are required'}), 400
        
        booking = Booking.query.get(data['booking_id'])
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        if booking.user_id != user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        if booking.status != 'pending':
            return jsonify({'error': 'Booking is not pending payment'}), 400
        
        payment_method = data['payment_method'].lower()
        
        # Check if payment already exists
        existing_payment = Payment.query.filter_by(booking_id=booking.id).first()
        if existing_payment and existing_payment.status == 'completed':
            return jsonify({'error': 'Payment already completed'}), 400
        
        # Initialize payment service based on method
        if payment_method == 'wave':
            service = WavePaymentService()
        elif payment_method == 'orange_money':
            service = OrangeMoneyService()
        elif payment_method == 'mtn_momo':
            service = MTNMomoService()
        else:
            return jsonify({'error': 'Invalid payment method'}), 400
        
        # Create or update payment record
        if existing_payment:
            payment = existing_payment
            payment.payment_method = payment_method
        else:
            payment = Payment(
                booking_id=booking.id,
                amount=booking.total_price,
                payment_method=payment_method,
                status='pending'
            )
            db.session.add(payment)
        
        # Initiate payment with provider
        payment_response = service.initiate_payment(
            amount=booking.total_price,
            phone=data.get('phone', booking.passenger_phone),
            transaction_id=f"MB{booking.id}{payment.id}"
        )
        
        payment.transaction_id = payment_response.get('transaction_id')
        payment.payment_provider_response = str(payment_response)
        db.session.commit()
        
        return jsonify({
            'message': 'Payment initiated successfully',
            'payment': payment.to_dict(),
            'payment_url': payment_response.get('payment_url'),
            'transaction_id': payment.transaction_id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@payment_bp.route('/webhook', methods=['POST'])
def payment_webhook():
    try:
        data = request.get_json()
        transaction_id = data.get('transaction_id')
        
        if not transaction_id:
            return jsonify({'error': 'transaction_id is required'}), 400
        
        payment = Payment.query.filter_by(transaction_id=transaction_id).first()
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        # Update payment status based on webhook data
        status = data.get('status', 'pending').lower()
        if status in ['completed', 'success', 'paid']:
            payment.status = 'completed'
            payment.booking.status = 'confirmed'
        elif status in ['failed', 'cancelled', 'error']:
            payment.status = 'failed'
        
        payment.payment_provider_response = str(data)
        db.session.commit()
        
        return jsonify({'message': 'Webhook processed successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@payment_bp.route('/status/<int:booking_id>', methods=['GET'])
@jwt_required()
def get_payment_status(booking_id):
    try:
        user_id = get_jwt_identity()
        booking = Booking.query.get(booking_id)
        
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        if booking.user_id != user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        payment = Payment.query.filter_by(booking_id=booking_id).first()
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        return jsonify({'payment': payment.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

