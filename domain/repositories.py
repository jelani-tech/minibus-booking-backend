from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from .entities import Booking, Customer, Line, LineStop, Payment, Trip


class LineRepository(Protocol):
    def list_active(self) -> list[Line]:
        ...

    def get_stops(self, line_id: UUID) -> list[LineStop]:
        ...


class TripRepository(Protocol):
    def search(
        self,
        *,
        line_id: UUID | None = None,
        origin_name: str | None = None,
        destination_name: str | None = None,
        trip_date: date | None = None,
    ) -> list[Trip]:
        ...

    def get(self, trip_id: UUID) -> Trip | None:
        ...

    def get_by_line_code(self, line_code: str) -> list[Trip]:
        ...


class CustomerRepository(Protocol):
    def find_by_phone(self, phone: str) -> Customer | None:
        ...

    def save(self, customer: Customer) -> Customer:
        ...


class BookingRepository(Protocol):
    def create(self, booking: Booking) -> Booking:
        ...

    def get(self, booking_id: UUID) -> Booking | None:
        ...

    def list_for_customer(self, customer_id: UUID) -> list[Booking]:
        ...

    def cancel(self, booking_id: UUID) -> Booking:
        ...


class PaymentRepository(Protocol):
    def create_or_update(self, payment: Payment) -> Payment:
        ...

    def get_for_booking(self, booking_id: UUID) -> Payment | None:
        ...

