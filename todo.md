# TODO

## 🚨 Haute Priorité (Critique pour la stabilité)
- [ ] **Refactoriser les Modèles de Données** :
    - Décider du schéma définitif (Fusionner `public` et `clients` ou finaliser la séparation).
    - Supprimer les modèles marqués "TO BE DELETED" ou migrer entièrement les `routes` pour utiliser les nouveaux modèles dans `clients.py` (et créer le modèle `Booking` manquant là-bas).
- [ ] **Migrations de Base de Données** :
    - Initialiser `Flask-Migrate` (Alembic) pour gérer les changements de schéma de manière fiable.
    - Créer le script de migration initial.
- [ ] **Sécurité de la Configuration** :
    - S'assurer que tous les secrets (Mot de passe BDD, Secret JWT) sont chargés strictement depuis `.env`.
    - Créer un `.env.template` pour les développeurs.

## 🛠 Moyenne Priorité (Qualité du code & Fiabilité)
- [ ] **Gestion Globale des Erreurs** :
    - Créer un `ErrorHandler` pour intercepter les exceptions (404, 500, Erreurs de validation) et retourner des structures JSON cohérentes.
- [ ] **Validation des Entrées** :
    - Remplacer les vérifications manuelles `if not data.get(...)` par des schémas `Marshmallow` ou `Pydantic` pour une validation robuste.
- [ ] **Système de Logging** :
    - Configurer un logging structuré (format JSON préféré) pour un débogage facile en production.
- [ ] **Documentation API** :
    - Mettre en place `Swagger`/`OpenAPI` (via `flasgger` ou `flask-restx`) pour générer la documentation automatiquement pour l'équipe frontend.

## 🚀 Basse Priorité (Améliorations)
- [ ] **Suite de Tests** :
    - Mettre en place `pytest`.
    - Écrire au moins un test fonctionnel pour le "Flux de Réservation" (Happy Path).
- [ ] **Configuration Docker pour la Production** :
    - Vérifier que le `Dockerfile` fonctionne avec `Gunicorn`.
    - S'assurer que `docker-compose.prod.yml` existe.

## ✅ Complété
- [x] Analyser l'état actuel de la base de code pour identifier les besoins du MVP.