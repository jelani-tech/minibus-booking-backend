# JELANI - Backend Flask

API backend de l'application JELANI, utilisee par l'application mobile Flutter `../minibus-booking-mobile`. Le backend expose les donnees de lignes, trajets, reservations, authentification client et paiements.

## Etat actuel

- API Flask exposee sur `http://localhost:8000`.
- Authentification JWT pour les clients mobiles.
- Inscription et connexion par numero de telephone.
- Reinitialisation de mot de passe par OTP e-mail via Brevo.
- Lecture des lignes, arrets et trajets via repositories alignes sur le schema Supabase.
- Creation, consultation et annulation de reservations.
- Consultation publique d'un ticket par reference.
- Paiement Paystack avec mode mock automatique en developpement.
- Services legacy Wave, Orange Money et MTN encore presents dans `services/`, mais le flux actif utilise Paystack.
- Docker local disponible pour lancer le backend et une base PostgreSQL miroir.

## Prerequis

- Python 3.9+
- PostgreSQL ou Docker
- pip / virtualenv
- Optionnel: Docker Compose pour l'environnement local recommande

## Installation locale sans Docker

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Sur macOS/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Le serveur ecoute sur `http://localhost:8000`.

## Developpement recommande avec Docker

Backend + base locale:

```powershell
.\scripts\dev.ps1
```

Equivalent manuel:

```bash
docker compose -f docker-compose.local.yml up -d postgres backend
```

Base locale uniquement, backend lance dans le terminal:

```powershell
.\scripts\dev-db.ps1
Copy-Item .env.development.example .env.development
$env:APP_ENV = "development"
python app.py
```

`config.py` charge `.env.development` quand `APP_ENV=development`.

## Configuration

Les variables d'environnement sont listees dans `.env.example` (et `.env.development.example` pour le developpement local). Copier le fichier en `.env` et renseigner les valeurs; ne jamais commiter de vraies cles.

En developpement, le paiement est mocke si `APP_ENV=development` ou si Flask est en debug.

Les variables Wave, Orange Money et MTN restent dans `.env.example` pour compatibilite avec les services legacy.

## Structure

```text
minibus-booking-backend/
|-- app.py                         # Factory Flask, blueprints, healthcheck
|-- config.py                      # Chargement env et configuration Flask
|-- database.py                    # Initialisation SQLAlchemy
|-- application/                   # Serializers API
|-- domain/                        # Entites et contrats repositories
|-- infrastructure/                # Repositories Supabase/read-write
|-- models/                        # Modeles SQLAlchemy par schema
|-- routes/                        # Blueprints REST
|-- services/                      # Paiement, import lignes, e-mail
|-- tests/                         # Tests API
|-- migrations/                    # Migrations Alembic legacy
|-- Dockerfile
`-- requirements.txt
```

## Routes API

### Sante

- `GET /`
- `GET /health`

### Authentification

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me` avec JWT
- `POST /api/auth/reset-password/request`
- `POST /api/auth/reset-password/reset`

### Lignes

- `GET /api/lines/`
- `GET /api/lines/<line_id>`
- `GET /api/lines/<line_id>/stops`

### Trajets

- `GET /api/trips`
- `GET /api/trips/<trip_id>`
- `POST /api/trips` avec JWT admin

Filtres supportes sur `GET /api/trips`:

- `departure_city`
- `arrival_city`
- `date` au format `YYYY-MM-DD`

### Reservations

- `POST /api/bookings` avec JWT
- `GET /api/bookings` avec JWT
- `GET /api/bookings/<booking_id>` avec JWT
- `GET /api/bookings/ticket/<ticket_reference>`
- `DELETE /api/bookings/<booking_id>` avec JWT

### Paiements

- `POST /api/payments/initiate` avec JWT
- `POST /api/payments/webhook`
- `GET /api/payments/status/<booking_id>` avec JWT

### Vehicules

- `GET /api/vehicles` avec JWT admin
- `GET /api/vehicles/available` avec JWT
- `POST /api/vehicles` avec JWT admin
- `PUT /api/vehicles/<vehicle_id>` avec JWT admin

## Exemples rapides

Connexion:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"phone\":\"+2250102030405\",\"password\":\"secret123\"}"
```

Recherche de trajets:

```bash
curl "http://localhost:8000/api/trips?departure_city=Abidjan&arrival_city=Yamoussoukro&date=2026-06-13"
```

Creation d'une reservation:

```bash
curl -X POST http://localhost:8000/api/bookings \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d "{\"trip_id\":\"<UUID>\",\"number_of_seats\":2,\"passenger_name\":\"Jean Dupont\",\"passenger_phone\":\"+2250102030405\"}"
```

Initialisation du paiement:

```bash
curl -X POST http://localhost:8000/api/payments/initiate \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d "{\"booking_id\":\"<UUID>\",\"payment_email\":\"client@example.com\"}"
```

## Tests

```bash
pytest
```

Avec l'environnement local Docker:

```powershell
.\scripts\test-local.ps1
```

## Migrations et schema

Le developpement local s'appuie sur la base miroir definie par `docker-compose.local.yml`. Les migrations Alembic legacy sont opt-in:

```bash
AUTO_UPGRADE_DB=true LEGACY_SCHEMA_BOOTSTRAP=true python app.py
```

Si une base existante est deja alignee mais qu'Alembic n'a pas l'historique:

```bash
flask db stamp head
```

## Deploiement

Exemple Gunicorn:

```bash
gunicorn -w 4 -b 0.0.0.0:8000 "app:create_app()"
```

Prevoir en production:

- `APP_ENV=production`
- secrets forts pour Flask et JWT
- base PostgreSQL geree ou securisee
- configuration Paystack reelle
- webhook paiement expose en HTTPS
- logs applicatifs et supervision
