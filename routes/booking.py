from flask import Blueprint, request, jsonify
from models import db, Booking, Trip
from flask_jwt_extended import jwt_required, get_jwt_identity

booking_bp = Blueprint('booking', __name__, url_prefix='/api/bookings')

@booking_bp.route('', methods=['POST'])
@jwt_required()
def create_booking():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validation
        required_fields = ['trip_id', 'number_of_seats', 'passenger_name', 'passenger_phone']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        trip = Trip.query.get(data['trip_id'])
        if not trip:
            return jsonify({'error': 'Trip not found'}), 404
        
        if trip.status != 'active':
            return jsonify({'error': 'Trip is not available for booking'}), 400
        
        number_of_seats = int(data['number_of_seats'])
        if number_of_seats > trip.available_seats:
            return jsonify({'error': 'Not enough seats available'}), 400
        
        total_price = trip.price * number_of_seats
        
        booking = Booking(
            user_id=user_id,
            trip_id=trip.id,
            number_of_seats=number_of_seats,
            total_price=total_price,
            passenger_name=data['passenger_name'],
            passenger_phone=data['passenger_phone'],
            status='pending'
        )
        
        # Update available seats
        trip.available_seats -= number_of_seats
        
        db.session.add(booking)
        db.session.commit()
        
        return jsonify({
            'message': 'Booking created successfully',
            'booking': booking.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@booking_bp.route('', methods=['GET'])
@jwt_required()
def get_user_bookings():
    try:
        user_id = get_jwt_identity()
        bookings = Booking.query.filter_by(user_id=user_id).order_by(Booking.created_at.desc()).all()
        
        return jsonify({
            'bookings': [booking.to_dict() for booking in bookings]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@booking_bp.route('/<int:booking_id>', methods=['GET'])
@jwt_required()
def get_booking(booking_id):
    try:
        user_id = get_jwt_identity()
        booking = Booking.query.get(booking_id)
        
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        if booking.user_id != user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        return jsonify({'booking': booking.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@booking_bp.route('/<int:booking_id>', methods=['DELETE'])
@jwt_required()
def cancel_booking(booking_id):
    try:
        user_id = get_jwt_identity()
        booking = Booking.query.get(booking_id)
        
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        if booking.user_id != user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        if booking.status == 'cancelled':
            return jsonify({'error': 'Booking already cancelled'}), 400
        
        # Restore seats
        trip = booking.trip
        trip.available_seats += booking.number_of_seats
        
        booking.status = 'cancelled'
        db.session.commit()
        
        return jsonify({
            'message': 'Booking cancelled successfully',
            'booking': booking.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

