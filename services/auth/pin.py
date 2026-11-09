"""PIN chauffeur : format, hachage et vérification.

Le PIN est haché avec bcrypt, comme le mot de passe client : 6 chiffres ne
font que 10⁶ combinaisons, c'est le coût de bcrypt et le verrouillage après
5 échecs qui les protègent.
"""

import bcrypt

PIN_LENGTH = 6

# Hash factice, vérifié quand le compte est inconnu : le temps de réponse ne
# révèle pas si le numéro de téléphone correspond à un chauffeur.
_DUMMY_PIN_HASH = bcrypt.hashpw(b'000000', bcrypt.gensalt()).decode()


def is_valid_pin_format(pin: str) -> bool:
    return len(pin) == PIN_LENGTH and pin.isascii() and pin.isdigit()


def is_trivial_pin(pin: str) -> bool:
    """Chiffres tous identiques (000000) ou suite continue (123456, 654321)."""
    steps = {int(b) - int(a) for a, b in zip(pin, pin[1:])}
    return steps in ({0}, {1}, {-1})


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, pin_hash: str | None) -> bool:
    if not pin_hash:
        bcrypt.checkpw(pin.encode(), _DUMMY_PIN_HASH.encode())
        return False
    return bcrypt.checkpw(pin.encode(), pin_hash.encode())
