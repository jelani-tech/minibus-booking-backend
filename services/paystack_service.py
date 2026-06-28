import requests
from flask import jsonify
from loguru import logger

from config import Config


class PaystackService:
    def __init__(self):
        self.secret_key = Config.PAYSTACK_SECRET_KEY
        self.payment_url = Config.PAYSTACK_URL


    def initialize_payment(self, email, amount):
        """
        Initiate payment
        :param email: customer email
        :param amount: amount of payment
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.secret_key}',
                'Content-Type': 'application/json'
            }

            payload = {
                'amount': amount,
                'email': email,
            }

            logger.info(f"Calling Paystack transaction/initialize (amount={amount}, email={email})")

            response = requests.post(
                f'{self.payment_url}/transaction/initialize',
                json= payload,
                headers=headers,
                timeout=60
            )

            if response.status_code == 201 or response.status_code == 200:
                data = response.json().get('data')
                logger.info(
                    f"Paystack payment initialized successfully (reference={data.get('reference')})"
                )
                return {
                    'authorization_url': data.get('authorization_url'),
                    'access_code': data.get('access_code'),
                    'reference': data.get('reference'),
                    'status': 'pending'
                }
            else:
                logger.error(
                    f"Paystack API error (status={response.status_code}): {response.text}"
                )
                raise Exception(f"Error with paystack api: {response.text}")

        except Exception as e:
            logger.exception(f"Failed to initiate Paystack payment (email={email}, amount={amount}): {e}")
            raise Exception(f"Failed to initiate Paystack payment: {str(e)}. Params: {email}, {amount}")



