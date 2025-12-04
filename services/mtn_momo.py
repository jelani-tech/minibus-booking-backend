import requests
from flask import current_app
from config import Config
import uuid
import base64
from datetime import datetime

class MTNMomoService:
    def __init__(self):
        self.api_key = Config.MTN_MOMO_API_KEY
        self.subscription_key = Config.MTN_MOMO_SUBSCRIPTION_KEY
        self.api_url = Config.MTN_MOMO_API_URL
    
    def get_access_token(self):
        """
        Get access token for MTN Mobile Money API
        """
        try:
            # Encode API key
            encoded_key = base64.b64encode(f"{self.api_key}:".encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_key}',
                'Ocp-Apim-Subscription-Key': self.subscription_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f'{self.api_url}/collection/token/',
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('access_token')
            else:
                raise Exception(f"MTN API token error: {response.text}")
                
        except Exception as e:
            raise Exception(f"Failed to get MTN access token: {str(e)}")
    
    def initiate_payment(self, amount, phone, transaction_id):
        """
        Initiate a payment with MTN Mobile Money
        Documentation: https://momodeveloper.mtn.com/docs
        """
        try:
            access_token = self.get_access_token()
            
            # Format phone number (remove + and ensure it starts with country code)
            formatted_phone = phone.replace('+', '').replace(' ', '')
            if not formatted_phone.startswith('225'):  # Côte d'Ivoire code
                formatted_phone = f'225{formatted_phone}'
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Ocp-Apim-Subscription-Key': self.subscription_key,
                'X-Target-Environment': 'sandbox',  # Change to 'production' in production
                'Content-Type': 'application/json',
                'X-Reference-Id': str(uuid.uuid4()),
                'X-Callback-Url': f'{current_app.config.get("BASE_URL", "http://localhost:5000")}/api/payments/webhook'
            }
            
            payload = {
                'amount': str(amount),
                'currency': 'XOF',
                'externalId': transaction_id,
                'payer': {
                    'partyIdType': 'MSISDN',
                    'partyId': formatted_phone
                },
                'payerMessage': f'Payment for booking {transaction_id}',
                'payeeNote': f'Minibus booking payment'
            }
            
            response = requests.post(
                f'{self.api_url}/collection/v1_0/requesttopay',
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 202:
                reference_id = headers.get('X-Reference-Id')
                return {
                    'transaction_id': reference_id,
                    'payment_url': None,  # MTN doesn't provide payment URL
                    'status': 'pending'
                }
            else:
                raise Exception(f"MTN API error: {response.text}")
                
        except Exception as e:
            raise Exception(f"Failed to initiate MTN payment: {str(e)}")
    
    def verify_payment(self, transaction_id):
        """
        Verify payment status with MTN Mobile Money
        """
        try:
            access_token = self.get_access_token()
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Ocp-Apim-Subscription-Key': self.subscription_key,
                'X-Target-Environment': 'sandbox'
            }
            
            response = requests.get(
                f'{self.api_url}/collection/v1_0/requesttopay/{transaction_id}',
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
                raise Exception(f"MTN API error: {response.text}")
                
        except Exception as e:
            raise Exception(f"Failed to verify MTN payment: {str(e)}")

