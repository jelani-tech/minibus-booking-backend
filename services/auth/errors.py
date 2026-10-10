class AuthenticationFailed(Exception):
    """Échec de login. `reason` n'est destiné qu'au journal des connexions :
    le client reçoit toujours le même message générique."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class InvalidRefreshToken(Exception):
    """Refresh token inconnu, expiré, révoqué ou réutilisé."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class PinChangeRejected(Exception):
    """Changement de PIN refusé. `code` est stable, pour l'app mobile."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
