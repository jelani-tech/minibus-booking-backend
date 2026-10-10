"""Jetons d'accès et sessions, communs à toutes les applications.

- Access token JWT court (JWT_ACCESS_TOKEN_EXPIRES), qui porte :
    sub  l'identifiant du profil (customer_id, driver_id…)
    aud  l'application (cf. services.auth.audiences)
    sid  la session, vérifiée à chaque requête : révoquer une session coupe
         aussi ses access tokens encore valides
    uid  le compte auth.users
- Refresh token opaque (JWT_REFRESH_TOKEN_DAYS), stocké haché, à usage unique :
  chaque refresh le remplace par un nouveau dans la même session.

Le service n'ouvre ni ne valide de transaction : c'est à l'appelant de commit.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import uuid4

from flask import current_app
from flask_jwt_extended import create_access_token

from infrastructure.supabase_auth_repositories import SupabaseRefreshTokenRepository
from services.auth.errors import InvalidRefreshToken

REVOKED_ROTATED = 'rotated'


@dataclass(frozen=True)
class Principal:
    """Titulaire d'un jeton : le profil (identity) et le compte qui le porte."""

    identity: str
    auth_user_id: str
    claims: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    session_id: str

    def to_api(self) -> dict[str, Any]:
        return {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'token_type': 'Bearer',
            'expires_in': self.expires_in,
        }


def hash_refresh_token(refresh_token: str) -> str:
    # Jeton aléatoire de 384 bits : un SHA-256 suffit (pas de dictionnaire
    # possible) et permet la recherche directe par hash.
    return hashlib.sha256(refresh_token.encode()).hexdigest()


class TokenService:
    def __init__(self, repository: SupabaseRefreshTokenRepository | None = None):
        self.repository = repository or SupabaseRefreshTokenRepository()

    def open_session(
        self, principal: Principal, audience: str, *, device_id: str | None = None
    ) -> IssuedTokens:
        return self._issue(principal, audience, session_id=str(uuid4()), device_id=device_id)

    def rotate(
        self,
        refresh_token: str,
        audience: str,
        resolve_principal: Callable[[str], Principal | None],
    ) -> IssuedTokens:
        """Échange un refresh token contre une nouvelle paire de jetons.

        `resolve_principal` recharge le profil depuis la base : un compte
        désactivé depuis l'ouverture de la session n'obtient pas de jeton.
        Lève InvalidRefreshToken ; l'appelant doit tout de même commit, pour
        persister une éventuelle révocation de session.
        """
        row = self.repository.find_by_hash(hash_refresh_token(refresh_token), for_update=True)
        if row is None or row['audience'] != audience:
            raise InvalidRefreshToken('unknown')

        if row['revoked_at'] is not None:
            if row['revoked_reason'] == REVOKED_ROTATED:
                # Un jeton déjà échangé ne doit jamais revenir : il a fuité.
                self.repository.revoke_session(row['session_id'], 'reuse_detected')
                raise InvalidRefreshToken('reused')
            raise InvalidRefreshToken('revoked')

        if row['expires_at'] <= datetime.now(timezone.utc):
            raise InvalidRefreshToken('expired')

        principal = resolve_principal(str(row['user_id']))
        if principal is None:
            self.repository.revoke_session(row['session_id'], 'account_inactive')
            raise InvalidRefreshToken('account_inactive')

        self.repository.revoke(row['id'], REVOKED_ROTATED)
        return self._issue(
            principal, audience, session_id=str(row['session_id']), device_id=row['device_id']
        )

    def access_token(self, principal: Principal, audience: str, *, session_id: str) -> str:
        return create_access_token(
            identity=principal.identity,
            additional_claims={
                **principal.claims,
                'aud': audience,
                'sid': session_id,
                'uid': principal.auth_user_id,
            },
        )

    def revoke_session(self, session_id: str, reason: str) -> None:
        self.repository.revoke_session(session_id, reason)

    def revoke_user_sessions(self, auth_user_id: str, audience: str, reason: str) -> int:
        return self.repository.revoke_user_sessions(
            user_id=auth_user_id, audience=audience, reason=reason
        )

    def is_session_active(self, session_id: str) -> bool:
        return self.repository.is_session_active(session_id)

    def _issue(
        self, principal: Principal, audience: str, *, session_id: str, device_id: str | None
    ) -> IssuedTokens:
        refresh_token = secrets.token_urlsafe(48)
        refresh_ttl = timedelta(days=current_app.config['JWT_REFRESH_TOKEN_DAYS'])
        self.repository.create(
            session_id=session_id,
            user_id=principal.auth_user_id,
            audience=audience,
            token_hash=hash_refresh_token(refresh_token),
            device_id=device_id,
            expires_at=datetime.now(timezone.utc) + refresh_ttl,
        )
        return IssuedTokens(
            access_token=self.access_token(principal, audience, session_id=session_id),
            refresh_token=refresh_token,
            expires_in=int(current_app.config['JWT_ACCESS_TOKEN_EXPIRES'].total_seconds()),
            session_id=session_id,
        )
