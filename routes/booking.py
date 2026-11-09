from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity
from loguru import logger

from application.api_serializers import booking_row_to_api
from infrastructure.supabase_write_repositories import (
    SupabaseBookingRepository,
    SupabaseCustomerRepository,
    SupabasePaymentRepository,
)
from models.public import db
from routes.guards import customer_required
from services.refund_service import process_refund_for_cancellation

booking_bp = Blueprint('booking', __name__, url_prefix='/api/bookings')
booking_repository = SupabaseBookingRepository()
customer_repository = SupabaseCustomerRepository()
payment_repository = SupabasePaymentRepository()


@booking_bp.route('', methods=['POST'])
@customer_required
def create_booking():
    customer_id = get_jwt_identity()
    try:
        data = request.get_json() or {}

        required_fields = ['trip_id', 'number_of_seats', 'pickup_stop_id', 'dropoff_stop_id']
        for field in required_fields:
            if not data.get(field):
                logger.warning(
                    f"Booking creation rejected: '{field}' is missing (customer_id={customer_id})"
                )
                return jsonify({'error': f'{field} is required'}), 400

        seats = data['number_of_seats']
        if isinstance(seats, bool) or not isinstance(seats, int) or seats < 1:
            return jsonify({'error': 'number_of_seats must be a positive integer'}), 400

        logger.info(
            f"Creating booking: customer_id={customer_id}, trip_id={data['trip_id']}, "
            f"seats={data['number_of_seats']}"
        )

        booking = booking_repository.create(
            customer_id=customer_id,
            trip_id=data['trip_id'],
            seats_reserved=seats,
            pickup_stop_id=data['pickup_stop_id'],
            dropoff_stop_id=data['dropoff_stop_id'],
        )
        db.session.commit()

        logger.info(
            f"Booking created successfully: booking_id={booking['booking_id']}, "
            f"customer_id={customer_id}, reference={booking.get('external_reference')}"
        )

        return jsonify({
            'message': 'Booking created successfully',
            'booking': booking_row_to_api(booking)
        }), 201

    except ValueError as e:
        db.session.rollback()
        logger.warning(f"Booking creation failed (customer_id={customer_id}): {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error creating booking (customer_id={customer_id}): {e}")
        return jsonify({'error': str(e)}), 500


@booking_bp.route('', methods=['GET'])
@customer_required
def get_user_bookings():
    customer_id = get_jwt_identity()
    try:
        bookings = booking_repository.list_for_customer(customer_id)
        db.session.commit()

        logger.info(f"Listed {len(bookings)} booking(s) for customer_id={customer_id}")

        return jsonify({
            'bookings': [booking_row_to_api(booking) for booking in bookings]
        }), 200

    except Exception as e:
        logger.exception(f"Error listing bookings (customer_id={customer_id}): {e}")
        return jsonify({'error': str(e)}), 500


@booking_bp.route('/ticket/<ticket_reference>', methods=['GET'])
def get_booking_by_ticket_reference(ticket_reference):
    try:
        booking = booking_repository.get_by_reference(ticket_reference)

        if not booking:
            logger.warning(f"Ticket lookup failed: reference '{ticket_reference}' not found")
            return jsonify({'error': 'Ticket not found'}), 404

        # Public lookup is verification metadata, never a passenger directory.
        result = booking_row_to_api(booking)
        return jsonify({'ticket': {
            key: result[key] for key in ('ticket_reference', 'trip_id', 'number_of_seats',
                                        'journey_status', 'ticket_status')
        }}), 200

    except Exception as e:
        logger.exception(f"Error fetching booking by ticket reference '{ticket_reference}': {e}")
        return jsonify({'error': str(e)}), 500


@booking_bp.route('/<uuid:booking_id>', methods=['GET'])
@customer_required
def get_booking(booking_id):
    customer_id = get_jwt_identity()
    try:
        booking = booking_repository.get(booking_id)

        if not booking:
            logger.warning(f"Booking lookup failed: booking_id={booking_id} not found")
            return jsonify({'error': 'Booking not found'}), 404

        if str(booking['customer_id']) != str(customer_id):
            logger.warning(
                f"Unauthorized booking access: customer_id={customer_id} tried to access "
                f"booking_id={booking_id} owned by {booking['customer_id']}"
            )
            return jsonify({'error': 'Unauthorized'}), 403

        booking_repository.expire_pending(trip_id=booking['trip_id'])
        db.session.commit()
        booking = booking_repository.get(booking_id)
        return jsonify({'booking': booking_row_to_api(booking)}), 200

    except Exception as e:
        logger.exception(f"Error fetching booking_id={booking_id} (customer_id={customer_id}): {e}")
        return jsonify({'error': str(e)}), 500


@booking_bp.route('/<uuid:booking_id>', methods=['DELETE'])
@customer_required
def cancel_booking(booking_id):
    customer_id = get_jwt_identity()
    try:
        logger.info(f"Cancelling booking_id={booking_id} (customer_id={customer_id})")
        booking = booking_repository.cancel(
            booking_id,
            customer_id,
            cutoff_minutes=current_app.config.get('BOOKING_CANCELLATION_CUTOFF_MINUTES', 60),
        )
        # L'annulation est rendue durable AVANT le remboursement : un echec du
        # refund ne doit jamais de-annuler la reservation.
        db.session.commit()

        logger.info(f"Booking cancelled successfully: booking_id={booking_id}")

        refund = process_refund_for_cancellation(booking, payment_repository)

        # Re-fetch : payment_status peut avoir change si le virement a ete
        # confirme de maniere synchrone.
        booking = booking_repository.get(booking_id) or booking
        return jsonify({
            'message': 'Booking cancelled successfully',
            'booking': booking_row_to_api(booking),
            'refund': refund
        }), 200

    except PermissionError as e:
        db.session.rollback()
        logger.warning(
            f"Booking cancellation denied: customer_id={customer_id}, booking_id={booking_id}: {e}"
        )
        return jsonify({'error': str(e)}), 403
    except ValueError as e:
        db.session.rollback()
        logger.warning(f"Booking cancellation failed: booking_id={booking_id}: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error cancelling booking_id={booking_id} (customer_id={customer_id}): {e}")
        return jsonify({'error': str(e)}), 500


@booking_bp.route('/ticket/<ticket_reference>/consume', methods=['POST'])
@jwt_required()
def consume_ticket(ticket_reference):
    # Explicit server-managed operator allowlist. Ordinary customer tokens
    # cannot scan; this remains disabled until operators are provisioned.
    scanner = str(get_jwt_identity())
    if scanner not in current_app.config.get('TICKET_SCANNER_CUSTOMER_IDS', ()):
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.get_json(silent=True) or {}
    if not data.get('trip_id'):
        return jsonify({'error': 'trip_id is required'}), 400
    try:
        booking = booking_repository.consume_ticket(ticket_reference, data['trip_id'])
        db.session.commit()
        return jsonify({'booking': booking_row_to_api(booking)}), 200
    except ValueError as error:
        db.session.rollback()
        return jsonify({'error': str(error), 'code': str(error)}), 409
    except Exception:
        db.session.rollback()
        logger.exception('Ticket consumption failed')
        return jsonify({'error': 'Ticket validation failed'}), 500
