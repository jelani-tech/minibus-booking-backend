from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import bcrypt
from sqlalchemy import text

from models.public import db


# ---------------------------------------------------------------------------
# Auth repository — gère auth.users (credentials uniquement)
# ---------------------------------------------------------------------------

class SupabaseAuthRepository:
    """Gère les entrées dans auth.users pour l'authentification par mot de passe.

    La table auth.users ne contient que le téléphone et le mot de passe hashé.
    Le profil métier est dans public.customers (lié via auth_user_id).
    """

    def create(self, * ,user_id:str, phone: str, password: str) -> dict[str, Any]:
        """Crée un utilisateur dans auth.users avec le mot de passe hashé."""
        encrypted = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        row = (
            db.session.execute(
                text(
                    """
                    insert into auth.users (id, phone, encrypted_password)
                    values (:id, :phone, :encrypted_password)
                    returning *
                    """
                ),
                {"id": user_id,"phone": phone, "encrypted_password": encrypted},
            )
            .mappings()
            .one()
        )
        return dict(row)

    def find_by_phone(self, phone: str) -> dict[str, Any] | None:
        """Retourne l'entrée auth.users pour ce numéro, ou None."""
        row = (
            db.session.execute(
                text("select * from auth.users where phone = :phone"),
                {"phone": phone},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def verify_password(self, phone: str, password: str) -> dict[str, Any] | None:
        """Vérifie le mot de passe. Retourne l'entrée auth.users si ok, sinon None."""
        auth_user = self.find_by_phone(phone)
        if not auth_user:
            return None
        is_valid = bcrypt.checkpw(
            password.encode(),
            auth_user["encrypted_password"].encode(),
        )
        return auth_user if is_valid else None

    def get(self, auth_user_id: UUID | str) -> dict[str, Any] | None:
        row = (
            db.session.execute(
                text("select * from auth.users where id = cast(:id as uuid)"),
                {"id": str(auth_user_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def create_password_reset(self, *, phone: str, email: str, otp_code: str, expires_at: Any) -> dict[str, Any]:
        """Crée une entrée d'OTP de réinitialisation dans la table auth.password_resets."""
        import uuid
        from datetime import datetime, timezone
        row = (
            db.session.execute(
                text(
                    """
                    insert into auth.password_resets (id, phone, email, otp_code, expires_at, used, created_at)
                    values (cast(:id as uuid), :phone, :email, :otp_code, :expires_at, false, :created_at)
                    returning *
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "phone": phone,
                    "email": email,
                    "otp_code": otp_code,
                    "expires_at": expires_at,
                    "created_at": datetime.now(timezone.utc),
                },
            )
            .mappings()
            .one()
        )
        return dict(row)

    def find_active_otp(self, *, phone: str, otp_code: str) -> dict[str, Any] | None:
        """Trouve un OTP de réinitialisation actif (non expiré et non utilisé) pour un téléphone."""
        row = (
            db.session.execute(
                text(
                    """
                    select *
                    from auth.password_resets
                    where phone = :phone
                      and otp_code = :otp_code
                      and used = false
                      and expires_at > timezone('utc', now())
                    order by created_at desc
                    limit 1
                    """
                ),
                {"phone": phone, "otp_code": otp_code},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def mark_otp_as_used(self, reset_id: Any) -> None:
        """Marque un OTP comme utilisé."""
        db.session.execute(
            text(
                """
                update auth.password_resets
                set used = true
                where id = cast(:id as uuid)
                """
            ),
            {"id": str(reset_id)},
        )

    def update_password(self, *, phone: str, password: str) -> bool:
        """Met à jour le mot de passe d'un utilisateur dans auth.users."""
        encrypted = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        result = db.session.execute(
            text(
                """
                update auth.users
                set encrypted_password = :encrypted_password,
                    updated_at = timezone('utc', now())
                where phone = :phone
                """
            ),
            {"phone": phone, "encrypted_password": encrypted},
        )
        return result.rowcount > 0


BOOKING_DETAILS_SQL = """
select
    b.id as booking_id,
    b.created_at as booking_created_at,
    b.updated_at as booking_updated_at,
    b.expires_at,
    b.booking_status,
    b.payment_status,
    b.booking_channel,
    b.external_reference,
    b.notes as booking_notes,
    b.seats_reserved,
    b.unit_price,
    b.total_price,
    b.trip_id,
    c.id as customer_id,
    c.first_name as customer_first_name,
    c.last_name as customer_last_name,
    concat_ws(' ', c.first_name, c.last_name) as customer_full_name,
    c.phone as customer_phone,
    c.whatsapp_phone,
    c.email as customer_email,
    t.*,
    l.code as line_code,
    l.name as line_name,
    l.origin_name,
    l.destination_name,
    p.name as partner_name,
    v.vehicle_code,
    v.plate_number,
    v.brand,
    v.model,
    d.first_name as driver_first_name,
    d.last_name as driver_last_name,
    d.phone as driver_phone
from public.bookings b
join public.customers c on c.id = b.customer_id
join public.trips t on t.id = b.trip_id
join public.lines l on l.id = t.line_id
join public.partners p on p.id = t.partner_id
join public.vehicles v on v.id = t.vehicle_id
left join public.drivers d on d.id = t.driver_id
"""


def split_customer_name(name: str) -> tuple[str, str | None]:
    parts = [part for part in name.strip().split(" ") if part]
    if not parts:
        return "Client", None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


class SupabaseCustomerRepository:
    def find_by_phone(self, phone: str) -> dict[str, Any] | None:
        row = (
            db.session.execute(
                text(
                    """
                    select *
                    from public.customers
                    where phone = :phone or whatsapp_phone = :phone
                    order by created_at
                    limit 1
                    """
                ),
                {"phone": phone},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def get(self, customer_id: UUID | str) -> dict[str, Any] | None:
        row = (
            db.session.execute(
                text(
                    """
                    select *
                    from public.customers
                    where id = cast(:customer_id as uuid)
                    """
                ),
                {"customer_id": str(customer_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def create_or_update(
        self,
        *,
        name: str,
        phone: str,
        email: str | None = None,
        auth_user_id: UUID | str | None = None,
    ) -> dict[str, Any]:
        existing = self.find_by_phone(phone)
        first_name, last_name = split_customer_name(name)

        if existing:
            row = (
                db.session.execute(
                    text(
                        """
                        update public.customers
                        set first_name = :first_name,
                            last_name = :last_name,
                            email = coalesce(:email, email),
                            auth_user_id = coalesce(cast(:auth_user_id as uuid), auth_user_id),
                            updated_at = timezone('utc', now())
                        where id = cast(:customer_id as uuid)
                        returning *
                        """
                    ),
                    {
                        "customer_id": str(existing["id"]),
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "auth_user_id": str(auth_user_id) if auth_user_id else None,
                    },
                )
                .mappings()
                .one()
            )
            return dict(row)

        row = (
            db.session.execute(
                text(
                    """
                    insert into public.customers (
                        auth_user_id,
                        first_name,
                        last_name,
                        phone,
                        whatsapp_phone,
                        email
                    )
                    values (cast(:auth_user_id as uuid), :first_name, :last_name, :phone, :phone, :email)
                    returning *
                    """
                ),
                {
                    "auth_user_id": str(auth_user_id) if auth_user_id else None,
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": phone,
                    "email": email,
                },
            )
            .mappings()
            .one()
        )
        return dict(row)

    def find_by_auth_user_id(self, auth_user_id: UUID | str) -> dict[str, Any] | None:
        """Récupère le profil customer lié à un auth_user_id."""
        row = (
            db.session.execute(
                text(
                    """
                    select *
                    from public.customers
                    where auth_user_id = cast(:auth_user_id as uuid)
                    """
                ),
                {"auth_user_id": str(auth_user_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None


class SupabaseBookingRepository:
    def create(
        self,
        *,
        customer_id: UUID | str,
        trip_id: UUID | str,
        seats_reserved: int,
        pickup_stop_id: UUID | str,
        dropoff_stop_id: UUID | str,
    ) -> dict[str, Any]:
        trip = (
            db.session.execute(
                text(
                    """
                    select *
                    from public.trips
                    where id = cast(:trip_id as uuid)
                    for update
                    """
                ),
                {"trip_id": str(trip_id)},
            )
            .mappings()
            .first()
        )
        if not trip:
            raise ValueError("Trip not found")
        if trip["status"] not in ("scheduled", "boarding"):
            raise ValueError("Trip is not available for booking")
        if seats_reserved > trip["capacity_available"]:
            raise ValueError("Not enough seats available")

        unit_price = trip["base_price"] or 0
        ticket_reference = f"JELANI-{str(uuid4()).split('-')[0].upper()}"
        row = (
            db.session.execute(
                text(
                    """
                    insert into public.bookings (
                        trip_id,
                        customer_id,
                        seats_reserved,
                        unit_price,
                        total_price,
                        payment_status,
                        booking_status,
                        booking_channel,
                        pickup_stop_id,
                        dropoff_stop_id,
                        external_reference,
                        notes
                    )
                    values (
                        cast(:trip_id as uuid),
                        cast(:customer_id as uuid),
                        :seats_reserved,
                        :unit_price,
                        :total_price,
                        'pending',
                        'pending',
                        'app',
                        :pickup_stop_id,
                        :dropoff_stop_id,
                        :external_reference,
                        :notes
                    )
                    returning id
                    """
                ),
                {
                    "trip_id": str(trip_id),
                    "customer_id": str(customer_id),
                    "seats_reserved": seats_reserved,
                    "unit_price": unit_price,
                    "total_price": unit_price * seats_reserved,
                    "external_reference": ticket_reference,
                    "pickup_stop_id": str(pickup_stop_id),
                    "dropoff_stop_id": str(dropoff_stop_id),
                    "notes": "Payment canal: app"
                },
            )
            .mappings()
            .one()
        )
        db.session.flush()
        return self.get(row["id"])

    def list_for_customer(self, customer_id: UUID | str) -> list[dict[str, Any]]:
        rows = db.session.execute(
            text(
                f"""
                {BOOKING_DETAILS_SQL}
                where b.customer_id = cast(:customer_id as uuid)
                order by b.created_at desc
                """
            ),
            {"customer_id": str(customer_id)},
        ).mappings()
        return [dict(row) for row in rows]

    def get(self, booking_id: UUID | str) -> dict[str, Any] | None:
        row = (
            db.session.execute(
                text(
                    f"""
                    {BOOKING_DETAILS_SQL}
                    where b.id = cast(:booking_id as uuid)
                    """
                ),
                {"booking_id": str(booking_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def get_by_reference(self, ticket_reference: str) -> dict[str, Any] | None:
        row = (
            db.session.execute(
                text(
                    f"""
                    {BOOKING_DETAILS_SQL}
                    where b.external_reference = :ticket_reference
                    """
                ),
                {"ticket_reference": ticket_reference},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def cancel(self, booking_id: UUID | str, customer_id: UUID | str) -> dict[str, Any]:
        existing = self.get(booking_id)
        if not existing:
            raise ValueError("Booking not found")
        if str(existing["customer_id"]) != str(customer_id):
            raise PermissionError("Unauthorized")
        if existing["booking_status"] == "cancelled":
            raise ValueError("Booking already cancelled")

        db.session.execute(
            text(
                """
                update public.bookings
                set booking_status = 'cancelled',
                    updated_at = timezone('utc', now())
                where id = cast(:booking_id as uuid)
                """
            ),
            {"booking_id": str(booking_id)},
        )
        db.session.flush()
        return self.get(booking_id)


class SupabasePaymentRepository:
    def create_or_update(
        self,
        *,
        booking_id: UUID | str,
        customer_id: UUID | str,
        amount,
        provider: str,
        provider_reference: str,
        provider_payment_url: str | None,
        raw_provider_response: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = (
            db.session.execute(
                text(
                    """
                    insert into public.payments (
                        booking_id,
                        customer_id,
                        amount,
                        currency,
                        provider,
                        provider_reference,
                        provider_payment_url,
                        status,
                        raw_provider_response
                    )
                    values (
                        cast(:booking_id as uuid),
                        cast(:customer_id as uuid),
                        :amount,
                        'XOF',
                        :provider,
                        :provider_reference,
                        :provider_payment_url,
                        'pending',
                        cast(:raw_provider_response as jsonb)
                    )
                    returning *
                    """
                ),
                {
                    "booking_id": str(booking_id),
                    "customer_id": str(customer_id),
                    "amount": amount,
                    "provider": provider,
                    "provider_reference": provider_reference,
                    "provider_payment_url": provider_payment_url,
                    "raw_provider_response": None,
                },
            )
            .mappings()
            .one()
        )
        return dict(row)

    def get_for_booking(self, booking_id: UUID | str) -> dict[str, Any] | None:
        row = (
            db.session.execute(
                text(
                    """
                    select *
                    from public.payments
                    where booking_id = cast(:booking_id as uuid)
                    order by created_at desc
                    limit 1
                    """
                ),
                {"booking_id": str(booking_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def update_status_by_reference(self, provider_reference: str, status: str) -> dict[str, Any] | None:
        payment_status = "paid" if status in ("completed", "success", "paid") else "failed"
        booking_status = "confirmed" if payment_status == "paid" else "pending"
        row = (
            db.session.execute(
                text(
                    """
                    update public.payments
                    set status = :payment_status,
                        paid_at = case when :payment_status = 'paid' then timezone('utc', now()) else paid_at end,
                        updated_at = timezone('utc', now())
                    where provider_reference = :provider_reference
                    returning *
                    """
                ),
                {
                    "provider_reference": provider_reference,
                    "payment_status": payment_status,
                },
            )
            .mappings()
            .first()
        )
        if not row:
            return None

        db.session.execute(
            text(
                """
                update public.bookings
                set payment_status = :payment_status,
                    booking_status = :booking_status,
                    updated_at = timezone('utc', now())
                where id = cast(:booking_id as uuid)
                """
            ),
            {
                "booking_id": str(row["booking_id"]),
                "payment_status": payment_status,
                "booking_status": booking_status,
            },
        )
        return dict(row)
