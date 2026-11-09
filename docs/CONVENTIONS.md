# Conventions de code — JELANI backend

Document de référence pour les développeurs **et** les agents IA qui travaillent
sur ce dépôt. Il décrit le projet, les conventions déjà en place (à respecter)
et les bonnes pratiques recommandées (à appliquer au code neuf).

> Règle d'or : **le code neuf ressemble au code récent** (`routes/wallet.py`,
> `routes/driver.py`, `services/auth/`, `infrastructure/supabase_auth_repositories.py`),
> pas au code legacy (`models/`, `routes/trip.py` POST, `routes/vehicles.py`,
> `services/wave_payment.py`, `orange_money.py`, `mtn_momo.py`).

---

## 1. Le projet

JELANI est une plateforme de réservation de minibus interurbains (Côte d'Ivoire,
monnaie XOF). Ce dépôt est l'**API backend Flask**, consommée par :

- l'app mobile client Flutter (`../minibus-booking-mobile`) — audience `customer-app` ;
- l'app chauffeur — audience `driver-app` ;
- un futur back-office admin — audience `admin-app` (routes admin pas encore implémentées).

Domaines fonctionnels :

| Domaine | Fichiers principaux |
|---|---|
| Lignes, arrêts, trajets (lecture) | `routes/lines.py`, `routes/trip.py`, `infrastructure/supabase_read_repositories.py` |
| Auth client (téléphone + mot de passe, OTP e-mail) | `routes/auth.py`, `routes/auth_sessions.py` |
| Auth chauffeur (téléphone + PIN, appareil lié) | `routes/driver.py`, `services/auth/` |
| Réservations | `routes/booking.py` |
| Paiements (Paystack, JEKO), webhooks, callback | `routes/payment.py`, `services/paystack_service.py`, `services/jeko_service.py` |
| Remboursements | `services/refund_service.py` |
| Wallet client (porte-monnaie fermé) | `routes/wallet.py`, `SupabaseWalletRepository` |

### Stack

- Python 3.12 en prod (image Docker), 3.10 dans le venv local — **le code doit rester compatible 3.10**.
- Flask 2.3, Flask-JWT-Extended, Flask-SQLAlchemy (utilisé surtout comme pool de connexions/session), Flask-Migrate/Alembic.
- PostgreSQL hébergé sur **Supabase** (schémas `public`, `auth`, `app_auth`).
- Logs : `loguru` + Better Stack (Logtail).
- E-mails transactionnels : Brevo.
- Prod : Render (plan gratuit, 1 instance, 512 Mo), Docker + gunicorn (`Dockerfile`).

---

## 2. Architecture et rôle de chaque couche

```
routes/          HTTP : parsing, validation d'entrée, auth, transaction (commit/rollback), réponse JSON
services/        Logique métier et intégrations externes (providers de paiement, e-mail, auth)
infrastructure/  Accès base : SQL brut via sqlalchemy.text(), une classe Supabase*Repository par agrégat
domain/          Entités (dataclasses gelées), enums de statuts, Protocols de repositories, mapping row -> entité
application/     Sérialiseurs : entité / row -> dict JSON exposé par l'API (*_to_api)
models/          LEGACY — modèles SQLAlchemy ORM, ne plus utiliser (sauf l'objet `db`)
migrations/      Alembic, révisions en SQL brut via op.execute()
local_db/        Schéma + seed de la base locale Docker (miroir de Supabase)
tests/           Tests d'intégration unittest sur une vraie base Postgres
```

Sens des dépendances : `routes → services → infrastructure → domain`, et
`routes → application`. Les couches basses n'importent jamais `flask.request`
ni ne construisent de réponse HTTP.

### Règles clés

- **Le schéma physique appartient à Supabase**, pas à l'ORM. Les accès base se
  font en **SQL brut paramétré** dans `infrastructure/`, pas via les modèles de `models/`.
- `models/public.py` n'est importé que pour `db` (`from models.public import db`).
  Les classes ORM (`User`, `ScheduledTrip`, …) sont des reliques : ne pas en
  ajouter, ne pas s'appuyer dessus dans du code neuf.
- Les repositories d'écriture retournent des `dict` (rows), les repositories de
  lecture peuvent retourner des entités du `domain`. Les deux formes existent ;
  suivre celle du repository que l'on étend.

---

## 3. Conventions de nommage

| Élément | Convention | Exemples |
|---|---|---|
| Modules, fonctions, variables | `snake_case` | `refund_service.py`, `parse_xof_amount` |
| Classes | `PascalCase` | `SupabaseWalletRepository`, `DriverAuthService` |
| Constantes de module | `UPPER_SNAKE_CASE`, en tête de module | `TOPUP_REFERENCE_PREFIX`, `TRANSACTIONS_MAX_LIMIT` |
| Helpers privés | préfixe `_` | `_client_ip`, `_initiate_jeko`, `_require_secrets` |
| Blueprints | `<domaine>_bp`, `url_prefix='/api/<domaine>'` | `wallet_bp`, `booking_bp` |
| Repositories | `Supabase<Agrégat>Repository` | `SupabaseBookingRepository` |
| Instances de repo/service dans une route | `<nom>_repository`, `<nom>_service`, au niveau module | `wallet_repository = SupabaseWalletRepository()` |
| Sérialiseurs | `<objet>_to_api` / `<objet>_row_to_api` | `topup_row_to_api`, `line_to_api` |
| Mapping base → domaine | `<objet>_from_row` | `line_from_row` |
| Exceptions | `<Quoi>Error` ou nom explicite | `WalletFrozenError`, `AuthenticationFailed` |
| Références de transaction | préfixe par type | `TU-` rechargement, `WL-` paiement wallet, `RF-` remboursement |
| Variables d'env | `UPPER_SNAKE_CASE`, préfixées par domaine | `WALLET_*`, `JEKO_*`, `JWT_*` |
| Champs JSON de l'API | `snake_case` | `number_of_seats`, `next_before` |
| Identifiants | UUID partout ; `str(uuid)` dans le JSON et les paramètres SQL | `cast(:id as uuid)` |

---

## 4. Langue

- **Docstrings et commentaires : en français.** Ils expliquent le *pourquoi*
  (règle métier, contrainte provider, raison d'un ordre d'opérations), pas le *quoi*.
- **Messages de log : en anglais**, au format `"<Action> <résultat> (clé=valeur, …)"`.
- **Messages d'erreur renvoyés au client : en français, sans aucun détail
  technique** (pas de `str(e)`, de SQL, de nom de table/colonne, de trace, de
  réponse brute d'un provider, ni de nom de variable d'env). Le message doit
  être compréhensible par l'utilisateur final ; le détail technique va dans les
  logs. L'app mobile ne doit jamais interpréter le texte : elle se fie au champ `code`.
  Le code existant contient encore des messages en anglais : les traduire
  lorsqu'on modifie la route concernée (sans changer le `code`).
- Noms de code (variables, fonctions, colonnes) : **en anglais**.

---

## 5. Routes (couche HTTP)

Squelette type d'un endpoint (cf. `routes/wallet.py`) :

```python
@wallet_bp.route('/topups/<uuid:topup_id>', methods=['GET'])
@customer_required
def get_topup(topup_id):
    customer_id = get_jwt_identity()
    try:
        topup = wallet_repository.get_topup(topup_id)
        if not topup:
            return error_response('NOT_FOUND', 'Rechargement introuvable', 404)
        if str(topup['customer_id']) != str(customer_id):
            return error_response('FORBIDDEN', "Ce rechargement n'est pas accessible", 403)
        ...
        db.session.commit()
        return jsonify({'topup': topup_row_to_api(topup)}), 200
    except Exception as e:
        db.session.rollback()
        # Détail technique dans les logs uniquement, jamais dans la réponse.
        logger.exception(f"Error fetching top-up (topup_id={topup_id}, customer_id={customer_id}): {e}")
        return error_response('INTERNAL_ERROR', 'Une erreur est survenue, veuillez réessayer', 500)
```

> Le code existant renvoie encore souvent `jsonify({'error': str(e)}), 500` et
> des messages en anglais : **ne pas reproduire ce modèle**.

### Authentification et autorisation

- Utiliser les décorateurs de `routes/guards.py` : `@customer_required`,
  `@driver_required`, ou `@app_jwt_required(AUDIENCE, allow_pending_pin_change=...)`.
  **Ne plus utiliser `@jwt_required()` seul** dans du code neuf : il ne vérifie pas l'audience.
- L'identité vient **toujours** du jeton (`get_jwt_identity()`), jamais du corps
  de requête. Aucun `customer_id`, `wallet_id`, `balance`… n'est accepté depuis le client.
- Vérifier la propriété de chaque ressource (`str(resource['customer_id']) != str(customer_id)` → 403).
- Les décorateurs laissent passer les requêtes `OPTIONS` (préflight CORS) :
  tout `before_request` ou guard nouveau doit faire de même.

### Entrées

- `data = request.get_json(silent=True) or {}` (préféré à `get_json()` qui lève sur un corps invalide).
- Valider et normaliser tôt (`.strip()`, `.lower()`), retourner 400 avant toute écriture.
- Paramètres de chemin typés par Flask quand possible : `<uuid:topup_id>`.
- Pagination : `limit` borné (`parse_limit(raw, default, maximum)`), curseur `before` en ISO-8601, réponse `{items, next_before, has_more}`.
- Idempotence des créations sensibles via en-tête `Idempotency-Key`.

### Réponses

- Toujours `return jsonify({...}), <status>` avec un statut explicite.
- Ressource enveloppée sous une clé nommée : `{'booking': {...}}`, `{'trips': [...]}`.
- **Erreurs : `{'error': <message en français>, 'code': <code stable>}`** (+ champs de
  contexte éventuels, ex. `min_amount`). Utiliser un helper `error_response(code, message, status, **extra)`.
- Le message `error` est en français et ne contient **aucun détail technique**
  (cf. § 4). Ne jamais y mettre `str(e)` : le message d'une exception peut
  contenir du SQL, des identifiants internes ou une réponse provider. Les
  exceptions métier relayées au client portent un message déjà rédigé pour
  l'utilisateur, en français.
- Erreur inattendue (500) : message générique (`'Une erreur est survenue, veuillez réessayer'`, code `INTERNAL_ERROR`).
- Codes d'erreur : `UPPER_SNAKE_CASE` pour le métier (`INVALID_AMOUNT`,
  `WALLET_FROZEN`, `TOPUP_LIMIT_REACHED`) ; les codes d'auth JWT historiques
  sont en minuscules (`token_expired`, `invalid_audience`) — ne pas les renommer,
  l'app mobile en dépend.
- Statuts : 400 entrée invalide, 401 non authentifié, 403 interdit, 404 absent ou
  fonctionnalité désactivée, 409 conflit d'état, 429 limite atteinte,
  503 provider indisponible, 500 inattendu.
- Échecs d'authentification : **un seul message générique** côté client ; la
  raison précise ne va que dans les logs / le journal `app_auth.login_attempts`.

### Feature flags

Les fonctionnalités à déploiement progressif sont pilotées par des booléens de
`Config` (`WALLET_ENABLED`, `WALLET_TOPUP_ENABLED`, …) lus via
`current_app.config`. Fonctionnalité désactivée → 404 avec un `code` dédié
(`WALLET_DISABLED`). Le code est livré inerte, puis activé étape par étape.

---

## 6. Transactions et accès base

- **La route possède la transaction** : `db.session.commit()` en cas de succès,
  `db.session.rollback()` dans chaque `except`. Les services et repositories
  **n'ouvrent ni ne valident** de transaction — sauf exception documentée en
  docstring (`refund_service.py`, commandes CLI).
- Exception assumée : quand une trace doit survivre à un échec (journal de
  login, compteur d'échecs PIN), l'appelant commit **aussi** après l'échec.
- Avant un appel réseau à un provider, **committer l'état `pending`** pour que
  la tentative reste tracée même si l'appel échoue.
- SQL brut via `sqlalchemy.text()`, **toujours paramétré** (`:param`), jamais
  d'interpolation de valeurs dans la chaîne. Cast explicite des UUID :
  `cast(:id as uuid)`. Toujours qualifier les tables par leur schéma (`public.bookings`).
- Requête SQL multi-lignes en triple quotes, mots-clés **en minuscules**, indentée dans l'appel.
- Lecture : `.mappings().first()` / `.one()` puis `dict(row)` ; `None` si absent.
- Concurrence (soldes, places, statuts de paiement) : verrouiller la ligne avec
  `for update` (paramètre `for_update=True` des repositories) avant de la modifier.
- Invariants critiques doublés en base : `check (balance >= 0)`, statuts
  contraints par `check (status in (...))`.
- Horodatage : `timezone('utc', now())` côté SQL, `datetime.now(timezone.utc)`
  côté Python. **Ne pas utiliser `datetime.utcnow()`** (naïf, déprécié).

---

## 7. Argent et paiements

- **Montants XOF en francs entiers** (`int`, colonnes `bigint`) : le franc CFA
  n'a pas de sous-unité. Le `× 100` exigé par Paystack/JEKO est confiné à
  l'appel provider (`amount_cents=int(amount) * 100`). Jamais de `float` pour un montant stocké.
- Rejeter les `bool` lors du parsing d'un montant (`isinstance(value, bool)`), un `float` n'est accepté que s'il est entier.
- Vérifier les plafonds **avant** d'encaisser : une fois l'argent pris, le crédit n'est plus refusable.
- **Webhooks** : authentifiés par signature HMAC sur le corps brut (401 si
  invalide), idempotents, et répondent 200 à tout événement signé (même
  inconnu / doublon) pour stopper les re-essais du provider.
- **Callback navigateur** : ne jamais faire confiance aux query params ;
  re-vérifier auprès de l'API du provider puis appliquer les mêmes règles que le webhook.
- Un paiement en succès **n'est jamais rétrogradé**. Webhook et callback peuvent arriver dans n'importe quel ordre.
- Wallet = registre en écritures (`wallet_entries`) + solde matérialisé ;
  `flask wallet-audit` détecte les écarts. Ne jamais corriger un solde « à la main » dans le code.

---

## 8. Logging

```python
from loguru import logger
from logger import mask_phone
```

- `logger.info` pour les étapes métier (création, règlement, réutilisation),
  `logger.warning` pour les rejets attendus (validation, accès refusé, limite),
  `logger.error` pour un échec provider géré, `logger.exception` dans les
  `except Exception` (trace complète).
- Contexte en `clé=valeur` entre parenthèses : `(customer_id=…, topup_id=…, provider=…)`.
- **Données sensibles** : jamais de mot de passe, PIN, OTP, jeton, clé API ou
  secret dans les logs ; téléphones masqués avec `mask_phone()`.
- Ne pas utiliser `print()` (encore présent dans `database.py`, legacy).

---

## 9. Configuration

- Toute variable d'environnement est déclarée dans `config.py` (classe `Config`)
  **et** documentée dans `.env.example` avec un commentaire.
- Lecture dans le code via `current_app.config['X']` (dans une requête) ;
  `Config.X` uniquement hors contexte applicatif (constructeurs de services).
- Booléens : `os.environ.get('X', 'false').lower() == 'true'`. Entiers : `int(os.environ.get('X') or <défaut>)`.
- Secrets : **aucune valeur par défaut** ; vérification au démarrage dans
  `app.py` (`_require_secrets`, `_require_payment_provider_config`) — refus de
  démarrer en production, repli avec warning en développement.
- `APP_ENV=development` charge `.env.development` ; `ENV_FILE` permet d'imposer un fichier.
- Ne jamais committer `.env*` réels.

---

## 10. Services et intégrations externes

- Un service = une classe (`PaystackService`, `JekoService`, `DriverAuthService`)
  ou un module de fonctions (`refund_service.py`).
- Dépendances injectables par mots-clés dans `__init__` (cf. `DriverAuthService`)
  pour faciliter les tests.
- Appels HTTP via `requests` avec **un `timeout` explicite**.
- Erreurs métier signalées par des **exceptions typées** (`services/auth/errors.py`,
  `WalletFrozenError`, `JekoDuplicateReferenceError`), portant un `code` stable
  quand la route doit le relayer au client. La route les traduit en réponse HTTP.
- Objets de valeur : `@dataclass(frozen=True)` (`LoginContext`, `IssuedTokens`, `Principal`).
- Les services legacy Wave / Orange Money / MTN ne sont pas branchés : ne pas les étendre.

---

## 11. Style Python

- PEP 8, indentation 4 espaces, lignes ≈ 100 caractères max.
- Imports groupés : stdlib, puis tiers, puis projet, séparés par une ligne
  vide, triés alphabétiquement ; imports absolus depuis la racine
  (`from infrastructure.supabase_write_repositories import ...`).
- `from __future__ import annotations` + annotations de type dans `domain/`,
  `infrastructure/`, `services/auth/` ; syntaxe moderne (`str | None`, `list[dict[str, Any]]`).
- Arguments par mot-clé obligatoires (`*`) pour les fonctions à plusieurs
  paramètres de même type (`create(self, *, user_id, phone, password)`).
- Chaînes : quotes simples dans `routes/`, doubles dans `domain/`/`infrastructure/` —
  suivre le fichier courant.
- f-strings pour le formatage.
- Docstring de module en tête de tout fichier non trivial : rôle + règles métier
  importantes (cf. `routes/wallet.py`, `services/auth/driver_auth_service.py`).
- Sections d'un gros module séparées par des bannières :
  ```python
  # ---------------------------------------------------------------------------
  # POST /api/wallet/topups — démarre un rechargement
  # ---------------------------------------------------------------------------
  ```

---

## 12. Base de données, schéma et migrations

- Trois sources de schéma, à **garder synchronisées** à chaque évolution :
  1. **Supabase (prod)** : les migrations sont exécutées **directement en
     production** (Supabase Studio > SQL Editor ou `psql`), **avant** le
     déploiement du code. Les scripts SQL correspondants restent locaux dans
     `scripts/`, qui est **volontairement ignoré par git** : aucun script ne doit
     être commité (ne pas retirer `/scripts` du `.gitignore`, ne pas forcer
     l'ajout avec `git add -f`). Ils doivent être idempotents
     (`begin; … commit;`, `if not exists`) pour pouvoir être rejoués sans risque.
  2. **Base locale Docker** : `local_db/01_schema.sql` + `local_db/02_seed.sql`
     (rejoués seulement à la création du volume : `docker compose down -v` pour repartir de zéro).
  3. **Alembic** (`migrations/versions/`) : révisions en SQL brut via `op.execute()`,
     **jamais d'autogénération** (elle tenterait de réconcilier les modèles ORM morts).
- Le schéma `auth` appartient à Supabase Auth : ne pas y créer de table ; les
  tables d'auth applicative vivent dans `app_auth` (non exposé par PostgREST).
- Clés primaires UUID (`gen_random_uuid()`), colonnes `created_at` / `updated_at` en `timestamptz`.

---

## 13. Tests

- Framework : `unittest` (classes héritant de `tests.base.BackendApiTestCase`),
  fichiers `tests/test_<domaine>.py`, bases partagées `tests/<domaine>_base.py`.
- Tests d'**intégration** sur une vraie base Postgres (la base Docker locale) via
  `self.client` (Flask test client). Pas de mock de la base.
- Chaque `setUp` nettoie puis insère ses propres données, dans l'ordre imposé
  par les clés étrangères. UUID de test fixes et lisibles (`8888…`), constantes en tête de fichier.
- Les appels providers (Paystack, JEKO, Brevo) sont mockés (`unittest.mock.patch`).
- Lancer les tests :
  ```bash
  docker compose -f docker-compose.local.yml up -d postgres
  ENV_FILE=/dev/null APP_ENV=development \
    DATABASE_URL=postgresql://user:password@localhost:5432/minibus_db \
    AUTO_UPGRADE_DB=false SECRET_KEY=test JWT_SECRET_KEY=test \
    ./venv/bin/python -m unittest discover -s tests -t .
  ```
- Tout correctif de bug ou nouvelle route s'accompagne d'un test ; couvrir au
  minimum : cas nominal, validation (400), autorisation (401/403 et accès à la
  ressource d'un autre client), idempotence pour les flux de paiement.

---

## 14. Git

- Branches : `main` (prod), `dev` (intégration), branches de fonctionnalité `feat/<sujet>`.
- Commits au format **Conventional Commits**, en anglais, à l'impératif :
  `feat: implement wallets`, `fix: return pickup and dropoff stop in booking response`.
  Préfixes utilisés : `feat`, `fix` ; recommandés en plus : `refactor`, `test`, `docs`, `chore`.
- Un commit = un changement cohérent ; pas de commits « divers ».
- Les agents IA ne committent jamais de leur propre initiative (cf. § 15).

---

## 15. Consignes spécifiques aux agents IA

- Lire ce document et le module que l'on modifie **avant** d'écrire du code ; imiter le code récent adjacent.
- Ne pas toucher au code legacy (modèles ORM, services Wave/Orange/MTN) sauf demande explicite.
- Les routes admin (`/api/admin/...`, guard `admin-app`) sont volontairement **reportées** : ne pas les implémenter ni les signaler comme manquantes.
- Toute modification de schéma : mettre à jour les trois sources (§ 12) et le
  signaler. Le script de prod va dans `scripts/` et **n'est jamais commité** ;
  rappeler à l'utilisateur de l'exécuter en production avant le déploiement.
- Messages d'erreur renvoyés au client : en français, sans détail technique (§ 4, § 5).
- Toute nouvelle variable d'env : `config.py` + `.env.example` + validation au démarrage si obligatoire en prod.
- Ne jamais changer un `code` d'erreur, un nom de champ JSON ou un chemin d'URL
  existant sans le signaler : l'app mobile en dépend (ex. le chemin
  `/api/payments/callback` est détecté par suffixe côté mobile).
- Vérifier la compilation rapide avant de rendre la main :
  `./venv/bin/python -m compileall -q routes infrastructure services application migrations/versions tests app.py config.py`,
  puis lancer les tests du domaine touché.
- **Ne jamais prendre l'initiative d'un commit** : aucun `git commit` (ni
  `git push`, `git commit --amend`, `git rebase`…) sans autorisation explicite
  de l'utilisateur, donnée pour ce commit-là. Une autorisation passée ne vaut
  pas pour les suivants. Par défaut, laisser les changements dans l'arbre de
  travail et proposer un message de commit.

---

## 16. Recommandations (bonnes pratiques à adopter)

Ces points ne sont **pas encore** appliqués partout ; à suivre pour le code neuf
et à intégrer progressivement lors des refactorings.

### Priorité haute

1. **Ajouter `app_auth` au schéma local** (`local_db/01_schema.sql`) pour qu'une
   base Docker neuve puisse faire tourner `tests/test_driver_auth.py`.
2. **Supprimer tous les `str(e)` renvoyés au client** (la plupart des `except
   Exception` des routes) : cela expose des détails SQL ou internes. Renvoyer
   `error_response('INTERNAL_ERROR', 'Une erreur est survenue, veuillez réessayer', 500)`
   et garder le détail dans `logger.exception`. Idéalement, laisser remonter au
   `errorhandler(Exception)` global d'`app.py` (après rollback), dont le message
   `'Erreur interne'` est déjà en français.
3. **Traduire en français les messages d'erreur encore en anglais** (wallet,
   booking, payment, trip, lines, guards JWT d'`app.py` : `'Session expired'`,
   `'Invalid token'`…) et retirer le champ `detail` des erreurs JWT, qui expose
   la raison technique. Ne pas changer les `code`.
4. **Uniformiser le format d'erreur** `{'error', 'code'}` sur toutes les routes
   (booking, trip, lines n'ont pas encore de `code`). Déplacer `error_response`
   de `routes/wallet.py` vers un module partagé (ex. `routes/responses.py`).
5. **Migrer les guards admin legacy** (`routes/trip.py` POST, `routes/vehicles.py`
   qui s'appuient sur `@jwt_required()` + `User.role`) vers `app_jwt_required(ADMIN_APP)`
   quand le back-office sera traité.

### Outillage

6. **Formatage et lint automatiques** : adopter `ruff` (lint + format, remplace
   flake8/isort/black) avec un `pyproject.toml` (`line-length = 100`,
   `target-version = "py310"`) et un hook `pre-commit`. Fixer la convention de
   quotes une fois pour toutes via le formateur.
7. **Typage** : annoter les signatures des nouvelles fonctions (y compris les
   routes et services) ; envisager `mypy` en mode non strict sur `domain/`, `infrastructure/`, `services/`.
8. **Épingler toutes les dépendances** (`pandas`, `loguru`, `gunicorn`… ne sont
   pas versionnées) et séparer `requirements-dev.txt` (ruff, pytest, mypy).
9. **CI** (GitHub Actions) : lint + tests sur service Postgres à chaque PR vers `dev`/`main`.
10. **Aligner la doc des tests** : le README indique `pytest` mais le projet
    utilise `unittest` sans pytest dans les dépendances — choisir l'un
    (pytest sait exécuter les tests unittest existants) et mettre le README à jour.

### Architecture et code

11. **Validation d'entrée déclarative** : pour les nouveaux endpoints à payload
    riche, envisager `pydantic` (schémas d'entrée typés) plutôt que des
    boucles `required_fields` manuelles.
12. **Logique métier hors des routes** : `routes/payment.py` (≈ 900 lignes)
    contient le règlement des paiements ; l'extraire progressivement dans
    `services/payment_settlement.py` pour qu'il soit testable sans HTTP.
13. **Découper `infrastructure/supabase_write_repositories.py`** (≈ 1 500 lignes)
    en un module par agrégat (`booking_repository.py`, `wallet_repository.py`, …).
14. **Instancier les repositories sans état au niveau module** reste acceptable ;
    éviter en revanche tout état mutable partagé (gunicorn sert en multi-threads).
15. **Supprimer le code mort** une fois confirmé : modèles ORM non utilisés,
    services de paiement legacy, `update_schema.py`, `verify_transport.py`,
    `lines.xlsx` hors seed, `__pycache__/` à la racine.
16. **Ajouter un identifiant de requête** (`X-Request-ID`) propagé dans les logs
    via `logger.contextualize(...)` pour corréler les lignes d'une même requête dans Better Stack.
17. **Limitation de débit** sur les endpoints d'authentification (login, reset
    password) comme c'est déjà fait pour les rechargements wallet.
18. **Documentation d'API** : maintenir la collection Bruno (`bruno/`) à jour à
    chaque nouvelle route, ou générer une spec OpenAPI.
