# Minibus Booking Backend API

Backend API pour l'application de réservation de minibus en Côte d'Ivoire.

## Technologies

- Python 3.9+
- Flask 2.3.3
- PostgreSQL
- Flask-JWT-Extended pour l'authentification
- Intégration des paiements Mobile Money (Wave, Orange Money, MTN)

## Installation

1. Créer un environnement virtuel:

```bash
python3 -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate
```

1. Installer les dépendances:

```bash
pip install -r requirements.txt
```

1. Configurer les variables d'environnement:

```bash
cp .env.example .env
# Éditer .env avec vos valeurs
```

1. Créer la base de données PostgreSQL:

```sql
CREATE DATABASE minibus_db;
```

1. Lancer l'application:

```bash
python app.py
```

## Structure du projet

```text
minibus-booking-backend/
├── app.py                 # Point d'entrée de l'application
├── config.py              # Configuration
├── database.py            # Initialisation de la base de données
├── models.py              # Modèles SQLAlchemy
├── requirements.txt       # Dépendances Python
├── routes/
│   ├── auth.py           # Routes d'authentification
│   ├── trip.py           # Routes des trajets
│   ├── booking.py        # Routes de réservation
│   └── payment.py        # Routes de paiement
└── services/
    ├── wave_payment.py   # Service Wave
    ├── orange_money.py   # Service Orange Money
    └── mtn_momo.py       # Service MTN Mobile Money
```

## Endpoints API

### Authentification

- `POST /api/auth/register` - Inscription
- `POST /api/auth/login` - Connexion
- `GET /api/auth/me` - Informations utilisateur (requiert JWT)

### Trajets

- `GET /api/trips` - Liste des trajets (filtres: departure_city, arrival_city, date)
- `GET /api/trips/<id>` - Détails d'un trajet
- `POST /api/trips` - Créer un trajet (requiert JWT)

### Réservations

- `POST /api/bookings` - Créer une réservation (requiert JWT)
- `GET /api/bookings` - Liste des réservations de l'utilisateur (requiert JWT)
- `GET /api/bookings/<id>` - Détails d'une réservation (requiert JWT)
- `DELETE /api/bookings/<id>` - Annuler une réservation (requiert JWT)

### Paiements

- `POST /api/payments/initiate` - Initier un paiement (requiert JWT)
- `POST /api/payments/webhook` - Webhook pour les notifications de paiement
- `GET /api/payments/status/<booking_id>` - Statut du paiement (requiert JWT)

## Déploiement

### Backend

1. Installer les dépendances système:

```bash
sudo apt-get update
sudo apt-get install python3-pip python3-venv postgresql
```

1. Configurer PostgreSQL et créer la base de données

1. Utiliser Gunicorn pour la production:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

1. Configurer Nginx comme reverse proxy (optionnel)
