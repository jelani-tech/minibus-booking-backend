# Audit JELANI Mobile MVP - corrections du 11 octobre 2026

Source : rapport JELANI Mobile MVP v1, daté du 27 août 2026, transmis dans
`JELANI_Rapport_Audit_Mobile_MVP_v1_261007_223619.pdf` (6 pages).
Le rapport est une source de constats, pas une autorisation de déploiement.
Analyse confrontée à `origin/main` : backend `939c2b0`, mobile `b1d746c`.
Branches des deux dépôts : `codex/audit-mobile-mvp`.
Le projet Angular `jelani-web` a été inspecté ; ses écrans administratifs
legacy ne sont pas nécessaires aux corrections du parcours mobile et restent inchangés.

## Constats et traitement

| Audit | Correction / état |
| --- | --- |
| P0 - trajets passés vendables | Recherche générale et par ligne : `scheduled`, capacité disponible, horloge UTC avant départ et fermeture. Création : même règle sous verrou du trajet. `scheduled` représente OPEN dans le schéma existant ; BOARDING ne permet plus de vendre. |
| P0 - impayés encore payables | Avant tout provider ou débit wallet : propriétaire, PENDING, délai de paiement, fermeture et départ. Refus des délais dépassés : HTTP 409 / BOOKING_EXPIRED. |
| P0 - expiration | Nouvelle réservation : 15 minutes maximum, bornée par fermeture/départ. Anciennes lignes sans délai : created_at + 15 min. PENDING -> EXPIRED ; le trigger existant restitue la capacité. Expiration à la recherche/lecture et commande périodique. |
| P0 - lifecycle | booking_status et payment_status restent indépendants ; journey_status et ticket_status sont calculés côté serveur. Fin explicite ou fin planifiée atteinte : COMPLETED pour embarqués, NO_SHOW pour confirmés non embarqués. Aucun QR/action active. |
| P0 - QR | Référence UUID complète pour les nouveaux billets, vérification serveur avec trip_id, paiement paid, confirmation et fenêtre ; passage atomique à boarded. Second scan : TICKET_ALREADY_USED. Scanner réservé aux identités provisionnées côté serveur. |
| Paiement tardif / répétition | Encaissement reçu après expiration/annulation/fermeture : booking non réactivé, paiement refund_required, paid_at et paiement payé conservés pour rapprochement. Livraison répétée ignorée. Checkout pending réutilisé sans nouvel appel provider ; paiement wallet refusé si checkout externe pending. Après un échec, chaque nouvel essai conserve sa propre ligne et référence ; un double encaissement tardif est détecté et signalé refund_required. |
| P1 - date, listes, actions | App mobile : date/heure du voyage, filtres À venir / À payer / Historique / Annulés, états lifecycle et permissions serveur. Bouton Voir ma réservation. |
| P1 - lenteur / loaders | Temps total et SQL par requête, Server-Timing, nombre de requêtes SQL dans les logs ; script GET de benchmark P50/P95/P99/TTFB. Mobile : timeout de 20 s sur connexion ET corps de réponse, pas de retry automatique des écritures. |
| P1 - i18n | Recherche déjà largement centralisée sur main ; format de date auparavant figé en français corrigé. Nouveaux libellés FR/EN. Audit complet des erreurs historiques encore à faire. |
| P2 - avant paiement / ticket | Arrêts intermédiaires repliables ; statut valide, date/heure et nombre de places près du QR dans l'app. |
| Android production | Signature debug supprimée pour release ; applicationId définitif et keystore obligatoires. Pas de clé créée ou commise. |

## Déploiement (non effectué)

1. Sauvegarder la base et appliquer **avant** le nouveau backend
   `scripts/audit_lifecycle_schema.sql` via psql / SQL Editor (statements séparés
   en autocommit pour l'enum PostgreSQL). Rejouable et sans suppression de données.
   Sur une base déjà suivie par Alembic au head `b3c4d5e6f7a8`, utiliser plutôt
   `flask db upgrade` vers `c4d5e6f7a8b9`. Ne pas activer toutes les migrations
   legacy sur une base Supabase existante sans vérifier son historique.
2. Déployer le backend, puis lancer `flask --app app expire-bookings` pour
   nettoyer les anciennes réservations. Programmer la même commande chaque minute.
   La recherche et les lectures client nettoient aussi les holds concernés ;
   elles ne remplacent pas le job pour les voyages sans trafic API.
3. Provisionner les opérateurs : `TICKET_SCANNER_CUSTOMER_IDS=uuid1,uuid2`.
   Par défaut aucun client n'est autorisé à scanner. Ce mécanisme serveur est
   un accès pilote explicite ; un modèle staff avec affectation par trajet reste
   préférable pour une flotte élargie. Ne jamais accorder cet accès à un client ordinaire.
4. Déployer l'app ensuite : sans les nouvelles permissions API, elle masque
   les actions sensibles. La nouvelle réponse publique ticket est volontairement
   minimale ; adapter tout consommateur externe éventuel.
5. Superviser les paiements `refund_required` : aucun virement de remboursement
   tardif n'est lancé automatiquement. Réconcilier avec le provider avant paiement.

## Contrat transport et ticket

- `trips.booking_close_at` nullable : null ferme les ventes au départ ; une date
  explicite ne peut jamais prolonger la vente après départ (minimum des deux).
- Hold initial : 15 min. Pas de modification des réservations confirmées à l'expiration.
- UTC pour toutes les comparaisons, timestamps naïfs anciens interprétés UTC.
- Annulation : cutoff existant de 60 min ; états terminal/embarqué exclus.
- Présentation ticket : confirmé et payé, trajet scheduled/boarding, avant la fin
  et avant départ + 15 min. Scan : à partir de départ - 30 min, jusqu'au minimum
  de la fin planifiée et départ + 15 min (bornes de fin exclusives).
- `POST /api/bookings/ticket/<reference>/consume`, JWT opérateur provisionné,
  JSON `{ "trip_id": "<uuid>" }`. 200 + booking si embarqué ; 409 pour mauvais
  trajet, billet invalide ou déjà consommé ; 401/403 pour accès non autorisé.
- `GET /api/bookings/ticket/<reference>` expose seulement `ticket_reference`,
  `trip_id`, `number_of_seats`, `journey_status`, `ticket_status` sous `ticket`.
  Aucun nom/téléphone/email client ni QR exploitable sur ce endpoint public.
- Le QR ne constitue pas une preuve autonome ; seul le scan serveur fait foi.
  La liste d'opérateurs et la fenêtre doivent être validées opérationnellement.
- Les états de voyage sont calculés, pas un nouveau système de dispatch.
  Pour un trajet retardé, les horaires et statuts doivent être actualisés par
  l'exploitation. Sans heure de fin, le ticket expire quand même ; la clôture
  opérationnelle nécessite le passage du trajet à completed.

## Validation

Base PostgreSQL 15 Docker isolée, port 55432, aucune connexion à la production.
Migration Alembic depuis b3c4d5e6f7a8 vers c4d5e6f7a8b9 et rejeu du script SQL vérifiés.
`python -m unittest discover -s tests -t .` : **127 tests réussis**.
Régressions : trajet passé via API directe, fermeture, hold expiré, legacy sans
expires_at, capacité restituée, dernière place concurrente, CLI idempotente,
encaissement tardif répété, autorisation scan et double scan, lifecycle terminé,
frontières exactes UTC, paiements/refunds/wallet existants.

Mobile : `flutter analyze --no-pub` sans problème ; `flutter test --no-pub` :
**106 tests réussis**, incluant les deadlines locales, les permissions serveur,
les timeouts de connexion/corps et les intents paiement. Fichier utilitaire
payment_url_utils.dart manquant sur main rétabli avec tests.

Mesure locale GET /api/trips, 100 requêtes séquentielles, Flask WSGI + PostgreSQL
sur cette machine : 0 échec ; total P50 **7,8 ms**, P95 **31,4 ms**, P99 **32,4 ms** ;
TTFB P95 **31,2 ms**, P99 **32,3 ms**. Ce résultat porte sur un jeu de données
minimal : il ne valide ni Render, ni réseau mobile, ni les cold starts, ni la charge.
Pour répéter : `python scripts/benchmark_api.py <URL staging>/api/trips --samples 100`.
DNS/TLS nécessitent en complément un outil réseau (par ex. curl -w) ; vérifier
les plans SQL et P95/P99 sous charge représentative avant le pilote élargi.

## Suite explicitement non livrée

- Nom de package final approuvé, vraie clé, Play App Signing, génération/validation AAB
  et test sur appareil réel : prérequis opérateur, voir documentation mobile.
- App Link HTTPS vérifié : domaine servi + assetlinks.json + empreinte du certificat
  de publication requis. Le scheme existant ne remplace pas cette vérification.
- Préremplissage Jéko : confirmer les champs supportés par le contrat provider,
  ne pas inventer des paramètres d'API.
- Optimisation logo/tailles APK, recherche récente/fréquente et mesures réseau
  production : travaux P2 / environnement, pas des validations déjà acquises.
- Modèle staff, scanner métier et transitions dispatch (départ/arrivée réels),
  suivi GPS, stockage historique de journey : intégration d'exploitation distincte.

Références techniques consultées : [RLS Supabase](https://supabase.com/docs/guides/database/postgres/row-level-security),
[changelog Supabase](https://supabase.com/changelog.md). Aucun nouveau accès public,
aucune modification de politiques RLS ni publication de secrets.
