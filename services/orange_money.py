import requests
from flask import current_app
from config import Config
import base64

class OrangeMoneyService:
    def __init__(self):
        self.api_key = Config.ORANGE_MONEY_API_KEY
        self.merchant_id = Config.ORANGE_MONEY_MERCHANT_ID
        self.api_url = Config.ORANGE_MONEY_API_URL
    
    def initiate_payment(self, amount, phone, transaction_id):
        """
        Initiate a payment with Orange Money
        Documentation: https://developer.orange.com/apis/orange-money-web/api-reference
        """
        try:
            # Encode credentials
            credentials = f"{self.merchant_id}:{self.api_key}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            payload = {
                'merchant_key': self.merchant_id,
                'currency': 'XOF',
                'order_id': transaction_id,
                'amount': amount,
                'return_url': f'{current_app.config.get("BASE_URL", "http://localhost:5000")}/api/payments/webhook',
                'cancel_url': f'{current_app.config.get("BASE_URL", "http://localhost:5000")}/api/payments/cancel',
                'notif_url': f'{current_app.config.get("BASE_URL", "http://localhost:5000")}/api/payments/webhook',
                'lang': 'fr',
                'reference': transaction_id
            }
            
            response = requests.post(
                f'{self.api_url}/ci/v1/webpayment',
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 201 or response.status_code == 200:
                data = response.json()
                return {
                    'transaction_id': data.get('pay_token') or transaction_id,
                    'payment_url': data.get('payment_url'),
                    'status': 'pending'
                }
            else:
                raise Exception(f"Orange Money API error: {response.text}")
                
        except Exception as e:
            raise Exception(f"Failed to initiate Orange Money payment: {str(e)}")
    
    def verify_payment(self, transaction_id):
        """
        Verify payment status with Orange Money
        """
        try:
            credentials = f"{self.merchant_id}:{self.api_key}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f'{self.api_url}/ci/v1/transactionstatus',
                params={'order_id': transaction_id},
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'status': data.get('status'),
                    'transaction_id': transaction_id
                }
            else:
                raise Exception(f"Orange Money API error: {response.text}")
                
        except Exception as e:
            raise Exception(f"Failed to verify Orange Money payment: {str(e)}")

