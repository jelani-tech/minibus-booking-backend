from flask import Blueprint, jsonify
from services.line_service import LineService

lines_bp = Blueprint('lines', __name__, url_prefix='/api/lines')

@lines_bp.route('/', methods=['GET'])
def get_lines():
    lines = LineService.get_all_lines()
    return jsonify([line.to_dict() for line in lines]), 200

@lines_bp.route('/<uuid:line_id>', methods=['GET'])
def get_line(line_id):
    line = LineService.get_line_by_id(line_id)
    if not line:
        return jsonify({'error': 'Line not found'}), 404
    return jsonify(line.to_dict()), 200

@lines_bp.route('/<uuid:line_id>/stops', methods=['GET'])
def get_line_stops(line_id):
    stops = LineService.get_stops_by_line_id(line_id)
    return jsonify([stop.to_dict() for stop in stops]), 200
