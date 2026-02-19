# Refactoring — Création des tables & Migrations

## Objectif

Remplacer le mécanisme actuel (`db.create_all()` avec imports dispersés) par un flow robuste basé sur **Flask-Migrate (Alembic)** avec un registre de modèles centralisé.

## Problèmes actuels

- `db.create_all()` dépend de l'ordre d'import des modèles → fragile et non déterministe
- `models/vehicles.py` importé **après** `db.create_all()` → table `vehicles` non créée sur BDD vierge
- `models/common.py` **jamais importé** → tables `common.*` jamais créées
- `schema.sql` désynchronisé des modèles Python → source de confusion
- Aucune migration versionnée → impossible de faire évoluer le schéma proprement

---

## Plan de refactoring

### Étape 1 — Centraliser les imports des modèles

- [ ] Créer `models/__init__.py` qui importe explicitement **tous** les modèles
- [ ] Vérifier que chaque modèle est bien listé (public, clients, partners, common, transport, vehicles)

### Étape 2 — Simplifier `database.py`

- [ ] Supprimer `db.create_all()` de `database.py`
- [ ] Conserver uniquement `db.init_app(app)` et la création des schémas PostgreSQL
- [ ] S'assurer que `import models` est fait **avant** `init_db()`

### Étape 3 — Nettoyer `app.py`

- [ ] Remplacer les imports dispersés de modèles par un unique `import models`
- [ ] Déplacer `from routes.vehicles import vehicles_bp` au top-level (comme les autres blueprint imports)
- [ ] Supprimer `import models.transport` (redondant avec `models/__init__.py`)

### Étape 4 — Initialiser Flask-Migrate

- [ ] Exécuter `flask db init` pour créer le dossier `migrations/`
- [ ] Vérifier la configuration Alembic (`migrations/env.py`) et s'assurer qu'il cible les bons schémas
- [ ] Configurer la détection multi-schémas dans `env.py` (`include_schemas=True`)

### Étape 5 — Générer la migration initiale

- [ ] S'assurer que la BDD est dans un état connu (soit vierge, soit existante)
- [ ] **Si BDD existante** : exécuter `flask db migrate -m "Initial migration"` puis `flask db stamp head` pour marquer l'état actuel sans ré-exécuter
- [ ] **Si BDD vierge** : exécuter `flask db migrate -m "Initial migration"` puis `flask db upgrade`

### Étape 6 — Documenter le workflow de migration

- [ ] Ajouter dans le `README.md` les commandes de migration :
  - `flask db migrate -m "description"` — génère un script de migration
  - `flask db upgrade` — applique les migrations pendantes
  - `flask db downgrade` — annule la dernière migration
  - `flask db current` — affiche la migration actuelle
  - `flask db history` — affiche l'historique des migrations

### Étape 7 — Nettoyage

- [ ] Décider du sort de `schema.sql` (supprimer ou archiver comme documentation)
- [ ] Décider du sort de `schema_entre_amis.sql`
- [ ] Commiter le dossier `migrations/` dans Git

---

## Commandes de migration — Aide-mémoire

```bash
# Première initialisation (une seule fois)
flask db init

# Après chaque modification d'un modèle
flask db migrate -m "Ajout colonne X à la table Y"

# Appliquer les migrations en attente
flask db upgrade

# Annuler la dernière migration
flask db downgrade

# Voir l'état actuel
flask db current
flask db history
```

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `models/__init__.py` | **Créer** — registre centralisé |
| `database.py` | **Modifier** — retirer `db.create_all()` |
| `app.py` | **Modifier** — nettoyer les imports |
| `migrations/` | **Créer** — via `flask db init` |
| `schema.sql` | **À décider** — supprimer ou archiver |
| `schema_entre_amis.sql` | **À décider** — supprimer ou archiver |
