create extension if not exists pgcrypto;

-- ============================================================
-- Schema AUTH : gestion des identifiants (inspire de Supabase)
-- La table auth.users stocke uniquement les credentials.
-- Le profil metier reste dans public.customers.
-- ============================================================
create schema if not exists auth;

create table auth.users (
    id               uuid primary key default gen_random_uuid(),
    phone            text unique not null,
    encrypted_password text not null,
    created_at       timestamptz not null default timezone('utc', now()),
    updated_at       timestamptz not null default timezone('utc', now())
);

create table auth.password_resets (
    id uuid primary key default gen_random_uuid(),
    phone text not null,
    email text not null,
    otp_code text not null,
    expires_at timestamptz not null,
    used boolean not null default false,
    created_at timestamptz not null default timezone('utc', now())
);

create index password_resets_phone_idx on auth.password_resets (phone);
create index password_resets_email_idx on auth.password_resets (lower(email));
create index password_resets_expires_at_idx on auth.password_resets (expires_at);

create type partner_status as enum ('pending', 'active', 'inactive');
create type vehicle_energy_type as enum ('diesel', 'essence', 'electric', 'hybrid');
create type vehicle_status as enum ('available', 'assigned', 'maintenance', 'inactive');
create type driver_status as enum ('active', 'inactive', 'suspended');
create type line_status as enum ('draft', 'active', 'inactive');
create type stop_status as enum ('active', 'inactive');
create type trip_status as enum ('scheduled', 'boarding', 'departed', 'completed', 'cancelled');
create type payment_status as enum ('pending', 'paid', 'failed', 'refunded');
create type booking_status as enum ('pending', 'confirmed', 'cancelled', 'boarded', 'no_show', 'completed');
create type booking_channel as enum ('whatsapp', 'admin', 'app', 'agent');

create table partners (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    contact_name text,
    contact_phone text,
    contact_email text,
    base_location text,
    status partner_status not null default 'pending',
    notes text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create unique index partners_name_unique_idx on partners (lower(name));

create table vehicles (
    id uuid primary key default gen_random_uuid(),
    partner_id uuid not null references partners(id),
    plate_number text not null,
    vehicle_code text not null,
    brand text,
    model text,
    seat_capacity integer not null check (seat_capacity >= 1),
    standing_capacity integer not null default 0 check (standing_capacity >= 0),
    total_capacity integer generated always as (seat_capacity + standing_capacity) stored,
    energy_type vehicle_energy_type not null default 'diesel',
    status vehicle_status not null default 'available',
    registration_expiry_date date,
    insurance_expiry_date date,
    inspection_expiry_date date,
    notes text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index vehicles_partner_id_idx on vehicles (partner_id);
create index vehicles_status_idx on vehicles (status);
create unique index vehicles_plate_number_unique_idx on vehicles (lower(plate_number));
create unique index vehicles_vehicle_code_unique_idx on vehicles (lower(vehicle_code));

create table drivers (
    id uuid primary key default gen_random_uuid(),
    partner_id uuid not null references partners(id),
    first_name text not null,
    last_name text,
    phone text not null,
    license_number text,
    license_expiry_date date,
    status driver_status not null default 'active',
    notes text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index drivers_partner_id_idx on drivers (partner_id);
create index drivers_phone_idx on drivers (phone);
create index drivers_status_idx on drivers (status);

create table lines (
    id uuid primary key default gen_random_uuid(),
    code text not null,
    name text not null,
    origin_name text not null,
    destination_name text not null,
    default_duration_minutes integer check (default_duration_minutes is null or default_duration_minutes > 0),
    default_price numeric check (default_price is null or default_price >= 0),
    status line_status not null default 'draft',
    notes text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create unique index lines_code_unique_idx on lines (lower(code));
create index lines_status_idx on lines (status);

create table stops (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    city text,
    district text,
    latitude numeric check (latitude is null or latitude between -90 and 90),
    longitude numeric check (longitude is null or longitude between -180 and 180),
    landmark text,
    status stop_status not null default 'active',
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index stops_name_idx on stops (lower(name));
create index stops_city_idx on stops (lower(city));
create index stops_status_idx on stops (status);

create table line_stops (
    id uuid primary key default gen_random_uuid(),
    line_id uuid not null references lines(id),
    stop_id uuid not null references stops(id),
    stop_order integer not null check (stop_order >= 1),
    is_pickup_allowed boolean not null default true,
    is_dropoff_allowed boolean not null default true,
    scheduled_offset_minutes integer not null default 0 check (scheduled_offset_minutes >= 0),
    created_at timestamptz not null default timezone('utc', now()),
    unique (line_id, stop_id),
    unique (line_id, stop_order)
);

create index line_stops_line_id_idx on line_stops (line_id);
create index line_stops_stop_id_idx on line_stops (stop_id);

create table trips (
    id uuid primary key default gen_random_uuid(),
    line_id uuid not null references lines(id),
    partner_id uuid not null references partners(id),
    vehicle_id uuid not null references vehicles(id),
    driver_id uuid references drivers(id),
    trip_date date not null,
    departure_time time not null,
    planned_start_datetime timestamptz not null,
    planned_end_datetime timestamptz,
    status trip_status not null default 'scheduled',
    capacity_total integer not null check (capacity_total >= 1),
    capacity_blocked integer not null default 0 check (capacity_blocked >= 0),
    capacity_booked integer not null default 0 check (capacity_booked >= 0),
    capacity_available integer not null default 0 check (capacity_available >= 0),
    base_price numeric check (base_price is null or base_price >= 0),
    notes text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index trips_line_id_idx on trips (line_id);
create index trips_partner_id_idx on trips (partner_id);
create index trips_vehicle_id_idx on trips (vehicle_id);
create index trips_driver_id_idx on trips (driver_id);
create index trips_trip_date_idx on trips (trip_date);
create index trips_status_idx on trips (status);
create index trips_planned_start_idx on trips (planned_start_datetime);

create table customers (
    id uuid primary key default gen_random_uuid(),
    -- Lien vers auth.users (nullable : un client peut exister sans compte app)
    auth_user_id     uuid unique references auth.users(id) on delete set null,
    first_name text not null,
    last_name text,
    phone text not null,
    whatsapp_phone text,
    email text,
    notes text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index customers_phone_idx on customers (phone);
create index customers_whatsapp_phone_idx on customers (whatsapp_phone);
create index customers_email_idx on customers (lower(email));
create index customers_auth_user_id_idx on customers (auth_user_id);

create table bookings (
    id uuid primary key default gen_random_uuid(),
    trip_id uuid not null references trips(id),
    customer_id uuid not null references customers(id),
    pickup_stop_id uuid references stops(id),
    dropoff_stop_id uuid references stops(id),
    seats_reserved integer not null default 1 check (seats_reserved >= 1),
    unit_price numeric not null check (unit_price >= 0),
    total_price numeric not null check (total_price >= 0),
    payment_status payment_status not null default 'pending',
    booking_status booking_status not null default 'pending',
    booking_channel booking_channel not null default 'admin',
    external_reference text,
    notes text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    expires_at timestamptz
);

create index bookings_trip_id_idx on bookings (trip_id);
create index bookings_customer_id_idx on bookings (customer_id);
create index bookings_pickup_stop_id_idx on bookings (pickup_stop_id);
create index bookings_dropoff_stop_id_idx on bookings (dropoff_stop_id);
create index bookings_booking_status_idx on bookings (booking_status);
create index bookings_payment_status_idx on bookings (payment_status);
create index bookings_created_at_idx on bookings (created_at);

create table payments (
    id uuid primary key default gen_random_uuid(),
    booking_id uuid not null references bookings(id),
    customer_id uuid references customers(id),
    amount numeric not null,
    currency text not null default 'XOF',
    provider text not null default 'jeko',
    provider_reference text,
    provider_payment_url text,
    status text not null default 'pending',
    paid_at timestamptz,
    raw_provider_response jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index payments_booking_id_idx on payments (booking_id);
create index payments_customer_id_idx on payments (customer_id);

create or replace function set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$;

create or replace function recalculate_trip_capacity(target_trip_id uuid)
returns void
language plpgsql
set search_path = public
as $$
declare
    booked integer;
begin
    select coalesce(sum(seats_reserved), 0)
    into booked
    from bookings
    where trip_id = target_trip_id
      and booking_status in ('pending', 'confirmed', 'boarded');

    update trips
    set capacity_booked = booked,
        capacity_available = greatest(capacity_total - capacity_blocked - booked, 0),
        updated_at = timezone('utc', now())
    where id = target_trip_id;
end;
$$;

create or replace function trg_recalculate_trip_capacity()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    if tg_op in ('INSERT', 'UPDATE') then
        perform recalculate_trip_capacity(new.trip_id);
    end if;
    if tg_op in ('UPDATE', 'DELETE') and old.trip_id is distinct from coalesce(new.trip_id, old.trip_id) then
        perform recalculate_trip_capacity(old.trip_id);
    elsif tg_op = 'DELETE' then
        perform recalculate_trip_capacity(old.trip_id);
    end if;
    return null;
end;
$$;

create or replace function set_trip_capacity_from_vehicle()
returns trigger
language plpgsql
set search_path = public
as $$
declare
    vehicle_capacity integer;
begin
    select total_capacity into vehicle_capacity
    from vehicles
    where id = new.vehicle_id;

    if new.capacity_total is null then
        new.capacity_total = vehicle_capacity;
    end if;

    new.capacity_available = greatest(new.capacity_total - new.capacity_blocked - new.capacity_booked, 0);
    return new;
end;
$$;

create trigger trg_auth_users_updated_at before update on auth.users for each row execute function set_updated_at();
create trigger trg_partners_updated_at before update on partners for each row execute function set_updated_at();
create trigger trg_vehicles_updated_at before update on vehicles for each row execute function set_updated_at();
create trigger trg_drivers_updated_at before update on drivers for each row execute function set_updated_at();
create trigger trg_lines_updated_at before update on lines for each row execute function set_updated_at();
create trigger trg_stops_updated_at before update on stops for each row execute function set_updated_at();
create trigger trg_trips_updated_at before update on trips for each row execute function set_updated_at();
create trigger trg_bookings_updated_at before update on bookings for each row execute function set_updated_at();
create trigger trg_trips_set_capacity_from_vehicle before insert or update on trips for each row execute function set_trip_capacity_from_vehicle();
create trigger trg_bookings_recalculate_trip_capacity after insert or update or delete on bookings for each row execute function trg_recalculate_trip_capacity();

create view trip_load_summary as
select
    t.id as trip_id,
    t.trip_date,
    t.departure_time,
    t.planned_start_datetime,
    t.planned_end_datetime,
    t.status as trip_status,
    l.id as line_id,
    l.code as line_code,
    l.name as line_name,
    l.origin_name,
    l.destination_name,
    p.id as partner_id,
    p.name as partner_name,
    v.id as vehicle_id,
    v.vehicle_code,
    v.plate_number,
    v.brand,
    v.model,
    d.id as driver_id,
    d.first_name as driver_first_name,
    d.last_name as driver_last_name,
    concat_ws(' ', d.first_name, d.last_name) as driver_full_name,
    d.phone as driver_phone,
    t.capacity_total,
    t.capacity_blocked,
    t.capacity_booked,
    t.capacity_available,
    round((t.capacity_booked::numeric / nullif(t.capacity_total, 0)) * 100, 2) as load_factor_percent,
    t.base_price,
    t.notes,
    t.created_at,
    t.updated_at
from trips t
join lines l on l.id = t.line_id
join partners p on p.id = t.partner_id
join vehicles v on v.id = t.vehicle_id
left join drivers d on d.id = t.driver_id;

create view booking_details as
select
    b.id as booking_id,
    b.created_at as booking_created_at,
    b.updated_at as booking_updated_at,
    b.booking_status,
    b.payment_status,
    b.booking_channel,
    b.external_reference,
    b.notes as booking_notes,
    b.seats_reserved,
    b.unit_price,
    b.total_price,
    c.id as customer_id,
    c.first_name as customer_first_name,
    c.last_name as customer_last_name,
    concat_ws(' ', c.first_name, c.last_name) as customer_full_name,
    c.phone as customer_phone,
    c.whatsapp_phone,
    c.email as customer_email,
    tls.*
from bookings b
join customers c on c.id = b.customer_id
join trip_load_summary tls on tls.trip_id = b.trip_id;

create view daily_operations as
select
    trip_id,
    trip_date,
    departure_time,
    planned_start_datetime,
    planned_end_datetime,
    trip_status,
    line_name,
    origin_name,
    destination_name,
    partner_name,
    vehicle_code,
    plate_number,
    driver_full_name,
    driver_phone,
    capacity_total,
    capacity_booked,
    capacity_available,
    load_factor_percent,
    case
        when capacity_available = 0 then 'full'
        when load_factor_percent >= 80 then 'nearly_full'
        else 'available'
    end as occupancy_status,
    base_price,
    notes
from trip_load_summary;

create view vehicle_availability as
select
    v.id as vehicle_id,
    v.vehicle_code,
    v.plate_number,
    v.brand,
    v.model,
    v.seat_capacity,
    v.standing_capacity,
    v.total_capacity,
    v.energy_type,
    v.status as vehicle_status,
    p.id as partner_id,
    p.name as partner_name,
    t.id as assigned_trip_id,
    t.trip_date as assigned_trip_date,
    t.departure_time as assigned_departure_time,
    t.status as assigned_trip_status,
    t.line_id as assigned_line_id,
    l.name as assigned_line_name,
    t.id is not null as is_assigned
from vehicles v
join partners p on p.id = v.partner_id
left join trips t on t.vehicle_id = v.id and t.status in ('scheduled', 'boarding', 'departed')
left join lines l on l.id = t.line_id;

alter table partners enable row level security;
alter table vehicles enable row level security;
alter table drivers enable row level security;
alter table lines enable row level security;
alter table stops enable row level security;
alter table line_stops enable row level security;
alter table trips enable row level security;
alter table customers enable row level security;
alter table bookings enable row level security;
alter table payments enable row level security;

create policy "Allow public read active lines" on lines for select using (status = 'active');
create policy "Allow public read active stops" on stops for select using (status = 'active');
create policy "Allow public read line stops for active lines" on line_stops for select using (
    exists (select 1 from lines l where l.id = line_stops.line_id and l.status = 'active')
);
create policy "Allow public read available trips" on trips for select using (
    status in ('scheduled', 'boarding') and capacity_available > 0
);
