# Collection Bruno - Minibus Booking API

Cette collection Bruno contient tous les endpoints de l'API de réservation de minibus.

## Installation

1. Installez [Bruno](https://www.usebruno.com/)
2. Ouvrez Bruno et importez le dossier `minibus-booking-api`

## Configuration

### Variables d'environnement

La collection utilise les variables suivantes (définies dans `env.json`) :

- `baseUrl` : URL de base de l'API (par défaut: `http://localhost:8000`)
- `token` : Token JWT pour l'authentification (à remplir après connexion)

### Utilisation

1. **Démarrer l'API** : Assurez-vous que l'API est en cours d'exécution sur `http://localhost:8000`

2. **S'inscrire/Se connecter** :
   - Utilisez l'endpoint `Register` pour créer un compte
   - Utilisez l'endpoint `Login` pour vous connecter
   - **Important** : Copiez le `access_token` reçu et collez-le dans la variable `token` dans l'onglet "Environnement" de Bruno

3. **Tester les endpoints** :
   - Les endpoints sont organisés par catégorie (Auth, Trips, Bookings, Payments, Health)
   - Les endpoints protégés nécessitent le token JWT dans le header `Authorization`

## Structure

```
minibus-booking-api/
├── Auth/
│   ├── Register.bru
│   ├── Login.bru
│   └── Get Current User.bru
├── Trips/
│   ├── Get All Trips.bru
│   ├── Get Trip by ID.bru
│   └── Create Trip.bru
├── Bookings/
│   ├── Create Booking.bru
│   ├── Get User Bookings.bru
│   ├── Get Booking by ID.bru
│   └── Cancel Booking.bru
├── Payments/
│   ├── Initiate Payment.bru
│   ├── Get Payment Status.bru
│   └── Payment Webhook.bru
└── Health/
    ├── Health Check.bru
    └── API Root.bru
```

## Ordre recommandé de test

1. Health Check → Vérifier que l'API fonctionne
2. Register → Créer un compte
3. Login → Se connecter et récupérer le token
4. Get Current User → Vérifier l'authentification
5. Create Trip → Créer un trajet (nécessite authentification)
6. Get All Trips → Lister les trajets
7. Create Booking → Créer une réservation
8. Get User Bookings → Voir ses réservations
9. Initiate Payment → Initier un paiement
10. Get Payment Status → Vérifier le statut du paiement

