import requests
from flask import current_app
from config import Config

class WavePaymentService:
    def __init__(self):
        self.api_key = Config.WAVE_API_KEY
        self.merchant_key = Config.WAVE_MERCHANT_KEY
        self.api_url = Config.WAVE_API_URL
    
    def initiate_payment(self, amount, phone, transaction_id):
        """
        Initiate a payment with Wave
        Documentation: https://developer.wave.com/docs/payments
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'amount': amount,
                'currency': 'XOF',
                'phone': phone,
                'merchant_reference': transaction_id,
                'callback_url': f'{current_app.config.get("BASE_URL", "http://localhost:5000")}/api/payments/webhook'
            }
            
            response = requests.post(
                f'{self.api_url}/payments',
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 201:
                data = response.json()
                return {
                    'transaction_id': data.get('id'),
                    'payment_url': data.get('payment_url'),
                    'status': 'pending'
                }
            else:
                raise Exception(f"Wave API error: {response.text}")
                
        except Exception as e:
            raise Exception(f"Failed to initiate Wave payment: {str(e)}")
    
    def verify_payment(self, transaction_id):
        """
        Verify payment status with Wave
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f'{self.api_url}/payments/{transaction_id}',
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'status': data.get('status'),
                    'transaction_id': data.get('id')
                }
            else:
                raise Exception(f"Wave API error: {response.text}")
                
        except Exception as e:
            raise Exception(f"Failed to verify Wave payment: {str(e)}")

