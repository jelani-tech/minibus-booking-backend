"""Script de vérification automatisée de bout en bout du Jeu de Données (JDD) de Test."""
import urllib.request
import urllib.error
import json
import sys

BASE_URL = 'http://localhost:8000'

def request(method, path, data=None, token=None):
    url = f'{BASE_URL}{path}'
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req_body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=req_body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {'raw_error': body}

def verify_all():
    print("=" * 70)
    print("VÉRIFICATION DU JEU DE DONNÉES DE TEST & DES ENDPOINTS BACKEND")
    print("=" * 70)

    # 1. Login avec Jean Kouassi
    status, data = request('POST', '/api/auth/login', {'phone': '+2250101010101', 'password': 'Password123!'})
    assert status == 200, f"Erreur login Jean Kouassi: {status} {data}"
    token_jean = data.get('access_token')
    print("1. [OK] Authentification Jean Kouassi (+2250101010101)")

    # 2. Wallet Jean Kouassi (doit valoir 50 000 FCFA)
    status, data = request('GET', '/api/wallet', token=token_jean)
    assert status == 200, f"Erreur wallet Jean: {status} {data}"
    wallet = data.get('wallet', {})
    balance = float(wallet.get('balance', 0))
    assert balance == 50000.0, f"Solde Jean incorrect : attendu 50000, reçu {balance}"
    print(f"2. [OK] Solde Wallet Jean Kouassi : {balance:,.0f} {wallet.get('currency')} (attendu 50 000 FCFA)")

    # 3. Historique Wallet Jean Kouassi
    status, data = request('GET', '/api/wallet/transactions', token=token_jean)
    assert status == 200, f"Erreur transactions wallet Jean: {status} {data}"
    entries = data.get('transactions', [])
    assert len(entries) >= 4, f"Nombre d'écritures insuffisant : {len(entries)}"
    print(f"3. [OK] Registre Wallet Jean Kouassi ({len(entries)} écritures comptables vérifiées) :")
    for e in entries:
        print(f"   -> {e.get('created_at', '')[:19]} | {e.get('direction').upper():<6} | {e.get('amount'):>6} FCFA | Solde après: {e.get('balance_after'):>6} FCFA | {e.get('description')}")

    # 4. Réservations de Jean Kouassi (7 réservations couvrant tous les états)
    status, data = request('GET', '/api/bookings', token=token_jean)
    assert status == 200, f"Erreur bookings Jean: {status} {data}"
    bookings = data.get('bookings', [])
    assert len(bookings) == 7, f"Attendu 7 réservations, reçu {len(bookings)}"
    print(f"4. [OK] 7 réservations trouvées pour Jean Kouassi :")
    for b in bookings:
        print(f"   -> Ref: {b.get('external_reference'):<26} | Statut: {b.get('booking_status'):<9} | Journey: {b.get('journey_status'):<9} | CanPay: {str(b.get('can_pay')):<5} | CanShowTicket: {str(b.get('can_show_ticket')):<5}")

    # 5. Billet public JELANI-TEST-UPCOMING
    status, data = request('GET', '/api/bookings/ticket/JELANI-TEST-UPCOMING')
    assert status == 200, f"Erreur billet public: {status} {data}"
    ticket = data.get('ticket', {})
    assert ticket.get('ticket_status') == 'valid'
    assert ticket.get('journey_status') == 'upcoming'
    print(f"5. [OK] Billet public JELANI-TEST-UPCOMING validé (ticket_status=valid, journey_status=upcoming)")

    # 6. Compte Marie Amani (solde 0 FCFA)
    status, data = request('POST', '/api/auth/login', {'phone': '+2250202020202', 'password': 'Password123!'})
    assert status == 200, f"Erreur login Marie Amani: {status} {data}"
    token_marie = data.get('access_token')
    status, data = request('GET', '/api/wallet', token=token_marie)
    assert status == 200, f"Erreur wallet Marie: {status} {data}"
    assert float(data.get('wallet', {}).get('balance', -1)) == 0.0
    print("6. [OK] Marie Amani (+2250202020202) vérifiée : Solde Wallet = 0 FCFA (cible test Mobile Money)")

    # 7. Compte Jean-Eudes KACOU (développeur, solde 50 000 FCFA)
    status, data = request('POST', '/api/auth/login', {'phone': '1234567890', 'password': 'Password123!'})
    assert status == 200, f"Erreur login Jean-Eudes KACOU: {status} {data}"
    token_jeaneudes = data.get('access_token')
    status, data = request('GET', '/api/wallet', token=token_jeaneudes)
    assert status == 200, f"Erreur wallet Jean-Eudes: {status} {data}"
    assert float(data.get('wallet', {}).get('balance', -1)) == 50000.0
    print("7. [OK] Jean-Eudes KACOU (1234567890) vérifié : Solde Wallet = 50 000 FCFA")

    # 8. Compte Scanner / Contrôleur Seydou (+2250303030303)
    status, data = request('POST', '/api/auth/login', {'phone': '+2250303030303', 'password': 'Password123!'})
    assert status == 200, f"Erreur login Seydou Contrôleur: {status} {data}"
    token_scanner = data.get('access_token')

    # 8.a. Test de sécurité : Jean Kouassi (client simple) tente de valider un ticket -> HTTP 403 attendu
    status, data = request('POST', '/api/bookings/ticket/JELANI-TEST-BOARDING/consume', {'trip_id': '77777777-7777-7777-7777-777777777702'}, token=token_jean)
    assert status == 403, f"Attendu 403 pour client non-contrôleur, reçu {status}"
    print("8.a [OK] Contrôle d'accès scanner : client simple rejeté avec HTTP 403 Unauthorized")

    # 8.b. Test contrôleur autorisé : Seydou valide le ticket prêt à l'embarquement
    status, data = request('POST', '/api/bookings/ticket/JELANI-TEST-BOARDING/consume', {'trip_id': '77777777-7777-7777-7777-777777777702'}, token=token_scanner)
    assert status == 200, f"Erreur validation ticket par Seydou: {status} {data}"
    consumed_booking = data.get('booking', {})
    assert consumed_booking.get('booking_status') == 'boarded'
    print(f"8.b [OK] Seydou Contrôleur valide l'embarquement de JELANI-TEST-BOARDING -> booking_status = {consumed_booking.get('booking_status')}")

    # 8.c. Test double scan (anti-fraude) : tentative de réutilisation immédiate -> HTTP 409 attendu
    status, data = request('POST', '/api/bookings/ticket/JELANI-TEST-BOARDING/consume', {'trip_id': '77777777-7777-7777-7777-777777777702'}, token=token_scanner)
    assert status == 409, f"Attendu 409 pour ticket déjà utilisé, reçu {status}"
    print(f"8.c [OK] Anti-fraude double scan : billet déjà consommé rejeté avec HTTP 409 ({data.get('error')})")

    # 9. Recherche des trajets
    status, data = request('GET', '/api/trips')
    assert status == 200, f"Erreur trips search: {status} {data}"
    trips = data.get('trips', [])
    print(f"9. [OK] Recherche de trajets : {len(trips)} trajets vendables retournés :")
    for t in trips:
        print(f"   -> Trip ID: {t.get('id')[:8]}... | {t.get('departure_city')} -> {t.get('arrival_city')} | Places dispo: {t.get('available_seats')} | Statut: {t.get('status')}")

    print("=" * 70)
    print("TOUTES LES VÉRIFICATIONS DU JEU DE DONNÉES SONT VALIDÉES AVEC SUCCÈS !")
    print("=" * 70)

if __name__ == '__main__':
    verify_all()
