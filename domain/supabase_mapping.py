from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from .entities import (
    Booking,
    BookingChannel,
    BookingStatus,
    Customer,
    Driver,
    DriverStatus,
    Line,
    LineStatus,
    LineStop,
    Partner,
    PartnerStatus,
    Payment,
    PaymentStatus,
    Stop,
    StopStatus,
    Trip,
    TripStatus,
    Vehicle,
    VehicleEnergyType,
    VehicleStatus,
)


def as_uuid(value: Any) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def as_decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def as_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def as_date(value: Any) -> date | None:
    if value is None or isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value))


def as_time(value: Any) -> time:
    if isinstance(value, time):
        return value
    return time.fromisoformat(str(value))


def partner_from_row(row: dict[str, Any]) -> Partner:
    return Partner(
        id=as_uuid(row["id"]),
        name=row["name"],
        status=PartnerStatus(row["status"]),
        contact_name=row.get("contact_name"),
        contact_phone=row.get("contact_phone"),
        contact_email=row.get("contact_email"),
        base_location=row.get("base_location"),
        notes=row.get("notes"),
        created_at=as_datetime(row.get("created_at")),
        updated_at=as_datetime(row.get("updated_at")),
    )


def vehicle_from_row(row: dict[str, Any]) -> Vehicle:
    return Vehicle(
        id=as_uuid(row["id"]),
        partner_id=as_uuid(row["partner_id"]),
        plate_number=row["plate_number"],
        vehicle_code=row["vehicle_code"],
        brand=row.get("brand"),
        model=row.get("model"),
        seat_capacity=int(row["seat_capacity"]),
        standing_capacity=int(row.get("standing_capacity") or 0),
        total_capacity=int(row["total_capacity"]),
        energy_type=VehicleEnergyType(row["energy_type"]),
        status=VehicleStatus(row["status"]),
        registration_expiry_date=as_date(row.get("registration_expiry_date")),
        insurance_expiry_date=as_date(row.get("insurance_expiry_date")),
        inspection_expiry_date=as_date(row.get("inspection_expiry_date")),
        notes=row.get("notes"),
        created_at=as_datetime(row.get("created_at")),
        updated_at=as_datetime(row.get("updated_at")),
    )


def driver_from_row(row: dict[str, Any]) -> Driver:
    return Driver(
        id=as_uuid(row["id"]),
        partner_id=as_uuid(row["partner_id"]),
        first_name=row["first_name"],
        last_name=row.get("last_name"),
        phone=row["phone"],
        license_number=row.get("license_number"),
        license_expiry_date=as_date(row.get("license_expiry_date")),
        status=DriverStatus(row["status"]),
        notes=row.get("notes"),
        created_at=as_datetime(row.get("created_at")),
        updated_at=as_datetime(row.get("updated_at")),
    )


def line_from_row(row: dict[str, Any]) -> Line:
    return Line(
        id=as_uuid(row["id"]),
        code=row["code"],
        name=row["name"],
        origin_name=row["origin_name"],
        destination_name=row["destination_name"],
        default_duration_minutes=row.get("default_duration_minutes"),
        default_price=as_decimal(row["default_price"]) if row.get("default_price") is not None else None,
        status=LineStatus(row["status"]),
        notes=row.get("notes"),
        created_at=as_datetime(row.get("created_at")),
        updated_at=as_datetime(row.get("updated_at")),
    )


def stop_from_row(row: dict[str, Any]) -> Stop:
    return Stop(
        id=as_uuid(row["id"]),
        name=row["name"],
        city=row.get("city"),
        district=row.get("district"),
        latitude=as_decimal(row["latitude"]) if row.get("latitude") is not None else None,
        longitude=as_decimal(row["longitude"]) if row.get("longitude") is not None else None,
        landmark=row.get("landmark"),
        status=StopStatus(row["status"]),
        created_at=as_datetime(row.get("created_at")),
        updated_at=as_datetime(row.get("updated_at")),
    )


def line_stop_from_row(row: dict[str, Any]) -> LineStop:
    stop_row = row.get("stop") or row.get("stops")
    return LineStop(
        id=as_uuid(row["id"]),
        line_id=as_uuid(row["line_id"]),
        stop_id=as_uuid(row["stop_id"]),
        stop_order=int(row["stop_order"]),
        is_pickup_allowed=bool(row["is_pickup_allowed"]),
        is_dropoff_allowed=bool(row["is_dropoff_allowed"]),
        scheduled_offset_minutes=int(row.get("scheduled_offset_minutes") or 0),
        created_at=as_datetime(row.get("created_at")),
        stop=stop_from_row(stop_row) if isinstance(stop_row, dict) else None,
    )


def trip_from_row(row: dict[str, Any]) -> Trip:
    return Trip(
        id=as_uuid(row["id"]),
        line_id=as_uuid(row["line_id"]),
        partner_id=as_uuid(row["partner_id"]),
        vehicle_id=as_uuid(row["vehicle_id"]),
        driver_id=as_uuid(row["driver_id"]) if row.get("driver_id") else None,
        trip_date=as_date(row["trip_date"]) or date.min,
        departure_time=as_time(row["departure_time"]),
        planned_start_datetime=as_datetime(row["planned_start_datetime"]) or datetime.min,
        planned_end_datetime=as_datetime(row.get("planned_end_datetime")),
        status=TripStatus(row["status"]),
        capacity_total=int(row["capacity_total"]),
        capacity_blocked=int(row.get("capacity_blocked") or 0),
        capacity_booked=int(row.get("capacity_booked") or 0),
        capacity_available=int(row.get("capacity_available") or 0),
        base_price=as_decimal(row["base_price"]) if row.get("base_price") is not None else None,
        notes=row.get("notes"),
        created_at=as_datetime(row.get("created_at")),
        updated_at=as_datetime(row.get("updated_at")),
    )


def customer_from_row(row: dict[str, Any]) -> Customer:
    return Customer(
        id=as_uuid(row["id"]),
        first_name=row["first_name"],
        last_name=row.get("last_name"),
        phone=row["phone"],
        whatsapp_phone=row.get("whatsapp_phone"),
        email=row.get("email"),
        notes=row.get("notes"),
        created_at=as_datetime(row.get("created_at")),
        updated_at=as_datetime(row.get("updated_at")),
    )


def booking_from_row(row: dict[str, Any]) -> Booking:
    return Booking(
        id=as_uuid(row["id"]),
        trip_id=as_uuid(row["trip_id"]),
        customer_id=as_uuid(row["customer_id"]),
        pickup_stop_id=as_uuid(row["pickup_stop_id"]) if row.get("pickup_stop_id") else None,
        dropoff_stop_id=as_uuid(row["dropoff_stop_id"]) if row.get("dropoff_stop_id") else None,
        seats_reserved=int(row["seats_reserved"]),
        unit_price=as_decimal(row["unit_price"]),
        total_price=as_decimal(row["total_price"]),
        payment_status=PaymentStatus(row["payment_status"]),
        booking_status=BookingStatus(row["booking_status"]),
        booking_channel=BookingChannel(row["booking_channel"]),
        external_reference=row.get("external_reference"),
        notes=row.get("notes"),
        expires_at=as_datetime(row.get("expires_at")),
        created_at=as_datetime(row.get("created_at")),
        updated_at=as_datetime(row.get("updated_at")),
    )


def payment_from_row(row: dict[str, Any]) -> Payment:
    return Payment(
        id=as_uuid(row["id"]),
        booking_id=as_uuid(row["booking_id"]),
        customer_id=as_uuid(row["customer_id"]) if row.get("customer_id") else None,
        amount=as_decimal(row["amount"]),
        currency=row.get("currency") or "XOF",
        provider=row.get("provider") or "jeko",
        provider_reference=row.get("provider_reference"),
        provider_payment_url=row.get("provider_payment_url"),
        status=row["status"],
        paid_at=as_datetime(row.get("paid_at")),
        raw_provider_response=row.get("raw_provider_response"),
        created_at=as_datetime(row.get("created_at")),
        updated_at=as_datetime(row.get("updated_at")),
    )

