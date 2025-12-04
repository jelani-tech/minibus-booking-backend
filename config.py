import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://user:password@localhost/minibus_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = 86400  # 24 hours
    
    # Payment service API keys
    WAVE_API_KEY = os.environ.get('WAVE_API_KEY') or ''
    WAVE_MERCHANT_KEY = os.environ.get('WAVE_MERCHANT_KEY') or ''
    WAVE_API_URL = os.environ.get('WAVE_API_URL') or 'https://api.wave.com/v1'
    
    ORANGE_MONEY_API_KEY = os.environ.get('ORANGE_MONEY_API_KEY') or ''
    ORANGE_MONEY_MERCHANT_ID = os.environ.get('ORANGE_MONEY_MERCHANT_ID') or ''
    ORANGE_MONEY_API_URL = os.environ.get('ORANGE_MONEY_API_URL') or 'https://api.orange.com/orange-money-webpay'
    
    MTN_MOMO_API_KEY = os.environ.get('MTN_MOMO_API_KEY') or ''
    MTN_MOMO_SUBSCRIPTION_KEY = os.environ.get('MTN_MOMO_SUBSCRIPTION_KEY') or ''
    MTN_MOMO_API_URL = os.environ.get('MTN_MOMO_API_URL') or 'https://sandbox.momodeveloper.mtn.com'

