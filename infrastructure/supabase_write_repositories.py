from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
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

    def update_phone(self, *, old_phone: str, new_phone: str) -> bool:
        """Updates a user's phone number in auth.users."""
        result = db.session.execute(
            text(
                """
                update auth.users
                set phone = :new_phone,
                    updated_at = timezone('utc', now())
                where phone = :old_phone
                """
            ),
            {"old_phone": old_phone, "new_phone": new_phone},
        )
        return result.rowcount > 0

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
    b.pickup_stop_id,
    b.dropoff_stop_id,
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

    def update_profile(
        self,
        *,
        customer_id: UUID | str,
        name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any] | None:
        """Updates the name, phone, and/or email of an existing customer.

        Only the provided fields (not None) are modified; the others keep
        their current value.
        """
        first_name = last_name = None
        if name:
            first_name, last_name = split_customer_name(name)

        row = (
            db.session.execute(
                text(
                    """
                    update public.customers
                    set first_name = coalesce(:first_name, first_name),
                        last_name = case when :name_provided then :last_name else last_name end,
                        phone = coalesce(:phone, phone),
                        email = coalesce(:email, email),
                        updated_at = timezone('utc', now())
                    where id = cast(:customer_id as uuid)
                    returning *
                    """
                ),
                {
                    "customer_id": str(customer_id),
                    "first_name": first_name,
                    "last_name": last_name,
                    "name_provided": name is not None,
                    "phone": phone,
                    "email": email,
                },
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

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

    def cancel(
        self,
        booking_id: UUID | str,
        customer_id: UUID | str,
        cutoff_minutes: int = 60,
    ) -> dict[str, Any]:
        existing = self.get(booking_id)
        if not existing:
            raise ValueError("Booking not found")
        if str(existing["customer_id"]) != str(customer_id):
            raise PermissionError("Unauthorized")
        if existing["booking_status"] == "cancelled":
            raise ValueError("Booking already cancelled")

        # Fenêtre d'annulation : refusée à moins de cutoff_minutes du départ
        # (couvre aussi les trips déjà partis).
        planned_start = existing.get("planned_start_datetime")
        if planned_start is not None:
            if planned_start.tzinfo is None:
                planned_start = planned_start.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > planned_start - timedelta(minutes=cutoff_minutes):
                raise ValueError(
                    f"Cancellation is only allowed up to {cutoff_minutes} minutes before departure"
                )

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


# Valeurs de payments.status marquant un paiement encaisse ('paid' et
# 'completed' sont les valeurs historiques, 'success' la valeur canonique).
SETTLED_SUCCESS_STATUSES = ("success", "paid", "completed")

# États de remboursement (payments.status) : refund_pending = virement JEKO créé
# en attente de confirmation webhook ; refunded = confirmé (terminal) ;
# refund_required = à traiter manuellement (Paystack, payeur introuvable, échec
# du virement...).
REFUND_STATUSES = ("refund_pending", "refunded", "refund_required")


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
        """Reutilise la ligne de paiement non soldee du booking (relance de
        checkout) plutot que d'en inserer une nouvelle : GET /status renvoie la
        ligne la plus recente, qui doit suivre la derniere reference emise."""
        raw_response_json = (
            json.dumps(raw_provider_response, default=str)
            if raw_provider_response is not None
            else None
        )

        existing = self.get_for_booking(booking_id)
        if existing and existing["status"] not in SETTLED_SUCCESS_STATUSES:
            row = (
                db.session.execute(
                    text(
                        """
                        update public.payments
                        set customer_id = cast(:customer_id as uuid),
                            amount = :amount,
                            provider = :provider,
                            provider_reference = :provider_reference,
                            provider_payment_url = :provider_payment_url,
                            status = 'pending',
                            paid_at = null,
                            raw_provider_response = cast(:raw_provider_response as jsonb),
                            updated_at = timezone('utc', now())
                        where id = cast(:payment_id as uuid)
                        returning *
                        """
                    ),
                    {
                        "payment_id": str(existing["id"]),
                        "customer_id": str(customer_id),
                        "amount": amount,
                        "provider": provider,
                        "provider_reference": provider_reference,
                        "provider_payment_url": provider_payment_url,
                        "raw_provider_response": raw_response_json,
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
                    "raw_provider_response": raw_response_json,
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

    def get_by_reference(self, provider_reference: str, for_update: bool = False) -> dict[str, Any] | None:
        lock_clause = " for update" if for_update else ""
        row = (
            db.session.execute(
                text(
                    f"""
                    select *
                    from public.payments
                    where provider_reference = :provider_reference{lock_clause}
                    """
                ),
                {"provider_reference": provider_reference},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def settle_by_reference(
        self,
        provider_reference: str,
        payment_status: str,
        raw_provider_response: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, bool]:
        """payment_status: 'success' ou 'failed' (statuts canoniques lus par le mobile).

        bookings.payment_status est un enum Postgres ('pending','paid','failed','refunded'),
        d'ou le mapping success -> paid cote booking.

        Le booking n'est mis a jour que s'il est encore 'pending' : un evenement
        tardif ne doit ni reactiver ni confirmer un booking annule.

        Retourne (ligne payment, booking mis a jour ou non).
        """
        booking_payment_status = "paid" if payment_status == "success" else "failed"
        booking_status = "confirmed" if payment_status == "success" else "pending"
        row = (
            db.session.execute(
                text(
                    """
                    update public.payments
                    set status = :payment_status,
                        paid_at = case
                            when :payment_status = 'success' then coalesce(paid_at, timezone('utc', now()))
                            else paid_at
                        end,
                        raw_provider_response = coalesce(
                            cast(:raw_provider_response as jsonb),
                            raw_provider_response
                        ),
                        updated_at = timezone('utc', now())
                    where provider_reference = :provider_reference
                    returning *
                    """
                ),
                {
                    "provider_reference": provider_reference,
                    "payment_status": payment_status,
                    "raw_provider_response": (
                        json.dumps(raw_provider_response, default=str)
                        if raw_provider_response is not None
                        else None
                    ),
                },
            )
            .mappings()
            .first()
        )
        if not row:
            return None, False

        booking_row = db.session.execute(
            text(
                """
                update public.bookings
                set payment_status = :payment_status,
                    booking_status = :booking_status,
                    updated_at = timezone('utc', now())
                where id = cast(:booking_id as uuid)
                  and booking_status = 'pending'
                returning id
                """
            ),
            {
                "booking_id": str(row["booking_id"]),
                "payment_status": booking_payment_status,
                "booking_status": booking_status,
            },
        ).first()
        return dict(row), booking_row is not None

    def mark_refund(
        self,
        payment_id: UUID | str,
        refund_status: str,
        refund_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Pose un état de remboursement (cf. REFUND_STATUSES) sur le paiement.

        Les détails du remboursement sont fusionnés sous la clé 'refund' du
        jsonb raw_provider_response (pas d'écrasement des données de paiement).
        """
        row = (
            db.session.execute(
                text(
                    """
                    update public.payments
                    set status = :refund_status,
                        raw_provider_response = case
                            when cast(:refund_data as jsonb) is null then raw_provider_response
                            else coalesce(raw_provider_response, '{}'::jsonb)
                                 || jsonb_build_object('refund', cast(:refund_data as jsonb))
                        end,
                        updated_at = timezone('utc', now())
                    where id = cast(:payment_id as uuid)
                    returning *
                    """
                ),
                {
                    "payment_id": str(payment_id),
                    "refund_status": refund_status,
                    "refund_data": (
                        json.dumps(refund_data, default=str)
                        if refund_data is not None
                        else None
                    ),
                },
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def settle_refund_by_reference(
        self,
        provider_reference: str,
        refund_status: str,
        provider_data: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, bool]:
        """Applique le résultat d'un virement de remboursement JEKO.

        refund_status: 'refunded' ou 'refund_required'. Si 'refunded', le booking
        passe payment_status='refunded' (booking_status inchangé : déjà annulé).
        Les données du virement sont fusionnées sous 'refund_settlement' dans le
        jsonb, sans écraser les données de paiement.

        Retourne (ligne payment, booking mis à jour ou non).
        """
        row = (
            db.session.execute(
                text(
                    """
                    update public.payments
                    set status = :refund_status,
                        raw_provider_response = case
                            when cast(:provider_data as jsonb) is null then raw_provider_response
                            else coalesce(raw_provider_response, '{}'::jsonb)
                                 || jsonb_build_object('refund_settlement', cast(:provider_data as jsonb))
                        end,
                        updated_at = timezone('utc', now())
                    where provider_reference = :provider_reference
                    returning *
                    """
                ),
                {
                    "provider_reference": provider_reference,
                    "refund_status": refund_status,
                    "provider_data": (
                        json.dumps(provider_data, default=str)
                        if provider_data is not None
                        else None
                    ),
                },
            )
            .mappings()
            .first()
        )
        if not row:
            return None, False

        booking_row = None
        if refund_status == "refunded":
            booking_row = db.session.execute(
                text(
                    """
                    update public.bookings
                    set payment_status = 'refunded',
                        updated_at = timezone('utc', now())
                    where id = cast(:booking_id as uuid)
                    returning id
                    """
                ),
                {"booking_id": str(row["booking_id"])},
            ).first()
        return dict(row), booking_row is not None


# ---------------------------------------------------------------------------
# Wallet repository — gère public.wallets / wallet_entries / wallet_topups
# ---------------------------------------------------------------------------

# Sens d'un mouvement. Le montant est toujours positif, le signe est porté ici.
WALLET_DIRECTIONS = ("credit", "debit")

# Types d'écriture du registre.
WALLET_ENTRY_TYPES = (
    "topup",
    "booking_payment",
    "booking_refund",
    "topup_reversal",
    "adjustment",
    "promo_credit",
)

# Un wallet gelé (fraude, litige) refuse les débits et les crédits de
# rechargement, mais jamais un remboursement ni une correction du support :
# bloquer ces deux-là laisserait de l'argent client dans les limbes.
WALLET_FROZEN_ALLOWED_ENTRY_TYPES = ("booking_refund", "adjustment")

# Statuts d'une tentative de rechargement, calqués sur payments.status.
TOPUP_STATUSES = ("pending", "success", "failed", "expired")

# Préfixe des références de rechargement que nous émettons. C'est lui qui permet
# d'aiguiller un événement provider vers le règlement d'un topup plutôt que vers
# celui d'un paiement de réservation (cf. RF- pour les virements sortants).
TOPUP_REFERENCE_PREFIX = "TU-"


class WalletError(Exception):
    """Erreur métier du wallet, portant un code stable pour l'app mobile."""

    code = "WALLET_ERROR"
    http_status = 400


class WalletFrozenError(WalletError):
    code = "WALLET_FROZEN"
    http_status = 409


class InsufficientFundsError(WalletError):
    code = "INSUFFICIENT_FUNDS"
    http_status = 402

    def __init__(self, *, balance: int, required: int):
        self.balance = int(balance)
        self.required = int(required)
        self.missing = self.required - self.balance
        super().__init__(
            f"Insufficient wallet balance: {self.balance} < {self.required} "
            f"(missing {self.missing})"
        )


class SupabaseWalletRepository:
    """Accès au porte-monnaie client.

    Toute mutation du solde passe par post_entry() : c'est le seul endroit qui
    verrouille le wallet, vérifie les invariants et écrit dans le registre.
    Aucune route ne doit toucher wallets.balance directement.
    """

    # ── wallets ────────────────────────────────────────────────────────────

    def get_or_create(self, customer_id: UUID | str) -> dict[str, Any]:
        """Retourne le wallet du client, en le créant à la volée si besoin.

        La contrainte d'unicité sur customer_id est la garantie anti-doublon :
        deux créations concurrentes ne produisent qu'un seul wallet.
        """
        wallet = self.get_for_customer(customer_id)
        if wallet:
            return wallet

        db.session.execute(
            text(
                """
                insert into public.wallets (customer_id)
                values (cast(:customer_id as uuid))
                on conflict (customer_id) do nothing
                """
            ),
            {"customer_id": str(customer_id)},
        )
        db.session.flush()
        wallet = self.get_for_customer(customer_id)
        if not wallet:
            raise WalletError(f"Could not create wallet for customer {customer_id}")
        return wallet

    def get_for_customer(
        self, customer_id: UUID | str, for_update: bool = False
    ) -> dict[str, Any] | None:
        lock_clause = " for update" if for_update else ""
        row = (
            db.session.execute(
                text(
                    f"""
                    select *
                    from public.wallets
                    where customer_id = cast(:customer_id as uuid){lock_clause}
                    """
                ),
                {"customer_id": str(customer_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    # ── registre ───────────────────────────────────────────────────────────

    def post_entry(
        self,
        *,
        customer_id: UUID | str,
        direction: str,
        entry_type: str,
        amount: int,
        idempotency_key: str,
        reference_type: str | None = None,
        reference_id: UUID | str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Applique un mouvement au wallet et l'inscrit au registre.

        Séquence, dans la transaction de l'appelant (qui commit) :
          1. verrou de ligne sur le wallet, ce qui sérialise les mouvements du
             même client (deux clients différents ne se bloquent jamais) ;
          2. wallet gelé -> WalletFrozenError, sauf remboursement/ajustement ;
          3. débit supérieur au solde -> InsufficientFundsError (avec le manquant) ;
          4. insertion de l'écriture, 'on conflict (idempotency_key) do nothing' ;
          5. si rien n'est inséré, l'opération a déjà été appliquée : on relit
             l'écriture existante, le solde n'est pas retouché, replayed=True ;
          6. report du nouveau solde sur wallets.balance.

        Le rejeu n'est pas une erreur : webhook et callback de retour courent en
        parallèle, et les providers redélivrent leurs événements. Celui qui
        arrive en second retrouve la clé déjà consommée et rend le même solde.
        """
        if direction not in WALLET_DIRECTIONS:
            raise ValueError(f"Invalid wallet direction '{direction}'")
        if entry_type not in WALLET_ENTRY_TYPES:
            raise ValueError(f"Invalid wallet entry_type '{entry_type}'")
        amount = int(amount)
        if amount <= 0:
            raise ValueError("Wallet entry amount must be a positive integer")
        if not idempotency_key:
            raise ValueError("Wallet entry requires an idempotency_key")

        self.get_or_create(customer_id)
        wallet = self.get_for_customer(customer_id, for_update=True)

        if (
            wallet["status"] != "active"
            and entry_type not in WALLET_FROZEN_ALLOWED_ENTRY_TYPES
        ):
            raise WalletFrozenError(f"Wallet {wallet['id']} is {wallet['status']}")

        balance = int(wallet["balance"])
        if direction == "debit":
            if amount > balance:
                raise InsufficientFundsError(balance=balance, required=amount)
            balance_after = balance - amount
        else:
            balance_after = balance + amount

        row = (
            db.session.execute(
                text(
                    """
                    insert into public.wallet_entries (
                        wallet_id,
                        direction,
                        entry_type,
                        amount,
                        balance_after,
                        reference_type,
                        reference_id,
                        idempotency_key,
                        description,
                        metadata
                    )
                    values (
                        cast(:wallet_id as uuid),
                        :direction,
                        :entry_type,
                        :amount,
                        :balance_after,
                        :reference_type,
                        cast(:reference_id as uuid),
                        :idempotency_key,
                        :description,
                        cast(:metadata as jsonb)
                    )
                    on conflict (idempotency_key) do nothing
                    returning *
                    """
                ),
                {
                    "wallet_id": str(wallet["id"]),
                    "direction": direction,
                    "entry_type": entry_type,
                    "amount": amount,
                    "balance_after": balance_after,
                    "reference_type": reference_type,
                    "reference_id": str(reference_id) if reference_id else None,
                    "idempotency_key": idempotency_key,
                    "description": description,
                    "metadata": (
                        json.dumps(metadata, default=str) if metadata is not None else None
                    ),
                },
            )
            .mappings()
            .first()
        )

        if not row:
            existing = self.get_entry_by_idempotency_key(idempotency_key)
            if not existing:
                # Conflit sur une autre contrainte que idempotency_key : ne pas
                # masquer l'anomalie derrière un faux rejeu.
                raise WalletError(
                    f"Wallet entry '{idempotency_key}' was not inserted and cannot be read back"
                )
            existing["replayed"] = True
            return existing

        db.session.execute(
            text(
                """
                update public.wallets
                set balance = :balance_after,
                    updated_at = timezone('utc', now())
                where id = cast(:wallet_id as uuid)
                """
            ),
            {"wallet_id": str(wallet["id"]), "balance_after": balance_after},
        )
        db.session.flush()

        entry = dict(row)
        entry["replayed"] = False
        return entry

    def get_entry_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        row = (
            db.session.execute(
                text(
                    """
                    select *
                    from public.wallet_entries
                    where idempotency_key = :idempotency_key
                    """
                ),
                {"idempotency_key": idempotency_key},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def list_entries(
        self,
        *,
        customer_id: UUID | str,
        limit: int = 20,
        before: Any = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Relevé descendant, paginé par curseur sur created_at.

        Retourne (écritures, has_more). Une ligne de plus que `limit` est lue
        pour savoir s'il reste une page, sans faire de count().
        """
        rows = (
            db.session.execute(
                text(
                    """
                    select e.*
                    from public.wallet_entries e
                    join public.wallets w on w.id = e.wallet_id
                    where w.customer_id = cast(:customer_id as uuid)
                      and (:before is null or e.created_at < cast(:before as timestamptz))
                    order by e.created_at desc, e.id desc
                    limit :limit
                    """
                ),
                {
                    "customer_id": str(customer_id),
                    "before": before,
                    "limit": limit + 1,
                },
            )
            .mappings()
            .all()
        )
        has_more = len(rows) > limit
        return [dict(row) for row in rows[:limit]], has_more

    def sum_entries(
        self,
        *,
        customer_id: UUID | str,
        entry_type: str,
        since_hours: int | None = None,
    ) -> int:
        """Cumul des montants d'un type d'écriture, éventuellement sur une
        fenêtre glissante (plafond journalier de rechargement)."""
        total = db.session.execute(
            text(
                """
                select coalesce(sum(e.amount), 0)
                from public.wallet_entries e
                join public.wallets w on w.id = e.wallet_id
                where w.customer_id = cast(:customer_id as uuid)
                  and e.entry_type = :entry_type
                  and (
                      :since_hours is null
                      or e.created_at > timezone('utc', now())
                         - make_interval(hours => cast(:since_hours as int))
                  )
                """
            ),
            {
                "customer_id": str(customer_id),
                "entry_type": entry_type,
                "since_hours": since_hours,
            },
        ).scalar()
        return int(total or 0)

    # ── rechargements ──────────────────────────────────────────────────────

    def create_topup(
        self,
        *,
        wallet_id: UUID | str,
        customer_id: UUID | str,
        amount: int,
        provider: str,
        provider_reference: str,
        provider_method: str | None = None,
    ) -> dict[str, Any]:
        row = (
            db.session.execute(
                text(
                    """
                    insert into public.wallet_topups (
                        wallet_id,
                        customer_id,
                        amount,
                        currency,
                        provider,
                        provider_method,
                        provider_reference,
                        status
                    )
                    values (
                        cast(:wallet_id as uuid),
                        cast(:customer_id as uuid),
                        :amount,
                        'XOF',
                        :provider,
                        :provider_method,
                        :provider_reference,
                        'pending'
                    )
                    returning *
                    """
                ),
                {
                    "wallet_id": str(wallet_id),
                    "customer_id": str(customer_id),
                    "amount": int(amount),
                    "provider": provider,
                    "provider_method": provider_method,
                    "provider_reference": provider_reference,
                },
            )
            .mappings()
            .one()
        )
        return dict(row)

    def attach_provider_checkout(
        self,
        *,
        topup_id: UUID | str,
        provider_payment_url: str | None,
        raw_provider_response: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Enregistre l'URL de checkout et la réponse brute du provider.

        raw_provider_response porte le provider_payment_id, seule clé acceptée
        par l'API de vérification JEKO au retour de checkout.
        """
        row = (
            db.session.execute(
                text(
                    """
                    update public.wallet_topups
                    set provider_payment_url = :provider_payment_url,
                        raw_provider_response = cast(:raw_provider_response as jsonb),
                        updated_at = timezone('utc', now())
                    where id = cast(:topup_id as uuid)
                    returning *
                    """
                ),
                {
                    "topup_id": str(topup_id),
                    "provider_payment_url": provider_payment_url,
                    "raw_provider_response": (
                        json.dumps(raw_provider_response, default=str)
                        if raw_provider_response is not None
                        else None
                    ),
                },
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def get_topup(self, topup_id: UUID | str) -> dict[str, Any] | None:
        row = (
            db.session.execute(
                text(
                    """
                    select *
                    from public.wallet_topups
                    where id = cast(:topup_id as uuid)
                    """
                ),
                {"topup_id": str(topup_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def get_topup_by_reference(
        self, provider_reference: str, for_update: bool = False
    ) -> dict[str, Any] | None:
        lock_clause = " for update" if for_update else ""
        row = (
            db.session.execute(
                text(
                    f"""
                    select *
                    from public.wallet_topups
                    where provider_reference = :provider_reference{lock_clause}
                    """
                ),
                {"provider_reference": provider_reference},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def list_topups(
        self, *, customer_id: UUID | str, limit: int = 20
    ) -> list[dict[str, Any]]:
        rows = (
            db.session.execute(
                text(
                    """
                    select *
                    from public.wallet_topups
                    where customer_id = cast(:customer_id as uuid)
                    order by created_at desc
                    limit :limit
                    """
                ),
                {"customer_id": str(customer_id), "limit": limit},
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]

    def find_reusable_pending_topup(
        self,
        *,
        customer_id: UUID | str,
        amount: int,
        provider: str,
        provider_method: str | None,
        max_age_minutes: int = 15,
    ) -> dict[str, Any] | None:
        """Rechargement 'pending' récent et identique, à réutiliser plutôt qu'à
        dupliquer (double tap sur le bouton, reprise d'écran). Même esprit que
        SupabasePaymentRepository.create_or_update côté paiement."""
        row = (
            db.session.execute(
                text(
                    """
                    select *
                    from public.wallet_topups
                    where customer_id = cast(:customer_id as uuid)
                      and status = 'pending'
                      and amount = :amount
                      and provider = :provider
                      and provider_method is not distinct from :provider_method
                      and provider_payment_url is not null
                      and created_at > timezone('utc', now())
                          - make_interval(mins => cast(:max_age_minutes as int))
                    order by created_at desc
                    limit 1
                    """
                ),
                {
                    "customer_id": str(customer_id),
                    "amount": int(amount),
                    "provider": provider,
                    "provider_method": provider_method,
                    "max_age_minutes": max_age_minutes,
                },
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def count_topups_since(self, *, customer_id: UUID | str, minutes: int) -> int:
        """Nombre de rechargements créés sur la fenêtre glissante (rate limit)."""
        count = db.session.execute(
            text(
                """
                select count(*)
                from public.wallet_topups
                where customer_id = cast(:customer_id as uuid)
                  and created_at > timezone('utc', now())
                      - make_interval(mins => cast(:minutes as int))
                """
            ),
            {"customer_id": str(customer_id), "minutes": minutes},
        ).scalar()
        return int(count or 0)

    def settle_topup_by_reference(
        self,
        provider_reference: str,
        status: str,
        raw_provider_response: dict[str, Any] | None = None,
        credited: bool = False,
    ) -> dict[str, Any] | None:
        """Pose le statut final d'un rechargement.

        credited=True horodate credited_at (une seule fois : coalesce), ce qui
        matérialise l'adossement entre le topup 'success' et son écriture.
        """
        if status not in TOPUP_STATUSES:
            raise ValueError(f"Invalid topup status '{status}'")
        row = (
            db.session.execute(
                text(
                    """
                    update public.wallet_topups
                    set status = :status,
                        credited_at = case
                            when :credited then coalesce(credited_at, timezone('utc', now()))
                            else credited_at
                        end,
                        raw_provider_response = coalesce(
                            cast(:raw_provider_response as jsonb),
                            raw_provider_response
                        ),
                        updated_at = timezone('utc', now())
                    where provider_reference = :provider_reference
                    returning *
                    """
                ),
                {
                    "provider_reference": provider_reference,
                    "status": status,
                    "credited": credited,
                    "raw_provider_response": (
                        json.dumps(raw_provider_response, default=str)
                        if raw_provider_response is not None
                        else None
                    ),
                },
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def expire_stale_topups(self, *, older_than_minutes: int = 60) -> int:
        """Passe en 'expired' les rechargements restés 'pending' trop longtemps.

        Sans effet sur le solde : un topup non réglé n'a jamais produit
        d'écriture.
        """
        result = db.session.execute(
            text(
                """
                update public.wallet_topups
                set status = 'expired',
                    updated_at = timezone('utc', now())
                where status = 'pending'
                  and created_at < timezone('utc', now())
                      - make_interval(mins => cast(:older_than_minutes as int))
                """
            ),
            {"older_than_minutes": older_than_minutes},
        )
        return result.rowcount

    # ── réconciliation ─────────────────────────────────────────────────────

    def find_balance_divergences(self) -> list[dict[str, Any]]:
        """Wallets dont le solde matérialisé diffère de la somme des écritures.

        Un écart signale un bug de code, pas une donnée à recoller en silence :
        cette méthode constate, elle ne corrige rien.
        """
        rows = (
            db.session.execute(
                text(
                    """
                    select w.id as wallet_id,
                           w.customer_id,
                           w.balance,
                           coalesce(sum(
                               case when e.direction = 'credit' then e.amount
                                    else -e.amount end
                           ), 0) as computed_balance
                    from public.wallets w
                    left join public.wallet_entries e on e.wallet_id = w.id
                    group by w.id, w.customer_id, w.balance
                    having w.balance <> coalesce(sum(
                        case when e.direction = 'credit' then e.amount
                             else -e.amount end
                    ), 0)
                    """
                )
            )
            .mappings()
            .all()
        )
        return [
            {**dict(row), "difference": int(row["balance"]) - int(row["computed_balance"])}
            for row in rows
        ]
