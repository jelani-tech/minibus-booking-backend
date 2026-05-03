from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


class PartnerStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"


class VehicleEnergyType(str, Enum):
    DIESEL = "diesel"
    ESSENCE = "essence"
    ELECTRIC = "electric"
    HYBRID = "hybrid"


class VehicleStatus(str, Enum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    MAINTENANCE = "maintenance"
    INACTIVE = "inactive"


class DriverStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class LineStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class StopStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class TripStatus(str, Enum):
    SCHEDULED = "scheduled"
    BOARDING = "boarding"
    DEPARTED = "departed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    BOARDED = "boarded"
    NO_SHOW = "no_show"
    COMPLETED = "completed"


class BookingChannel(str, Enum):
    WHATSAPP = "whatsapp"
    ADMIN = "admin"
    APP = "app"
    AGENT = "agent"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass(frozen=True)
class Partner:
    id: UUID
    name: str
    status: PartnerStatus
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    base_location: str | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class Vehicle:
    id: UUID
    partner_id: UUID
    plate_number: str
    vehicle_code: str
    seat_capacity: int
    standing_capacity: int
    total_capacity: int
    energy_type: VehicleEnergyType
    status: VehicleStatus
    brand: str | None = None
    model: str | None = None
    registration_expiry_date: date | None = None
    insurance_expiry_date: date | None = None
    inspection_expiry_date: date | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class Driver:
    id: UUID
    partner_id: UUID
    first_name: str
    phone: str
    status: DriverStatus
    last_name: str | None = None
    license_number: str | None = None
    license_expiry_date: date | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def full_name(self) -> str:
        return " ".join(part for part in [self.first_name, self.last_name] if part)


@dataclass(frozen=True)
class Line:
    id: UUID
    code: str
    name: str
    origin_name: str
    destination_name: str
    status: LineStatus
    default_duration_minutes: int | None = None
    default_price: Decimal | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class Stop:
    id: UUID
    name: str
    status: StopStatus
    city: str | None = None
    district: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    landmark: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class LineStop:
    id: UUID
    line_id: UUID
    stop_id: UUID
    stop_order: int
    is_pickup_allowed: bool
    is_dropoff_allowed: bool
    scheduled_offset_minutes: int
    created_at: datetime | None = None
    stop: Stop | None = None


@dataclass(frozen=True)
class Trip:
    id: UUID
    line_id: UUID
    partner_id: UUID
    vehicle_id: UUID
    trip_date: date
    departure_time: time
    planned_start_datetime: datetime
    status: TripStatus
    capacity_total: int
    capacity_blocked: int
    capacity_booked: int
    capacity_available: int
    driver_id: UUID | None = None
    planned_end_datetime: datetime | None = None
    base_price: Decimal | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    line: Line | None = None
    partner: Partner | None = None
    vehicle: Vehicle | None = None
    driver: Driver | None = None


@dataclass(frozen=True)
class Customer:
    id: UUID
    first_name: str
    phone: str
    last_name: str | None = None
    whatsapp_phone: str | None = None
    email: str | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def full_name(self) -> str:
        return " ".join(part for part in [self.first_name, self.last_name] if part)


@dataclass(frozen=True)
class Booking:
    id: UUID
    trip_id: UUID
    customer_id: UUID
    seats_reserved: int
    unit_price: Decimal
    total_price: Decimal
    payment_status: PaymentStatus
    booking_status: BookingStatus
    booking_channel: BookingChannel
    pickup_stop_id: UUID | None = None
    dropoff_stop_id: UUID | None = None
    external_reference: str | None = None
    notes: str | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    trip: Trip | None = None
    customer: Customer | None = None
    pickup_stop: Stop | None = None
    dropoff_stop: Stop | None = None


@dataclass(frozen=True)
class Payment:
    id: UUID
    booking_id: UUID
    amount: Decimal
    currency: str
    provider: str
    status: str
    customer_id: UUID | None = None
    provider_reference: str | None = None
    provider_payment_url: str | None = None
    paid_at: datetime | None = None
    raw_provider_response: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

