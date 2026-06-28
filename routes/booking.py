from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from application.api_serializers import booking_row_to_api
from infrastructure.supabase_write_repositories import (
    SupabaseBookingRepository,
    SupabaseCustomerRepository,
)
from models.public import db

booking_bp = Blueprint('booking', __name__, url_prefix='/api/bookings')
booking_repository = SupabaseBookingRepository()
customer_repository = SupabaseCustomerRepository()


@booking_bp.route('', methods=['POST'])
@jwt_required()
def create_booking():
    try:
        customer_id = get_jwt_identity()
        data = request.get_json() or {}

        required_fields = ['trip_id', 'number_of_seats', 'pickup_stop_id', 'dropoff_stop_id']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400


        booking = booking_repository.create(
            customer_id=customer_id,
            trip_id=data['trip_id'],
            seats_reserved=int(data['number_of_seats']),
            pickup_stop_id=data['pickup_stop_id'],
            dropoff_stop_id=data['dropoff_stop_id'],
        )
        db.session.commit()

        return jsonify({
            'message': 'Booking created successfully',
            'booking': booking_row_to_api(booking)
        }), 201

    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@booking_bp.route('', methods=['GET'])
@jwt_required()
def get_user_bookings():
    try:
        customer_id = get_jwt_identity()
        bookings = booking_repository.list_for_customer(customer_id)

        return jsonify({
            'bookings': [booking_row_to_api(booking) for booking in bookings]
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@booking_bp.route('/ticket/<ticket_reference>', methods=['GET'])
def get_booking_by_ticket_reference(ticket_reference):
    try:
        booking = booking_repository.get_by_reference(ticket_reference)

        if not booking:
            return jsonify({'error': 'Ticket not found'}), 404

        return jsonify({'booking': booking_row_to_api(booking)}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@booking_bp.route('/<uuid:booking_id>', methods=['GET'])
@jwt_required()
def get_booking(booking_id):
    try:
        customer_id = get_jwt_identity()
        booking = booking_repository.get(booking_id)

        if not booking:
            return jsonify({'error': 'Booking not found'}), 404

        if str(booking['customer_id']) != str(customer_id):
            return jsonify({'error': 'Unauthorized'}), 403

        return jsonify({'booking': booking_row_to_api(booking)}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@booking_bp.route('/<uuid:booking_id>', methods=['DELETE'])
@jwt_required()
def cancel_booking(booking_id):
    try:
        customer_id = get_jwt_identity()
        booking = booking_repository.cancel(booking_id, customer_id)
        db.session.commit()

        return jsonify({
            'message': 'Booking cancelled successfully',
            'booking': booking_row_to_api(booking)
        }), 200

    except PermissionError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 403
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
