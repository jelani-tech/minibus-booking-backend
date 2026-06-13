from html import escape
import os
import requests
from loguru import logger

class BrevoEmailService:
    """Service d'envoi d'e-mails via l'API transactionnelle de Brevo (Sendinblue)."""

    def __init__(self):
        self.api_url = "https://api.brevo.com/v3/smtp/email"
        self.api_key = os.getenv("BREVO_API_KEY")
        self.sender_name = os.getenv("BREVO_SENDER_NAME", "Jelani")
        self.sender_email = os.getenv("BREVO_SENDER_EMAIL", "noreply@jelani.tech")

    def send_reset_otp_email(self, to_email: str, customer_name: str, otp_code: str) -> bool:
        """Envoie un e-mail contenant le code OTP de réinitialisation de mot de passe.

        En environnement de développement local sans clé API Brevo, le code OTP
        est affiché dans les logs de la console.
        """
        subject = "Réinitialisation de votre mot de passe - Jelani"
        safe_customer_name = escape(customer_name)
        safe_otp_code = escape(otp_code)
        
        # HTML Content template
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                    <h2 style="color: #6C63FF; text-align: center;">Jelani Minibus</h2>
                    <p>Bonjour {safe_customer_name},</p>
                    <p>Vous avez demandé la réinitialisation du mot de passe de votre compte Jelani.</p>
                    <p>Veuillez utiliser le code de vérification à 6 chiffres ci-dessous pour procéder au changement :</p>
                    <div style="background-color: #f4f4f9; padding: 15px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 5px; color: #333; margin: 20px 0; border-radius: 4px; border: 1px dashed #6C63FF;">
                        {safe_otp_code}
                    </div>
                    <p>Ce code est valide pendant <strong>15 minutes</strong> et ne peut être utilisé qu'une seule fois.</p>
                    <p>Si vous n'avez pas demandé ce changement, vous pouvez ignorer cet e-mail en toute sécurité.</p>
                    <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                    <p style="font-size: 12px; color: #777; text-align: center;">L'équipe Jelani</p>
                </div>
            </body>
        </html>
        """

        if not self.api_key:
            logger.warning(
                f"⚠️ Clé BREVO_API_KEY non configurée. "
                f"[SIMULATION] OTP pour {to_email} ({customer_name}) : {otp_code}"
            )
            return True

        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json"
        }

        payload = {
            "sender": {
                "name": self.sender_name,
                "email": self.sender_email
            },
            "to": [
                {
                    "email": to_email,
                    "name": customer_name
                }
            ],
            "subject": subject,
            "htmlContent": html_content
        }

        try:
            logger.info(f"Envoi du mail de réinitialisation à {to_email} via Brevo...")
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=10)
            
            if response.status_code in (200, 201, 202):
                logger.info(f"E-mail envoyé avec succès à {to_email}. Message ID: {response.json().get('messageId')}")
                return True
            else:
                logger.error(
                    f"Erreur lors de l'envoi de l'e-mail via Brevo. "
                    f"Status: {response.status_code}, Réponse: {response.text}"
                )
                return False
        except Exception as e:
            logger.exception(f"Exception lors de l'envoi de l'e-mail à {to_email}: {e}")
            return False
