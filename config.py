import os
from dotenv import load_dotenv

env_file = os.environ.get('ENV_FILE')
if env_file:
    load_dotenv(env_file)
elif os.environ.get('APP_ENV') == 'development' and os.path.exists('.env.development'):
    load_dotenv('.env.development')
else:
    load_dotenv()

class Config:
    APP_ENV = os.environ.get('APP_ENV', 'development')
    # Pas de valeur par défaut codée en dur : une clé absente doit être détectée
    # au démarrage (cf. _require_secrets dans app.py) plutôt que de retomber
    # silencieusement sur un secret devinable.
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://user:password@localhost/minibus_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    AUTO_UPGRADE_DB = os.environ.get('AUTO_UPGRADE_DB', 'false').lower() == 'true'
    LEGACY_SCHEMA_BOOTSTRAP = os.environ.get('LEGACY_SCHEMA_BOOTSTRAP', 'false').lower() == 'true'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
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

    PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY') or ''
    PAYSTACK_URL = os.environ.get('PAYSTACK_URL') or ''
    PAYMENT_EMAIL_DOMAIN = os.environ.get('PAYMENT_EMAIL_DOMAIN') or 'jelani.tech'

    # Provider utilisé pour les NOUVELLES initiations de paiement ('paystack' ou
    # 'jeko'). Les webhooks/callbacks des deux providers restent toujours actifs
    # pour que les paiements en cours de l'autre provider soient réglés.
    PAYMENT_PROVIDER = (os.environ.get('PAYMENT_PROVIDER') or 'paystack').lower()

    JEKO_API_KEY = os.environ.get('JEKO_API_KEY') or ''
    JEKO_API_KEY_ID = os.environ.get('JEKO_API_KEY_ID') or ''
    JEKO_STORE_ID = os.environ.get('JEKO_STORE_ID') or ''
    JEKO_WEBHOOK_SECRET = os.environ.get('JEKO_WEBHOOK_SECRET') or ''
    JEKO_URL = os.environ.get('JEKO_URL') or 'https://api.jeko.africa/partner_api'
    # Base publique de l'API, pour construire les successUrl/errorUrl exigées par
    # JEKO à l'initiation (ex: https://minibus-booking.onrender.com).
    PAYMENT_PUBLIC_BASE_URL = (os.environ.get('PAYMENT_PUBLIC_BASE_URL') or '').rstrip('/')

