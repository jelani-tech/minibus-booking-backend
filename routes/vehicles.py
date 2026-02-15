from flask import Blueprint, request, jsonify
from models.public import db, User
from models.vehicles import Vehicle
from models.partners import ScheduledTrip
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from sqlalchemy import or_

vehicles_bp = Blueprint('vehicles', __name__, url_prefix='/api/vehicles')

def admin_required():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user or user.role != 'admin':
        return False
    return True

@vehicles_bp.route('', methods=['GET'])
@jwt_required()
def get_vehicles():
    if not admin_required():
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        vehicles = Vehicle.query.all()
        return jsonify({'vehicles': [v.to_dict() for v in vehicles]}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@vehicles_bp.route('/available', methods=['GET'])
@jwt_required()
def get_available_vehicles():
    # if not admin_required():
    #     return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        start_time_str = request.args.get('start_time')
        end_time_str = request.args.get('end_time')
        
        if not start_time_str or not end_time_str:
            return jsonify({'error': 'Start time and end time are required'}), 400
            
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
        
        # Find vehicles that have overlapping trips
        overlapping_trips = ScheduledTrip.query.filter(
            ScheduledTrip.status == 'active',
            or_(
                (ScheduledTrip.departure_time <= end_time) & (ScheduledTrip.arrival_time >= start_time)
            )
        ).all()
        
        busy_vehicle_ids = [trip.vehicle_id for trip in overlapping_trips if trip.vehicle_id]
        
        available_vehicles = Vehicle.query.filter(
            Vehicle.status == 'ACTIVE',
            ~Vehicle.id.in_(busy_vehicle_ids)
        ).all()
        
        return jsonify({'vehicles': [v.to_dict() for v in available_vehicles]}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@vehicles_bp.route('', methods=['POST'])
@jwt_required()
def create_vehicle():
    if not admin_required():
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        data = request.get_json()
        required_fields = ['plate_number', 'make', 'model', 'capacity']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
                
        if Vehicle.query.filter_by(plate_number=data['plate_number']).first():
            return jsonify({'error': 'Vehicle with this plate number already exists'}), 400
            
        vehicle = Vehicle(
            plate_number=data['plate_number'],
            make=data['make'],
            model=data['model'],
            capacity=int(data['capacity']),
            image_url=data.get('image_url'),
            status=data.get('status', 'ACTIVE')
        )
        
        db.session.add(vehicle)
        db.session.commit()
        
        return jsonify({'message': 'Vehicle created', 'vehicle': vehicle.to_dict()}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@vehicles_bp.route('/<uuid:vehicle_id>', methods=['PUT'])
@jwt_required()
def update_vehicle(vehicle_id):
    if not admin_required():
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        vehicle = Vehicle.query.get(vehicle_id)
        if not vehicle:
            return jsonify({'error': 'Vehicle not found'}), 404
            
        data = request.get_json()
        if 'plate_number' in data: vehicle.plate_number = data['plate_number']
        if 'make' in data: vehicle.make = data['make']
        if 'model' in data: vehicle.model = data['model']
        if 'capacity' in data: vehicle.capacity = int(data['capacity'])
        if 'image_url' in data: vehicle.image_url = data['image_url']
        if 'status' in data: vehicle.status = data['status']
        
        db.session.commit()
        return jsonify({'message': 'Vehicle updated', 'vehicle': vehicle.to_dict()}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
