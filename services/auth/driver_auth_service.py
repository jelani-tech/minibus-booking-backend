"""Authentification des chauffeurs : téléphone + PIN, compte lié à un appareil.

- Tout échec de login lève AuthenticationFailed avec une raison qui ne va que
  dans le journal (auth.login_attempts) : la route renvoie toujours le même 401.
- 5 PIN incorrects verrouillent le compte ; seul un reset PIN admin débloque.
- Le premier login réussi enregistre l'appareil ; un autre appareil est refusé.
- Un login réussi révoque les sessions précédentes : une seule session chauffeur.

Le service n'ouvre ni ne valide de transaction : c'est à l'appelant de commit,
y compris après un échec (pour conserver le journal et le compteur d'échecs).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import current_app

from infrastructure.supabase_auth_repositories import (
    SupabaseDriverRepository,
    SupabaseLoginAttemptRepository,
    SupabaseUserPinRepository,
)
from infrastructure.supabase_write_repositories import SupabaseAuthRepository
from services.auth.audiences import DRIVER_APP
from services.auth.errors import AuthenticationFailed, PinChangeRejected
from services.auth.pin import hash_pin, is_trivial_pin, is_valid_pin_format, verify_pin
from services.auth.token_service import IssuedTokens, Principal, TokenService

DRIVER_ACTIVE_STATUS = 'active'


@dataclass(frozen=True)
class LoginContext:
    phone: str
    device_id: str
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True)
class DriverLogin:
    driver: dict[str, Any]
    tokens: IssuedTokens
    must_change_pin: bool


def driver_principal(driver: dict[str, Any], credentials: dict[str, Any]) -> Principal:
    return Principal(
        identity=str(driver['id']),
        auth_user_id=str(driver['auth_user_id']),
        claims={'must_change_pin': bool(credentials['must_change_pin'])},
    )


class DriverAuthService:
    def __init__(
        self,
        *,
        auth_repository: SupabaseAuthRepository | None = None,
        driver_repository: SupabaseDriverRepository | None = None,
        pin_repository: SupabaseUserPinRepository | None = None,
        login_attempts: SupabaseLoginAttemptRepository | None = None,
        token_service: TokenService | None = None,
    ):
        self.auth_repository = auth_repository or SupabaseAuthRepository()
        self.driver_repository = driver_repository or SupabaseDriverRepository()
        self.pin_repository = pin_repository or SupabaseUserPinRepository()
        self.login_attempts = login_attempts or SupabaseLoginAttemptRepository()
        self.token_service = token_service or TokenService()

    # ── Login ───────────────────────────────────────────────────────────────

    def login(self, context: LoginContext, pin: str) -> DriverLogin:
        auth_user = self.auth_repository.find_by_phone(context.phone)
        user_id = str(auth_user['id']) if auth_user else None
        driver = self.driver_repository.find_by_auth_user_id(user_id) if user_id else None
        credentials = self.pin_repository.get(user_id, for_update=True) if driver else None

        if credentials is None:
            verify_pin(pin, None)
            self._fail(context, user_id, 'unknown_account')

        if credentials['locked_at'] is not None:
            self._fail(context, user_id, 'locked')

        if not verify_pin(pin, credentials['pin_hash']):
            self._fail(context, user_id, self._register_pin_failure(user_id))

        if driver['status'] != DRIVER_ACTIVE_STATUS:
            self._fail(context, user_id, 'driver_inactive')

        if credentials['device_id'] and credentials['device_id'] != context.device_id:
            self._fail(context, user_id, 'unknown_device')

        credentials = self.pin_repository.register_success(user_id, device_id=context.device_id)
        self.token_service.revoke_user_sessions(user_id, DRIVER_APP, 'new_login')
        tokens = self.token_service.open_session(
            driver_principal(driver, credentials), DRIVER_APP, device_id=context.device_id
        )
        self._record(context, user_id, success=True)

        return DriverLogin(
            driver=driver,
            tokens=tokens,
            must_change_pin=bool(credentials['must_change_pin']),
        )

    # ── Changement de PIN ───────────────────────────────────────────────────

    def change_pin(
        self, *, driver_id: str, session_id: str, current_pin: str, new_pin: str
    ) -> str:
        """Remplace le PIN et retourne un access token à jour (must_change_pin
        levé) pour la session en cours. Un PIN actuel incorrect compte comme
        un échec de login."""
        if not is_valid_pin_format(new_pin):
            raise PinChangeRejected(
                'invalid_pin_format', 'Le nouveau PIN doit contenir exactement 6 chiffres'
            )
        if is_trivial_pin(new_pin):
            raise PinChangeRejected(
                'weak_pin', 'Choisissez un PIN moins prévisible que 000000 ou 123456'
            )

        driver = self.driver_repository.get(driver_id)
        credentials = self.pin_repository.get(driver['auth_user_id'], for_update=True)

        if not verify_pin(current_pin, credentials['pin_hash']):
            self._register_pin_failure(str(driver['auth_user_id']))
            raise PinChangeRejected('invalid_current_pin', 'Le PIN actuel est incorrect')

        if new_pin == current_pin:
            raise PinChangeRejected(
                'pin_unchanged', "Le nouveau PIN doit être différent de l'actuel"
            )

        credentials = self.pin_repository.update_pin(
            driver['auth_user_id'], pin_hash=hash_pin(new_pin)
        )
        return self.token_service.access_token(
            driver_principal(driver, credentials), DRIVER_APP, session_id=session_id
        )

    # ── Refresh ─────────────────────────────────────────────────────────────

    def refresh(self, refresh_token: str) -> IssuedTokens:
        return self.token_service.rotate(refresh_token, DRIVER_APP, self._active_principal)

    def _active_principal(self, auth_user_id: str) -> Principal | None:
        driver = self.driver_repository.find_by_auth_user_id(auth_user_id)
        credentials = self.pin_repository.get(auth_user_id)
        if (
            driver is None
            or credentials is None
            or driver['status'] != DRIVER_ACTIVE_STATUS
            or credentials['locked_at'] is not None
        ):
            return None
        return driver_principal(driver, credentials)

    # ── Interne ─────────────────────────────────────────────────────────────

    def _register_pin_failure(self, user_id: str) -> str:
        """Incrémente les échecs ; au verrouillage, coupe aussi les sessions."""
        credentials = self.pin_repository.register_failure(
            user_id, max_attempts=current_app.config['DRIVER_PIN_MAX_ATTEMPTS']
        )
        if credentials['locked_at'] is None:
            return 'invalid_pin'
        self.token_service.revoke_user_sessions(user_id, DRIVER_APP, 'locked')
        return 'invalid_pin_locked'

    def _fail(self, context: LoginContext, user_id: str | None, reason: str) -> None:
        self._record(context, user_id, success=False, failure_reason=reason)
        raise AuthenticationFailed(reason)

    def _record(
        self,
        context: LoginContext,
        user_id: str | None,
        *,
        success: bool,
        failure_reason: str | None = None,
    ) -> None:
        self.login_attempts.record(
            audience=DRIVER_APP,
            phone=context.phone,
            user_id=user_id,
            success=success,
            failure_reason=failure_reason,
            device_id=context.device_id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
        )
