CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE SCHEMA IF NOT EXISTS clients;
CREATE SCHEMA IF NOT EXISTS partners;
CREATE SCHEMA IF NOT EXISTS common;

CREATE TYPE clients.transaction_type AS ENUM ('TRANSPORT_FEES', 'WALLET_CREDITING');

CREATE TYPE partners.transaction_type AS ENUM ('TRANSPORT_FEES', 'WITHDRAWL');

CREATE TYPE common.payment_method AS ENUM ('WALLET', 'OM', 'MOMO', 'MM', 'WAVE', 'CREDIT_CARD', 'CASH');

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE clients.clients ( 
    client_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), 
    created_at timestamptz DEFAULT now() NOT NULL, 
    updated_at timestamptz DEFAULT now() NOT NULL, 
    user_id UUID NOT NULL,
    CONSTRAINT fk_client_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
);

CREATE TABLE clients.accounts (
    account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL,
    balance FLOAT NOT NULL DEFAULT 0.0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_client FOREIGN KEY (client_id) REFERENCES clients.clients(client_id) ON DELETE CASCADE
);

CREATE TABLE clients.trips (
    trip_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL,
    step_number INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_client_trip FOREIGN KEY (client_id) REFERENCES clients.clients(client_id) ON DELETE CASCADE
);

CREATE TABLE clients.transactions (
    transaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL,
    type clients.transaction_type NOT NULL,
    amount FLOAT NOT NULL,
    departure TEXT,
    arrival TEXT,
    payment_method common.payment_method,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_client_transaction FOREIGN KEY (client_id) REFERENCES clients.clients(client_id) ON DELETE CASCADE
);

CREATE TABLE partners.partners (
    partner_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE partners.accounts (
    account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    partner_id UUID NOT NULL,
    balance FLOAT NOT NULL DEFAULT 0.0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_partner FOREIGN KEY (partner_id) REFERENCES partners.partners(partner_id) ON DELETE CASCADE
);

CREATE TABLE partners.transactions (
    transaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    partner_id UUID NOT NULL,
    type partners.transaction_type NOT NULL,
    amount FLOAT NOT NULL DEFAULT 0.0,
    departure TEXT,
    arrival TEXT,
    payment_method common.payment_method,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_partner_transaction FOREIGN KEY (partner_id) REFERENCES partners.partners(partner_id) ON DELETE CASCADE
);

CREATE TABLE common.stations (
    station_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE common.lines (
    line_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    direction TEXT,
    stop_number INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE common.stops (
    stop_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    line_id UUID NOT NULL,
    station_id UUID NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    latitude DECIMAL(10, 7) NOT NULL,
    "order" INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_line FOREIGN KEY (line_id) REFERENCES common.lines(line_id) ON DELETE CASCADE,
    CONSTRAINT fk_station FOREIGN KEY (station_id) REFERENCES common.stations(station_id) ON DELETE CASCADE
);

CREATE TABLE common.steps (
    step_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID NOT NULL,
    client_transaction_id UUID NOT NULL,
    partner_transaction_id UUID NOT NULL,
    partner_id UUID,
    status TEXT NOT NULL,
    "order" INT NOT NULL,
    departure TEXT NOT NULL,
    arrival TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_trip FOREIGN KEY (trip_id) REFERENCES clients.trips(trip_id) ON DELETE CASCADE,
    CONSTRAINT fk_client_trans FOREIGN KEY (client_transaction_id) REFERENCES clients.transactions(transaction_id) ON DELETE CASCADE,
    CONSTRAINT fk_partner_trans FOREIGN KEY (partner_transaction_id) REFERENCES partners.transactions(transaction_id) ON DELETE CASCADE,
    CONSTRAINT fk_partner FOREIGN KEY (partner_id) REFERENCES partners.partners(partner_id) ON DELETE SET NULL
);

CREATE INDEX idx_client_accounts ON clients.accounts(client_id);
CREATE INDEX idx_client_trips ON clients.trips(client_id);
CREATE INDEX idx_client_transactions ON clients.transactions(client_id);
CREATE INDEX idx_client_transactions_created ON clients.transactions(created_at DESC);

CREATE INDEX idx_partner_accounts ON partners.accounts(partner_id);
CREATE INDEX idx_partner_transactions ON partners.transactions(partner_id);
CREATE INDEX idx_partner_transactions_created ON partners.transactions(created_at DESC);

CREATE INDEX idx_stops_line ON common.stops(line_id);
CREATE INDEX idx_stops_station ON common.stops(station_id);
CREATE INDEX idx_steps_trip ON common.steps(trip_id);
CREATE INDEX idx_steps_partner ON common.steps(partner_id);
CREATE INDEX idx_steps_status ON common.steps(status);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_clients_updated_at BEFORE UPDATE ON clients.clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_client_accounts_updated_at BEFORE UPDATE ON clients.accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_partners_updated_at BEFORE UPDATE ON partners.partners
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_partner_accounts_updated_at BEFORE UPDATE ON partners.accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_stations_updated_at BEFORE UPDATE ON common.stations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_lines_updated_at BEFORE UPDATE ON common.lines
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_stops_updated_at BEFORE UPDATE ON common.stops
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_steps_updated_at BEFORE UPDATE ON common.steps
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();