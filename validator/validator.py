class Validator:
    @staticmethod
    def validate_password(password: str) -> bool:
        if len(password) >= 6:
            return True
        else:
            raise ValidationException("Le mot de passe doit contenir au moins 6 caractères")

class ValidationException(Exception):
    def __init__(self, message):
        self.message = message

    def getMessage(self):
        return self.message