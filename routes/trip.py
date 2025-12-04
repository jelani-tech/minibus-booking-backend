from flask import Blueprint, request, jsonify
from models import db, Trip
from flask_jwt_extended import jwt_required
from datetime import datetime

trip_bp = Blueprint('trip', __name__, url_prefix='/api/trips')

@trip_bp.route('', methods=['GET'])
def get_trips():
    try:
        departure_city = request.args.get('departure_city')
        arrival_city = request.args.get('arrival_city')
        date = request.args.get('date')
        
        query = Trip.query.filter_by(status='active')
        
        if departure_city:
            query = query.filter(Trip.departure_city.ilike(f'%{departure_city}%'))
        if arrival_city:
            query = query.filter(Trip.arrival_city.ilike(f'%{arrival_city}%'))
        if date:
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d').date()
                query = query.filter(db.func.date(Trip.departure_time) == date_obj)
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        trips = query.all()
        
        return jsonify({
            'trips': [trip.to_dict() for trip in trips]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@trip_bp.route('/<int:trip_id>', methods=['GET'])
def get_trip(trip_id):
    try:
        trip = Trip.query.get(trip_id)
        
        if not trip:
            return jsonify({'error': 'Trip not found'}), 404
        
        return jsonify({'trip': trip.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@trip_bp.route('', methods=['POST'])
@jwt_required()
def create_trip():
    try:
        data = request.get_json()
        
        # Validation
        required_fields = ['departure_city', 'arrival_city', 'departure_time', 'arrival_time', 'price', 'driver_name', 'driver_phone', 'vehicle_number']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Parse datetime
        try:
            departure_time = datetime.fromisoformat(data['departure_time'].replace('Z', '+00:00'))
            arrival_time = datetime.fromisoformat(data['arrival_time'].replace('Z', '+00:00'))
        except (ValueError, KeyError):
            return jsonify({'error': 'Invalid datetime format'}), 400
        
        trip = Trip(
            departure_city=data['departure_city'],
            arrival_city=data['arrival_city'],
            departure_time=departure_time,
            arrival_time=arrival_time,
            price=float(data['price']),
            available_seats=int(data.get('available_seats', 18)),
            total_seats=int(data.get('total_seats', 18)),
            driver_name=data['driver_name'],
            driver_phone=data['driver_phone'],
            vehicle_number=data['vehicle_number'],
            status=data.get('status', 'active')
        )
        
        db.session.add(trip)
        db.session.commit()
        
        return jsonify({
            'message': 'Trip created successfully',
            'trip': trip.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

