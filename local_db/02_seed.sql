insert into partners (id, name, contact_name, contact_phone, base_location, status)
values
    ('11111111-1111-1111-1111-111111111111', 'Jelani Transport', 'Awa Coulibaly', '+2250100000001', 'Abidjan', 'active');

insert into vehicles (
    id,
    partner_id,
    plate_number,
    vehicle_code,
    brand,
    model,
    seat_capacity,
    standing_capacity,
    energy_type,
    status
) values (
    '22222222-2222-2222-2222-222222222222',
    '11111111-1111-1111-1111-111111111111',
    'AB-123-CD',
    'JEL-001',
    'Toyota',
    'Hiace',
    18,
    0,
    'diesel',
    'available'
);

insert into drivers (id, partner_id, first_name, last_name, phone, status)
values (
    '33333333-3333-3333-3333-333333333333',
    '11111111-1111-1111-1111-111111111111',
    'Moussa',
    'Kone',
    '+2250100000002',
    'active'
);

insert into lines (
    id,
    code,
    name,
    origin_name,
    destination_name,
    default_duration_minutes,
    default_price,
    status
) values (
    '44444444-4444-4444-4444-444444444444',
    'ABJ-YAM',
    'Abidjan - Yamoussoukro',
    'Abidjan',
    'Yamoussoukro',
    180,
    5000,
    'active'
);

insert into stops (id, name, city, district, latitude, longitude, status)
values
    ('55555555-5555-5555-5555-555555555551', 'Gare Nord', 'Abidjan', 'Adjamé', 5.365, -4.023, 'active'),
    ('55555555-5555-5555-5555-555555555552', 'Tiébissou Centre', 'Tiébissou', null, 7.157, -5.224, 'active'),
    ('55555555-5555-5555-5555-555555555553', 'Gare Yamoussoukro', 'Yamoussoukro', null, 6.827, -5.289, 'active');

insert into line_stops (id, line_id, stop_id, stop_order, scheduled_offset_minutes)
values
    ('66666666-6666-6666-6666-666666666661', '44444444-4444-4444-4444-444444444444', '55555555-5555-5555-5555-555555555551', 1, 0),
    ('66666666-6666-6666-6666-666666666662', '44444444-4444-4444-4444-444444444444', '55555555-5555-5555-5555-555555555552', 2, 110),
    ('66666666-6666-6666-6666-666666666663', '44444444-4444-4444-4444-444444444444', '55555555-5555-5555-5555-555555555553', 3, 180);

insert into trips (
    id,
    line_id,
    partner_id,
    vehicle_id,
    driver_id,
    trip_date,
    departure_time,
    planned_start_datetime,
    planned_end_datetime,
    status,
    capacity_total,
    capacity_blocked,
    capacity_booked,
    capacity_available,
    base_price
) values (
    '77777777-7777-7777-7777-777777777777',
    '44444444-4444-4444-4444-444444444444',
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333333',
    current_date + interval '1 day',
    '08:00',
    (current_date + interval '1 day' + time '08:00') at time zone 'UTC',
    (current_date + interval '1 day' + time '11:00') at time zone 'UTC',
    'scheduled',
    18,
    0,
    0,
    18,
    5000
);

insert into customers (id, first_name, last_name, phone, whatsapp_phone, email)
values (
    '88888888-8888-8888-8888-888888888888',
    'Jean',
    'Client',
    '+2250100000003',
    '+2250100000003',
    'jean.client@example.com'
);
