from uuid import UUID

from flask import Blueprint, jsonify
from loguru import logger

from application.api_serializers import line_stop_to_api, line_to_api
from infrastructure.supabase_read_repositories import SupabaseLineRepository

lines_bp = Blueprint('lines', __name__, url_prefix='/api/lines')
line_repository = SupabaseLineRepository()

@lines_bp.route('/', methods=['GET'])
def get_lines():
    lines = line_repository.list_active()
    logger.info(f"Listed {len(lines)} active line(s)")
    payload = [
        line_to_api(line, line_repository.get_stops(line.id))
        for line in lines
    ]
    return jsonify(payload), 200

@lines_bp.route('/<uuid:line_id>', methods=['GET'])
def get_line(line_id):
    line = line_repository.get(line_id)
    if not line:
        logger.warning(f"Line lookup failed: line_id={line_id} not found")
        return jsonify({'error': 'Line not found'}), 404
    return jsonify(line_to_api(line, line_repository.get_stops(line_id))), 200

@lines_bp.route('/<uuid:line_id>/stops', methods=['GET'])
def get_line_stops(line_id):
    stops = line_repository.get_stops(UUID(str(line_id)))
    return jsonify([line_stop_to_api(stop) for stop in stops]), 200
