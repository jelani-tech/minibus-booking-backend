"""Repositories du module d'authentification multi-applications.

auth.users (credentials client) reste géré par SupabaseAuthRepository ; ce
module couvre les sessions, le PIN chauffeur, le journal des connexions et le
profil chauffeur.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text

from models.public import db


class SupabaseRefreshTokenRepository:
    """auth.app_refresh_tokens : une ligne par refresh token émis.

    Les lignes d'une même session partagent session_id ; une session est
    active tant qu'elle a une ligne non révoquée et non expirée.
    """

    def create(
        self,
        *,
        session_id: UUID | str,
        user_id: UUID | str,
        audience: str,
        token_hash: str,
        device_id: str | None,
        expires_at: datetime,
    ) -> dict[str, Any]:
        row = (
            db.session.execute(
                text(
                    """
                    insert into auth.app_refresh_tokens
                        (session_id, user_id, audience, token_hash, device_id, expires_at)
                    values (cast(:session_id as uuid), cast(:user_id as uuid), :audience,
                            :token_hash, :device_id, :expires_at)
                    returning *
                    """
                ),
                {
                    "session_id": str(session_id),
                    "user_id": str(user_id),
                    "audience": audience,
                    "token_hash": token_hash,
                    "device_id": device_id,
                    "expires_at": expires_at,
                },
            )
            .mappings()
            .one()
        )
        return dict(row)

    def find_by_hash(self, token_hash: str, for_update: bool = False) -> dict[str, Any] | None:
        """Verrouiller la ligne sérialise deux refresh concurrents du même jeton :
        le second voit la rotation du premier et est traité comme une réutilisation."""
        lock = " for update" if for_update else ""
        row = (
            db.session.execute(
                text(f"select * from auth.app_refresh_tokens where token_hash = :token_hash{lock}"),
                {"token_hash": token_hash},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def revoke(self, token_id: UUID | str, reason: str) -> None:
        db.session.execute(
            text(
                """
                update auth.app_refresh_tokens
                set revoked_at = timezone('utc', now()),
                    revoked_reason = :reason
                where id = cast(:id as uuid)
                  and revoked_at is null
                """
            ),
            {"id": str(token_id), "reason": reason},
        )

    def revoke_session(self, session_id: UUID | str, reason: str) -> int:
        result = db.session.execute(
            text(
                """
                update auth.app_refresh_tokens
                set revoked_at = timezone('utc', now()),
                    revoked_reason = :reason
                where session_id = cast(:session_id as uuid)
                  and revoked_at is null
                """
            ),
            {"session_id": str(session_id), "reason": reason},
        )
        return result.rowcount

    def revoke_user_sessions(self, *, user_id: UUID | str, audience: str, reason: str) -> int:
        result = db.session.execute(
            text(
                """
                update auth.app_refresh_tokens
                set revoked_at = timezone('utc', now()),
                    revoked_reason = :reason
                where user_id = cast(:user_id as uuid)
                  and audience = :audience
                  and revoked_at is null
                """
            ),
            {"user_id": str(user_id), "audience": audience, "reason": reason},
        )
        return result.rowcount

    def is_session_active(self, session_id: UUID | str) -> bool:
        return bool(
            db.session.execute(
                text(
                    """
                    select exists (
                        select 1
                        from auth.app_refresh_tokens
                        where session_id = cast(:session_id as uuid)
                          and revoked_at is null
                          and expires_at > timezone('utc', now())
                    )
                    """
                ),
                {"session_id": str(session_id)},
            ).scalar_one()
        )


class SupabaseUserPinRepository:
    """auth.user_pins : PIN chauffeur, compteur d'échecs, appareil enregistré."""

    def get(self, user_id: UUID | str, for_update: bool = False) -> dict[str, Any] | None:
        """Verrouiller la ligne sérialise les logins concurrents d'un même compte
        (compteur d'échecs, enregistrement du premier appareil)."""
        lock = " for update" if for_update else ""
        row = (
            db.session.execute(
                text(f"select * from auth.user_pins where user_id = cast(:user_id as uuid){lock}"),
                {"user_id": str(user_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def register_failure(self, user_id: UUID | str, *, max_attempts: int) -> dict[str, Any]:
        """Incrémente les échecs et verrouille le compte au seuil."""
        row = (
            db.session.execute(
                text(
                    """
                    update auth.user_pins
                    set failed_attempts = failed_attempts + 1,
                        locked_at = case
                            when failed_attempts + 1 >= :max_attempts
                                then coalesce(locked_at, timezone('utc', now()))
                            else locked_at
                        end,
                        updated_at = timezone('utc', now())
                    where user_id = cast(:user_id as uuid)
                    returning *
                    """
                ),
                {"user_id": str(user_id), "max_attempts": max_attempts},
            )
            .mappings()
            .one()
        )
        return dict(row)

    def register_success(self, user_id: UUID | str, *, device_id: str) -> dict[str, Any]:
        """Remet le compteur d'échecs à zéro et enregistre l'appareil s'il n'y en
        a pas encore."""
        row = (
            db.session.execute(
                text(
                    """
                    update auth.user_pins
                    set failed_attempts = 0,
                        device_registered_at = case
                            when device_id is null then timezone('utc', now())
                            else device_registered_at
                        end,
                        device_id = coalesce(device_id, :device_id),
                        updated_at = timezone('utc', now())
                    where user_id = cast(:user_id as uuid)
                    returning *
                    """
                ),
                {"user_id": str(user_id), "device_id": device_id},
            )
            .mappings()
            .one()
        )
        return dict(row)

    def update_pin(self, user_id: UUID | str, *, pin_hash: str) -> dict[str, Any]:
        row = (
            db.session.execute(
                text(
                    """
                    update auth.user_pins
                    set pin_hash = :pin_hash,
                        must_change_pin = false,
                        failed_attempts = 0,
                        pin_changed_at = timezone('utc', now()),
                        updated_at = timezone('utc', now())
                    where user_id = cast(:user_id as uuid)
                    returning *
                    """
                ),
                {"user_id": str(user_id), "pin_hash": pin_hash},
            )
            .mappings()
            .one()
        )
        return dict(row)


class SupabaseLoginAttemptRepository:
    """auth.login_attempts : journal append-only des tentatives de connexion."""

    def record(
        self,
        *,
        audience: str,
        phone: str,
        success: bool,
        user_id: UUID | str | None = None,
        failure_reason: str | None = None,
        device_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        db.session.execute(
            text(
                """
                insert into auth.login_attempts
                    (user_id, audience, phone, device_id, ip_address, user_agent,
                     success, failure_reason)
                values (cast(:user_id as uuid), :audience, :phone, :device_id, :ip_address,
                        :user_agent, :success, :failure_reason)
                """
            ),
            {
                "user_id": str(user_id) if user_id else None,
                "audience": audience,
                "phone": phone,
                "device_id": device_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "success": success,
                "failure_reason": failure_reason,
            },
        )


class SupabaseDriverRepository:
    def get(self, driver_id: UUID | str) -> dict[str, Any] | None:
        row = (
            db.session.execute(
                text("select * from public.drivers where id = cast(:driver_id as uuid)"),
                {"driver_id": str(driver_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def find_by_auth_user_id(self, auth_user_id: UUID | str) -> dict[str, Any] | None:
        row = (
            db.session.execute(
                text(
                    "select * from public.drivers where auth_user_id = cast(:auth_user_id as uuid)"
                ),
                {"auth_user_id": str(auth_user_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None
