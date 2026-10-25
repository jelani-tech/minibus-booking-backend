-- ==============================================================================
-- JELANI TECHNOLOGIES - JEU DE DONNÉES DE TEST & VALIDATION (MVP AUDIT & DEV)
-- ==============================================================================
-- Idempotent : Peut être rejoué à volonté.
-- Mot de passe de test universel pour tous les comptes : Password123!
-- Hash Bcrypt : $2b$12$b1U49zKvNOPCTPe/xxkN4O23JkJ3D0i2XaOTBYNQ1jXqkFJ2ka1xK
-- ==============================================================================

BEGIN;

-- ------------------------------------------------------------------------------
-- 0. NETTOYAGE PRÉALABLE DES DONNÉES DE TESTS FIXES
-- ------------------------------------------------------------------------------
DELETE FROM public.wallet_entries WHERE idempotency_key LIKE 'seed-%';
DELETE FROM public.payments WHERE provider_reference LIKE 'PAY-TEST-%'
    OR booking_id IN (SELECT id FROM public.bookings WHERE trip_id IN (
        '77777777-7777-7777-7777-777777777701',
        '77777777-7777-7777-7777-777777777702',
        '77777777-7777-7777-7777-777777777703',
        '77777777-7777-7777-7777-777777777704',
        '77777777-7777-7777-7777-777777777705'
    ));
DELETE FROM public.bookings WHERE external_reference LIKE 'JELANI-TEST-%'
    OR trip_id IN (
        '77777777-7777-7777-7777-777777777701',
        '77777777-7777-7777-7777-777777777702',
        '77777777-7777-7777-7777-777777777703',
        '77777777-7777-7777-7777-777777777704',
        '77777777-7777-7777-7777-777777777705'
    );
DELETE FROM public.trips WHERE id IN (
    '77777777-7777-7777-7777-777777777701',
    '77777777-7777-7777-7777-777777777702',
    '77777777-7777-7777-7777-777777777703',
    '77777777-7777-7777-7777-777777777704',
    '77777777-7777-7777-7777-777777777705'
);
DELETE FROM public.line_stops WHERE id IN (
    '66666666-6666-6666-6666-666666666664',
    '66666666-6666-6666-6666-666666666665',
    '66666666-6666-6666-6666-666666666666'
);
DELETE FROM public.lines WHERE id = '44444444-4444-4444-4444-444444444445';
DELETE FROM public.stops WHERE id IN (
    '55555555-5555-5555-5555-555555555554',
    '55555555-5555-5555-5555-555555555555',
    '55555555-5555-5555-5555-555555555556'
);
DELETE FROM public.vehicles WHERE id = '22222222-2222-2222-2222-222222222223';
DELETE FROM public.drivers WHERE id = '33333333-3333-3333-3333-333333333334';
DELETE FROM public.partners WHERE id = '11111111-1111-1111-1111-111111111112';

-- Nettoyage des wallets et clients de test
DELETE FROM public.wallet_topups WHERE customer_id IN (
    '88888888-8888-8888-8888-888888888881',
    '88888888-8888-8888-8888-888888888882',
    '88888888-8888-8888-8888-888888888883'
);
DELETE FROM public.wallet_entries WHERE wallet_id IN (
    SELECT id FROM public.wallets WHERE customer_id IN (
        '88888888-8888-8888-8888-888888888881',
        '88888888-8888-8888-8888-888888888882',
        '88888888-8888-8888-8888-888888888883'
    )
);
DELETE FROM public.wallets WHERE customer_id IN (
    '88888888-8888-8888-8888-888888888881',
    '88888888-8888-8888-8888-888888888882',
    '88888888-8888-8888-8888-888888888883'
);
DELETE FROM public.customers WHERE id IN (
    '88888888-8888-8888-8888-888888888881',
    '88888888-8888-8888-8888-888888888882',
    '88888888-8888-8888-8888-888888888883'
);
DELETE FROM auth.users WHERE id IN (
    '99999999-9999-9999-9999-999999999991',
    '99999999-9999-9999-9999-999999999992',
    '99999999-9999-9999-9999-999999999993'
);

-- ------------------------------------------------------------------------------
-- 1. PARTENAIRES, VÉHICULES ET CHAUFFEURS SUPPLÉMENTAIRES
-- ------------------------------------------------------------------------------
INSERT INTO public.partners (id, name, contact_name, contact_phone, base_location, status)
VALUES
    ('11111111-1111-1111-1111-111111111112', 'VIP Express Minibus', 'Mamadou Diabaté', '+2250100000004', 'Abidjan', 'active')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, status = 'active';

INSERT INTO public.vehicles (
    id, partner_id, plate_number, vehicle_code, brand, model, seat_capacity, standing_capacity, energy_type, status
) VALUES
    ('22222222-2222-2222-2222-222222222223', '11111111-1111-1111-1111-111111111112', 'CI-456-EF', 'VIP-002', 'Mercedes', 'Sprinter VIP', 14, 0, 'diesel', 'available')
ON CONFLICT (id) DO UPDATE SET plate_number = EXCLUDED.plate_number, seat_capacity = 14;

INSERT INTO public.drivers (id, partner_id, first_name, last_name, phone, status)
VALUES
    ('33333333-3333-3333-3333-333333333334', '11111111-1111-1111-1111-111111111112', 'Bakary', 'Touré', '+2250100000005', 'active')
ON CONFLICT (id) DO UPDATE SET phone = EXCLUDED.phone;

-- ------------------------------------------------------------------------------
-- 2. NOUVELLE LIGNE URBAINE & ARRÊTS (Yopougon - Plateau)
-- ------------------------------------------------------------------------------
INSERT INTO public.lines (id, code, name, origin_name, destination_name, default_duration_minutes, default_price, status)
VALUES
    ('44444444-4444-4444-4444-444444444445', 'YOP-PLA', 'Yopougon Siporex - Plateau Postel', 'Abidjan Yopougon', 'Abidjan Plateau', 45, 1000, 'active')
ON CONFLICT (id) DO UPDATE SET status = 'active';

INSERT INTO public.stops (id, name, city, district, latitude, longitude, status)
VALUES
    ('55555555-5555-5555-5555-555555555554', 'Siporex', 'Abidjan', 'Yopougon', 5.3412, -4.0728, 'active'),
    ('55555555-5555-5555-5555-555555555555', 'Carrefour Liberté', 'Abidjan', 'Adjamé', 5.3580, -4.0250, 'active'),
    ('55555555-5555-5555-5555-555555555556', 'Postel 2001', 'Abidjan', 'Plateau', 5.3261, -4.0197, 'active')
ON CONFLICT (id) DO UPDATE SET status = 'active';

INSERT INTO public.line_stops (id, line_id, stop_id, stop_order, scheduled_offset_minutes)
VALUES
    ('66666666-6666-6666-6666-666666666664', '44444444-4444-4444-4444-444444444445', '55555555-5555-5555-5555-555555555554', 1, 0),
    ('66666666-6666-6666-6666-666666666665', '44444444-4444-4444-4444-444444444445', '55555555-5555-5555-5555-555555555555', 2, 25),
    ('66666666-6666-6666-6666-666666666666', '44444444-4444-4444-4444-444444444445', '55555555-5555-5555-5555-555555555556', 3, 45)
ON CONFLICT (line_id, stop_order) DO NOTHING;

-- ------------------------------------------------------------------------------
-- 3. COMPTES UTILISATEURS (AUTH + CUSTOMER + WALLET)
-- Mot de passe : Password123!
-- ------------------------------------------------------------------------------
-- Utilisateur 1 : Client Pilote Principal (avec solde wallet de 50 000 FCFA)
INSERT INTO auth.users (id, phone, encrypted_password)
VALUES
    ('99999999-9999-9999-9999-999999999991', '+2250101010101', '$2b$12$b1U49zKvNOPCTPe/xxkN4O23JkJ3D0i2XaOTBYNQ1jXqkFJ2ka1xK');

INSERT INTO public.customers (id, auth_user_id, first_name, last_name, phone, whatsapp_phone, email)
VALUES
    ('88888888-8888-8888-8888-888888888881', '99999999-9999-9999-9999-999999999991', 'Jean', 'Kouassi', '+2250101010101', '+2250101010101', 'jean.kouassi@jelani.test');

INSERT INTO public.wallets (id, customer_id, currency, balance, status)
VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', '88888888-8888-8888-8888-888888888881', 'XOF', 0, 'active');

-- Inscription comptable dans le registre wallet_entries (double-entry bookkeeping)
INSERT INTO public.wallet_entries (
    wallet_id, direction, entry_type, amount, balance_after, idempotency_key, description
) VALUES (
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', 'credit', 'adjustment', 50000, 50000, 'seed-wallet-init-jean', 'Crédit initial compte de test'
);

UPDATE public.wallets
SET balance = 50000
WHERE id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1';

-- Utilisateur 2 : Client avec solde wallet nul (pour tester Mobile Money Jèko/Wave)
INSERT INTO auth.users (id, phone, encrypted_password)
VALUES
    ('99999999-9999-9999-9999-999999999992', '+2250202020202', '$2b$12$b1U49zKvNOPCTPe/xxkN4O23JkJ3D0i2XaOTBYNQ1jXqkFJ2ka1xK');

INSERT INTO public.customers (id, auth_user_id, first_name, last_name, phone, whatsapp_phone, email)
VALUES
    ('88888888-8888-8888-8888-888888888882', '99999999-9999-9999-9999-999999999992', 'Marie', 'Amani', '+2250202020202', '+2250202020202', 'marie.amani@jelani.test');

INSERT INTO public.wallets (id, customer_id, currency, balance, status)
VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2', '88888888-8888-8888-8888-888888888882', 'XOF', 0, 'active');

-- Utilisateur 3 : Opérateur de Gare / Contrôleur (pour scanner et embarquer)
INSERT INTO auth.users (id, phone, encrypted_password)
VALUES
    ('99999999-9999-9999-9999-999999999993', '+2250303030303', '$2b$12$b1U49zKvNOPCTPe/xxkN4O23JkJ3D0i2XaOTBYNQ1jXqkFJ2ka1xK');

INSERT INTO public.customers (id, auth_user_id, first_name, last_name, phone, whatsapp_phone, email)
VALUES
    ('88888888-8888-8888-8888-888888888883', '99999999-9999-9999-9999-999999999993', 'Seydou', 'Contrôleur', '+2250303030303', '+2250303030303', 'seydou.controleur@jelani.test');

INSERT INTO public.wallets (id, customer_id, currency, balance, status)
VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3', '88888888-8888-8888-8888-888888888883', 'XOF', 0, 'active');

-- ------------------------------------------------------------------------------
-- 4. TRAJETS (TRIPS) DIVERSIFIÉS RECOUVRANT TOUS LES CAS DU LIFECYCLE AUDITÉ
-- ------------------------------------------------------------------------------
-- Trip 1 : Futur Ouvert à la vente (Scheduled, demain 08:00 UTC)
INSERT INTO public.trips (
    id, line_id, partner_id, vehicle_id, driver_id, trip_date, departure_time,
    planned_start_datetime, planned_end_datetime, booking_close_at,
    status, capacity_total, capacity_blocked, capacity_booked, capacity_available, base_price
) VALUES (
    '77777777-7777-7777-7777-777777777701',
    '44444444-4444-4444-4444-444444444444', -- ABJ-YAM
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333333',
    CURRENT_DATE + INTERVAL '1 day',
    '08:00',
    (CURRENT_DATE + INTERVAL '1 day' + TIME '08:00') AT TIME ZONE 'UTC',
    (CURRENT_DATE + INTERVAL '1 day' + TIME '11:00') AT TIME ZONE 'UTC',
    (CURRENT_DATE + INTERVAL '1 day' + TIME '07:30') AT TIME ZONE 'UTC', -- Fermeture 30 min avant
    'scheduled', 18, 0, 0, 18, 5000
);

-- Trip 2 : Embarquement en cours (Boarding, départ dans 5 min)
INSERT INTO public.trips (
    id, line_id, partner_id, vehicle_id, driver_id, trip_date, departure_time,
    planned_start_datetime, planned_end_datetime, booking_close_at,
    status, capacity_total, capacity_blocked, capacity_booked, capacity_available, base_price
) VALUES (
    '77777777-7777-7777-7777-777777777702',
    '44444444-4444-4444-4444-444444444445', -- YOP-PLA
    '11111111-1111-1111-1111-111111111112',
    '22222222-2222-2222-2222-222222222223',
    '33333333-3333-3333-3333-333333333334',
    CURRENT_DATE,
    TO_CHAR(NOW() + INTERVAL '5 minutes', 'HH24:MI')::TIME,
    NOW() + INTERVAL '5 minutes',
    NOW() + INTERVAL '50 minutes',
    NOW() - INTERVAL '5 minutes', -- Ventes fermées
    'boarding', 14, 0, 0, 14, 1000
);

-- Trip 3 : Trajet Passé / Clôturé (Completed, il y a 2 jours) - Audit P0
INSERT INTO public.trips (
    id, line_id, partner_id, vehicle_id, driver_id, trip_date, departure_time,
    planned_start_datetime, planned_end_datetime, booking_close_at,
    status, capacity_total, capacity_blocked, capacity_booked, capacity_available, base_price
) VALUES (
    '77777777-7777-7777-7777-777777777703',
    '44444444-4444-4444-4444-444444444444', -- ABJ-YAM
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333333',
    CURRENT_DATE - INTERVAL '2 days',
    '07:00',
    (CURRENT_DATE - INTERVAL '2 days' + TIME '07:00') AT TIME ZONE 'UTC',
    (CURRENT_DATE - INTERVAL '2 days' + TIME '10:00') AT TIME ZONE 'UTC',
    (CURRENT_DATE - INTERVAL '2 days' + TIME '06:30') AT TIME ZONE 'UTC',
    'completed', 18, 0, 0, 18, 5000
);

-- Trip 4 : Trajet Complet (0 place dispo, après-demain)
INSERT INTO public.trips (
    id, line_id, partner_id, vehicle_id, driver_id, trip_date, departure_time,
    planned_start_datetime, planned_end_datetime, booking_close_at,
    status, capacity_total, capacity_blocked, capacity_booked, capacity_available, base_price
) VALUES (
    '77777777-7777-7777-7777-777777777704',
    '44444444-4444-4444-4444-444444444445', -- YOP-PLA
    '11111111-1111-1111-1111-111111111112',
    '22222222-2222-2222-2222-222222222223',
    '33333333-3333-3333-3333-333333333334',
    CURRENT_DATE + INTERVAL '2 days',
    '14:00',
    (CURRENT_DATE + INTERVAL '2 days' + TIME '14:00') AT TIME ZONE 'UTC',
    (CURRENT_DATE + INTERVAL '2 days' + TIME '15:00') AT TIME ZONE 'UTC',
    (CURRENT_DATE + INTERVAL '2 days' + TIME '13:30') AT TIME ZONE 'UTC',
    'scheduled', 14, 0, 14, 0, 1000
);

-- Trip 5 : Trajet Annulé
INSERT INTO public.trips (
    id, line_id, partner_id, vehicle_id, driver_id, trip_date, departure_time,
    planned_start_datetime, planned_end_datetime, booking_close_at,
    status, capacity_total, capacity_blocked, capacity_booked, capacity_available, base_price
) VALUES (
    '77777777-7777-7777-7777-777777777705',
    '44444444-4444-4444-4444-444444444444',
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333333',
    CURRENT_DATE + INTERVAL '3 days',
    '09:00',
    (CURRENT_DATE + INTERVAL '3 days' + TIME '09:00') AT TIME ZONE 'UTC',
    (CURRENT_DATE + INTERVAL '3 days' + TIME '12:00') AT TIME ZONE 'UTC',
    (CURRENT_DATE + INTERVAL '3 days' + TIME '08:30') AT TIME ZONE 'UTC',
    'cancelled', 18, 0, 0, 18, 5000
);

-- ------------------------------------------------------------------------------
-- 5. RÉSERVATIONS & PAIEMENTS (Couverture complète des états pour le client 1)
-- ------------------------------------------------------------------------------
-- 5.1. Réservation 1 : EN ATTENTE ACTIVE (Hold en cours, can_pay = true, 12 min restantes)
INSERT INTO public.bookings (
    id, trip_id, customer_id, pickup_stop_id, dropoff_stop_id, seats_reserved,
    unit_price, total_price, payment_status, booking_status, booking_channel,
    external_reference, expires_at, notes
) VALUES (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1',
    '77777777-7777-7777-7777-777777777701',
    '88888888-8888-8888-8888-888888888881',
    '55555555-5555-5555-5555-555555555551',
    '55555555-5555-5555-5555-555555555553',
    1, 5000, 5000, 'pending', 'pending', 'app',
    'JELANI-TEST-PENDING-ACTIVE',
    NOW() + INTERVAL '12 minutes',
    'Réservation de test - PENDING actif'
);

-- 5.2. Réservation 2 : EXPIRÉE (Hold dépassé, can_pay = false)
INSERT INTO public.bookings (
    id, trip_id, customer_id, pickup_stop_id, dropoff_stop_id, seats_reserved,
    unit_price, total_price, payment_status, booking_status, booking_channel,
    external_reference, expires_at, notes
) VALUES (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2',
    '77777777-7777-7777-7777-777777777701',
    '88888888-8888-8888-8888-888888888881',
    '55555555-5555-5555-5555-555555555551',
    '55555555-5555-5555-5555-555555555553',
    1, 5000, 5000, 'pending', 'expired', 'app',
    'JELANI-TEST-EXPIRED',
    NOW() - INTERVAL '30 minutes',
    'Réservation de test - Hold expiré'
);

-- 5.3. Réservation 3 : CONFIRMÉE & PAYÉE (Voyage à venir, Ticket UPCOMING avec QR)
INSERT INTO public.bookings (
    id, trip_id, customer_id, pickup_stop_id, dropoff_stop_id, seats_reserved,
    unit_price, total_price, payment_status, booking_status, booking_channel,
    external_reference, expires_at, notes
) VALUES (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb3',
    '77777777-7777-7777-7777-777777777701',
    '88888888-8888-8888-8888-888888888881',
    '55555555-5555-5555-5555-555555555551',
    '55555555-5555-5555-5555-555555555553',
    1, 5000, 5000, 'paid', 'confirmed', 'app',
    'JELANI-TEST-UPCOMING',
    NULL,
    'Réservation de test - Confirmée et payée'
);

INSERT INTO public.payments (
    id, booking_id, customer_id, amount, currency, provider,
    provider_reference, status, paid_at
) VALUES (
    'cccccccc-cccc-cccc-cccc-ccccccccccc3',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb3',
    '88888888-8888-8888-8888-888888888881',
    5000, 'XOF', 'wallet',
    'PAY-TEST-UPCOMING-001', 'success', NOW() - INTERVAL '1 hour'
);

-- 5.4. Réservation 4 : PRÊTE POUR SCAN / EMBARQUEMENT (Départ imminent sur Trip 2)
INSERT INTO public.bookings (
    id, trip_id, customer_id, pickup_stop_id, dropoff_stop_id, seats_reserved,
    unit_price, total_price, payment_status, booking_status, booking_channel,
    external_reference, expires_at, notes
) VALUES (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb4',
    '77777777-7777-7777-7777-777777777702', -- Trip 2 en boarding
    '88888888-8888-8888-8888-888888888881',
    '55555555-5555-5555-5555-555555555554',
    '55555555-5555-5555-5555-555555555556',
    1, 1000, 1000, 'paid', 'confirmed', 'app',
    'JELANI-TEST-BOARDING',
    NULL,
    'Réservation de test - Prête pour scan QR'
);

INSERT INTO public.payments (
    id, booking_id, customer_id, amount, currency, provider,
    provider_reference, status, paid_at
) VALUES (
    'cccccccc-cccc-cccc-cccc-ccccccccccc4',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb4',
    '88888888-8888-8888-8888-888888888881',
    1000, 'XOF', 'wallet',
    'PAY-TEST-BOARDING-001', 'success', NOW() - INTERVAL '20 minutes'
);

-- 5.5. Réservation 5 : DÉJÀ CONSOMMÉE (Boarded - Test double scan)
INSERT INTO public.bookings (
    id, trip_id, customer_id, pickup_stop_id, dropoff_stop_id, seats_reserved,
    unit_price, total_price, payment_status, booking_status, booking_channel,
    external_reference, expires_at, notes
) VALUES (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb5',
    '77777777-7777-7777-7777-777777777702',
    '88888888-8888-8888-8888-888888888881',
    '55555555-5555-5555-5555-555555555554',
    '55555555-5555-5555-5555-555555555556',
    1, 1000, 1000, 'paid', 'boarded', 'app',
    'JELANI-TEST-BOARDED',
    NULL,
    'Réservation de test - Déjà scannée'
);

INSERT INTO public.payments (
    id, booking_id, customer_id, amount, currency, provider,
    provider_reference, status, paid_at
) VALUES (
    'cccccccc-cccc-cccc-cccc-ccccccccccc5',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb5',
    '88888888-8888-8888-8888-888888888881',
    1000, 'XOF', 'wallet',
    'PAY-TEST-BOARDED-001', 'success', NOW() - INTERVAL '15 minutes'
);

-- 5.6. Réservation 6 : HISTORIQUE TERMINÉ (Completed)
INSERT INTO public.bookings (
    id, trip_id, customer_id, pickup_stop_id, dropoff_stop_id, seats_reserved,
    unit_price, total_price, payment_status, booking_status, booking_channel,
    external_reference, expires_at, notes
) VALUES (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb6',
    '77777777-7777-7777-7777-777777777703', -- Trip passé
    '88888888-8888-8888-8888-888888888881',
    '55555555-5555-5555-5555-555555555551',
    '55555555-5555-5555-5555-555555555553',
    2, 5000, 10000, 'paid', 'completed', 'app',
    'JELANI-TEST-COMPLETED',
    NULL,
    'Réservation de test - Voyage terminé'
);

INSERT INTO public.payments (
    id, booking_id, customer_id, amount, currency, provider,
    provider_reference, status, paid_at
) VALUES (
    'cccccccc-cccc-cccc-cccc-ccccccccccc6',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb6',
    '88888888-8888-8888-8888-888888888881',
    10000, 'XOF', 'paystack',
    'PAY-TEST-COMPLETED-001', 'success', CURRENT_DATE - INTERVAL '2 days'
);

-- 5.7. Réservation 7 : ANNULÉE
INSERT INTO public.bookings (
    id, trip_id, customer_id, pickup_stop_id, dropoff_stop_id, seats_reserved,
    unit_price, total_price, payment_status, booking_status, booking_channel,
    external_reference, expires_at, notes
) VALUES (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb7',
    '77777777-7777-7777-7777-777777777701',
    '88888888-8888-8888-8888-888888888881',
    '55555555-5555-5555-5555-555555555551',
    '55555555-5555-5555-5555-555555555553',
    1, 5000, 5000, 'refunded', 'cancelled', 'app',
    'JELANI-TEST-CANCELLED',
    NULL,
    'Réservation de test - Annulée et remboursée'
);

-- ------------------------------------------------------------------------------
-- 6. RECALCUL AUTOMATIQUE DES CAPACITÉS DES TRIPS
-- ------------------------------------------------------------------------------
SELECT recalculate_trip_capacity('77777777-7777-7777-7777-777777777701');
SELECT recalculate_trip_capacity('77777777-7777-7777-7777-777777777702');
SELECT recalculate_trip_capacity('77777777-7777-7777-7777-777777777703');
SELECT recalculate_trip_capacity('77777777-7777-7777-7777-777777777704');
SELECT recalculate_trip_capacity('77777777-7777-7777-7777-777777777705');

COMMIT;
