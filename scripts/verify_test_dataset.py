import urllib.request
import json

def test_api():
    # 1. Login avec Jean Kouassi
    req = urllib.request.Request(
        'http://localhost:8000/api/auth/login',
        data=json.dumps({'phone': '+2250101010101', 'password': 'Password123!'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    token = data.get('access_token')
    print('1. [OK] Authentification réussie pour +2250101010101 (Jean Kouassi)')

    # 2. Récupération des réservations
    req2 = urllib.request.Request(
        'http://localhost:8000/api/bookings',
        headers={'Authorization': f'Bearer {token}'}
    )
    with urllib.request.urlopen(req2) as resp2:
        res = json.loads(resp2.read().decode())
        bookings = res.get('bookings', [])
    print(f'2. [OK] {len(bookings)} réservations trouvées pour ce client :')
    for b in bookings:
        print(f"   -> Ref: {b.get('external_reference'):<26} | Statut: {b.get('booking_status'):<9} | Journey: {b.get('journey_status'):<9} | CanPay: {str(b.get('can_pay')):<5} | CanShowTicket: {str(b.get('can_show_ticket')):<5}")

    # 3. Consultation publique du billet
    req3 = urllib.request.Request('http://localhost:8000/api/bookings/ticket/JELANI-TEST-UPCOMING')
    with urllib.request.urlopen(req3) as resp3:
        ticket = json.loads(resp3.read().decode()).get('ticket', {})
    print(f'3. [OK] Billet public JELANI-TEST-UPCOMING : ticket_status={ticket.get("ticket_status")}, journey_status={ticket.get("journey_status")}')

    # 4. Recherche de trajets disponibles (Trips search)
    req4 = urllib.request.Request('http://localhost:8000/api/trips')
    with urllib.request.urlopen(req4) as resp4:
        trips = json.loads(resp4.read().decode()).get('trips', [])
    print(f'4. [OK] Recherche de trajets : {len(trips)} trajets vendables retournés :')
    for t in trips:
        print(f"   -> Trip ID: {t.get('id')[:8]}... | {t.get('departure_city')} -> {t.get('arrival_city')} | Date: {t.get('trip_date')} | Depart: {t.get('departure_time')} | Places dispo: {t.get('available_seats')} | Status: {t.get('status')}")

if __name__ == '__main__':
    test_api()
