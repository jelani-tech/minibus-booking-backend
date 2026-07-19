import requests
from loguru import logger

from config import Config


# Moyens de paiement acceptés par l'API JEKO (champ paymentMethod, obligatoire
# dès l'initiation) : contrat avec l'app mobile.
JEKO_PAYMENT_METHODS = ('wave', 'orange', 'mtn', 'moov', 'djamo')


class JekoDuplicateReferenceError(Exception):
    """La référence a déjà été utilisée (409) : l'opération est déjà initiée."""


def normalize_jeko_status(jeko_status) -> str:
    """Mappe un statut JEKO (pending|success|error) vers le vocabulaire canonique
    consommé par settle_payment_from_provider (pending|success|failed)."""
    status = (jeko_status or '').lower()
    if status == 'success':
        return 'success'
    if status == 'error':
        return 'failed'
    return 'pending'


class JekoService:
    def __init__(self):
        self.api_key = Config.JEKO_API_KEY
        self.api_key_id = Config.JEKO_API_KEY_ID
        self.store_id = Config.JEKO_STORE_ID
        self.base_url = (Config.JEKO_URL or '').rstrip('/')

    def _headers(self):
        return {
            'X-API-KEY': self.api_key,
            'X-API-KEY-ID': self.api_key_id,
            'Content-Type': 'application/json',
        }

    def initialize_payment(self, *, amount_cents, reference, payment_method,
                           success_url, error_url):
        """
        Crée une demande de paiement JEKO de type redirect.
        :param amount_cents: montant en sous-unités (int)
        :param reference: référence unique générée par nous
        :param payment_method: wave|orange|mtn|moov|djamo
        :param success_url: URL de redirection après paiement réussi
        :param error_url: URL de redirection après échec
        """
        try:
            payload = {
                'amountCents': amount_cents,
                'currency': 'XOF',
                'reference': reference,
                'storeId': self.store_id,
                'paymentDetails': {
                    'type': 'redirect',
                    'data': {
                        'paymentMethod': payment_method,
                        'successUrl': success_url,
                        'errorUrl': error_url,
                    },
                },
            }

            logger.info(
                f"Calling JEKO payment_requests (amount_cents={amount_cents}, "
                f"reference={reference}, payment_method={payment_method})"
            )

            response = requests.post(
                f'{self.base_url}/payment_requests',
                json=payload,
                headers=self._headers(),
                timeout=60,
            )

            if response.status_code in (200, 201):
                body = response.json()
                logger.info(
                    f"JEKO payment request created (id={body.get('id')}, reference={reference})"
                )
                return {
                    'payment_url': body.get('redirectUrl'),
                    'reference': reference,
                    'provider_payment_id': body.get('id'),
                    'status': 'pending',
                    'raw': body,
                }

            if response.status_code == 409:
                logger.error(f"JEKO API duplicate reference '{reference}': {response.text}")
                raise Exception(f"JEKO duplicate reference '{reference}': {response.text}")

            logger.error(f"JEKO API error (status={response.status_code}): {response.text}")
            raise Exception(f"Error with JEKO api: {response.text}")

        except Exception as e:
            logger.exception(
                f"Failed to initiate JEKO payment (reference={reference}, "
                f"amount_cents={amount_cents}): {e}"
            )
            raise Exception(f"Failed to initiate JEKO payment: {str(e)}")

    def verify_payment(self, payment_request_id):
        """
        Vérifie une demande de paiement JEKO par son id (seul lookup supporté,
        pas de recherche par référence).
        :return: dict normalisé pour settle_payment_from_provider
                 (status, amount en sous-unités, currency, reference, raw)
        """
        logger.info(f"Calling JEKO payment_requests/{payment_request_id} (verify)")

        # Timeout court : l'app mobile attend cette reponse derriere l'ecran de
        # verification avant de poller le statut (cf. PaystackService.verify_payment).
        response = requests.get(
            f'{self.base_url}/payment_requests/{payment_request_id}',
            headers=self._headers(),
            timeout=8,
        )

        if response.status_code == 200:
            body = response.json() or {}
            transaction = body.get('transaction') or {}
            amount = transaction.get('amount') or {}
            logger.info(
                f"JEKO verify response (id={payment_request_id}, status={body.get('status')})"
            )
            return {
                'status': normalize_jeko_status(body.get('status')),
                'amount': int(amount['amount']) if amount.get('amount') is not None else None,
                'currency': amount.get('currency'),
                'reference': body.get('reference'),
                'provider_payment_id': body.get('id'),
                'raw': body,
            }

        logger.error(
            f"JEKO verify API error (id={payment_request_id}, "
            f"status={response.status_code}): {response.text}"
        )
        raise Exception(f"Error with JEKO verify api: {response.text}")

    def create_beneficiary_contact(self, *, name, payment_method, identifier):
        """
        Crée un contact bénéficiaire (destinataire d'un virement).
        :param name: nom du bénéficiaire
        :param payment_method: wave|orange|mtn|moov|djamo|bank
        :param identifier: numéro de téléphone mobile money
        :return: l'id du contact (UUID)
        """
        payload = {
            'name': name,
            'paymentMethod': payment_method,
            'identifier': identifier,
        }

        logger.info(
            f"Calling JEKO contacts (payment_method={payment_method}, identifier={identifier})"
        )

        response = requests.post(
            f'{self.base_url}/contacts',
            json=payload,
            headers=self._headers(),
            timeout=60,
        )

        if response.status_code in (200, 201):
            body = response.json()
            logger.info(f"JEKO beneficiary contact created (id={body.get('id')})")
            return body.get('id')

        logger.error(f"JEKO contacts API error (status={response.status_code}): {response.text}")
        raise Exception(f"Error with JEKO contacts api: {response.text}")

    def create_transfer(self, *, amount_cents, contact_id, reference, description):
        """
        Crée un virement depuis le portefeuille du store vers un contact
        bénéficiaire (utilisé pour les remboursements).
        :param amount_cents: montant en sous-unités (min 500 côté JEKO)
        :param contact_id: id du contact bénéficiaire
        :param reference: référence unique (409 -> JekoDuplicateReferenceError)
        :param description: libellé du virement (max 255)
        """
        payload = {
            'storeId': self.store_id,
            'contactId': contact_id,
            'amountCents': amount_cents,
            'currency': 'XOF',
            'reference': reference,
            'description': description,
        }

        logger.info(
            f"Calling JEKO transfers (amount_cents={amount_cents}, "
            f"contact_id={contact_id}, reference={reference})"
        )

        response = requests.post(
            f'{self.base_url}/transfers',
            json=payload,
            headers=self._headers(),
            timeout=60,
        )

        if response.status_code in (200, 201):
            body = response.json()
            logger.info(
                f"JEKO transfer created (id={body.get('id')}, reference={reference}, "
                f"status={body.get('status')})"
            )
            return {
                'status': normalize_jeko_status(body.get('status')),
                'transfer_id': body.get('id'),
                'reference': reference,
                'raw': body,
            }

        if response.status_code == 409:
            logger.warning(f"JEKO transfer duplicate reference '{reference}': {response.text}")
            raise JekoDuplicateReferenceError(
                f"JEKO transfer already exists with reference '{reference}'"
            )

        logger.error(f"JEKO transfers API error (status={response.status_code}): {response.text}")
        raise Exception(f"Error with JEKO transfers api: {response.text}")

    def get_transfer(self, transfer_id):
        """Récupère un virement par son id (polling/reprise manuelle)."""
        logger.info(f"Calling JEKO transfers/{transfer_id} (status)")

        response = requests.get(
            f'{self.base_url}/transfers/{transfer_id}',
            headers=self._headers(),
            timeout=8,
        )

        if response.status_code == 200:
            body = response.json() or {}
            return {
                'status': normalize_jeko_status(body.get('status')),
                'transfer_id': body.get('id'),
                'reference': body.get('reference'),
                'raw': body,
            }

        logger.error(
            f"JEKO transfer status API error (id={transfer_id}, "
            f"status={response.status_code}): {response.text}"
        )
        raise Exception(f"Error with JEKO transfers api: {response.text}")
