from flask import Blueprint, request, jsonify
from models.public import db
from models.partners import ScheduledTrip
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from uuid import UUID

from application.api_serializers import trip_row_to_api
from infrastructure.supabase_read_repositories import SupabaseTripRepository

trip_bp = Blueprint('trip', __name__, url_prefix='/api/trips')
trip_repository = SupabaseTripRepository()

@trip_bp.route('', methods=['GET'])
def get_trips():
    try:
        departure_city = request.args.get('departure_city')
        arrival_city = request.args.get('arrival_city')
        date = request.args.get('date')

        trip_date = None
        if date:
            try:
                trip_date = datetime.strptime(date, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        trips = trip_repository.search(
            origin_name=departure_city,
            destination_name=arrival_city,
            trip_date=trip_date,
        )

        return jsonify({
            'trips': [trip_row_to_api(trip) for trip in trips]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@trip_bp.route('/by-line/<string:line_code>', methods=['GET'])
def get_trips_by_line_code(line_code):
    try:
        trips = trip_repository.get_by_line_code(line_code)
        return jsonify({'trips': [trip_row_to_api(trip) for trip in trips]}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trip_bp.route('/<uuid:trip_id>', methods=['GET'])
def get_trip(trip_id):
    try:
        trip = trip_repository.get(trip_id)
        
        if not trip:
            return jsonify({'error': 'Trip not found'}), 404
        
        return jsonify({'trip': trip_row_to_api(trip)}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@trip_bp.route('', methods=['POST'])
@jwt_required()
def create_trip():
    try:
        user_id = get_jwt_identity()
        from models.public import User
        user = User.query.get(user_id)
        if not user or user.role != 'admin':
             return jsonify({'error': 'Unauthorized'}), 403

        data = request.get_json()
        
        # Validation
        required_fields = ['departure_city', 'arrival_city', 'departure_time', 'arrival_time', 'price', 'driver_name', 'driver_phone', 'vehicle_id']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Parse datetime
        try:
            departure_time = datetime.fromisoformat(data['departure_time'].replace('Z', '+00:00'))
            arrival_time = datetime.fromisoformat(data['arrival_time'].replace('Z', '+00:00'))
        except (ValueError, KeyError):
            return jsonify({'error': 'Invalid datetime format'}), 400
            
        # Check Vehicle Availability
        from models.vehicles import Vehicle
        from sqlalchemy import or_
        
        vehicle = Vehicle.query.get(data['vehicle_id'])
        if not vehicle:
            return jsonify({'error': 'Vehicle not found'}), 404
            
        if vehicle.status != 'ACTIVE':
            return jsonify({'error': 'Vehicle is not active'}), 400
            
        # Check for overlaps
        overlapping = ScheduledTrip.query.filter(
            ScheduledTrip.vehicle_id == data['vehicle_id'],
            ScheduledTrip.status == 'active',
            or_(
                (ScheduledTrip.departure_time <= arrival_time) & (ScheduledTrip.arrival_time >= departure_time)
            )
        ).first()
        
        if overlapping:
             return jsonify({'error': 'Vehicle is already booked for this time range'}), 409
        
        trip = ScheduledTrip(
            departure_city=data['departure_city'],
            arrival_city=data['arrival_city'],
            departure_time=departure_time,
            arrival_time=arrival_time,
            price=float(data['price']),
            available_seats=int(data.get('available_seats', vehicle.capacity)), # Default to vehicle capacity
            total_seats=int(data.get('total_seats', vehicle.capacity)),
            driver_name=data['driver_name'],
            driver_phone=data['driver_phone'],
            # vehicle_number=data['vehicle_number'], # Deprecated
            vehicle_id=data['vehicle_id'],
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

