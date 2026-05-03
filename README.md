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

1. **(Première fois uniquement)** Initialiser Flask-Migrate et créer la migration initiale:

```bash
export FLASK_APP=app:create_app
flask db init
flask db migrate -m "Initial"
```

Les migrations seront ensuite appliquées automatiquement à chaque démarrage de l'app.

**Si la base existait déjà** (erreur « relation already exists » ou « Target database is not up to date »), aligner Alembic sur l’état actuel sans réexécuter les créations de tables :

```bash
flask db stamp head
```

Ensuite vous pouvez créer de nouvelles migrations (`flask db migrate -m "..."`) et les appliquer au démarrage.

1. Lancer l'application:

```bash
python app.py
```

## Developpement local avec la base miroir Supabase

En developpement, utilisez la base PostgreSQL locale definie par
`docker-compose.local.yml`. Elle evite de toucher a Supabase et reprend le
schema applicatif cible.

### Option recommandee: backend et base dans Docker

```powershell
.\scripts\dev.ps1
```

Equivalent manuel:

```bash
docker compose -f docker-compose.local.yml up -d postgres backend
```

Le backend sera disponible sur `http://localhost:8000`.

### Option alternative: backend local, base dans Docker

Demarrez seulement la base:

```powershell
.\scripts\dev-db.ps1
```

Copiez ensuite le fichier d'environnement de developpement:

```powershell
Copy-Item .env.development.example .env.development
$env:APP_ENV = "development"
python app.py
```

`config.py` charge automatiquement `.env.development` quand `APP_ENV=development`.
La variable importante est:

```text
DATABASE_URL=postgresql://user:password@localhost:5432/minibus_db
```

La base locale initialise les tables `public.partners`, `vehicles`, `drivers`,
`lines`, `stops`, `line_stops`, `trips`, `customers`, `bookings`, `payments`,
les enums, vues et triggers principaux.

`init_db` reste utile pour attacher SQLAlchemy a Flask, mais ne cree plus de
schemas ni n'applique les migrations automatiquement en developpement. Les
migrations Alembic legacy sont opt-in uniquement:

```bash
AUTO_UPGRADE_DB=true LEGACY_SCHEMA_BOOTSTRAP=true python app.py
```

Pour lancer les tests de lecture contre la base locale:

```powershell
.\scripts\test-local.ps1
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
