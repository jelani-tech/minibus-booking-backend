-- DROP SCHEMA clients;

CREATE SCHEMA clients AUTHORIZATION "user";

-- DROP TYPE clients."client_payment_method";

CREATE TYPE clients."client_payment_method" AS ENUM (
	'WALLET',
	'OM',
	'MOMO',
	'MM',
	'WAVE',
	'CREDIT_CARD',
	'CASH');

-- DROP TYPE clients."client_transaction_type";

CREATE TYPE clients."client_transaction_type" AS ENUM (
	'TRANSPORT_FEES',
	'WALLET_CREDITING');

-- DROP SEQUENCE clients.bookings_id_seq;

CREATE SEQUENCE clients.bookings_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 2147483647
	START 1
	CACHE 1
	NO CYCLE;
-- DROP SEQUENCE clients.payments_id_seq;

CREATE SEQUENCE clients.payments_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 2147483647
	START 1
	CACHE 1
	NO CYCLE;-- clients.accounts definition

-- Drop table

-- DROP TABLE clients.accounts;

CREATE TABLE clients.accounts (
	id uuid NOT NULL,
	client_id uuid NOT NULL,
	balance float8 NOT NULL,
	updated_at timestamp NULL,
	CONSTRAINT accounts_pkey PRIMARY KEY (id)
);


-- clients.bookings definition

-- Drop table

-- DROP TABLE clients.bookings;

CREATE TABLE clients.bookings (
	id serial4 NOT NULL,
	user_id int4 NOT NULL,
	trip_id int4 NOT NULL,
	number_of_seats int4 NOT NULL,
	total_price float8 NOT NULL,
	status varchar(20) NULL,
	passenger_name varchar(100) NOT NULL,
	passenger_phone varchar(20) NOT NULL,
	created_at timestamp NULL,
	CONSTRAINT bookings_pkey PRIMARY KEY (id)
);


-- clients.clients definition

-- Drop table

-- DROP TABLE clients.clients;

CREATE TABLE clients.clients (
	id uuid NOT NULL,
	user_id int4 NOT NULL,
	created_at timestamp NULL,
	updated_at timestamp NULL,
	CONSTRAINT clients_pkey PRIMARY KEY (id)
);


-- clients.payments definition

-- Drop table

-- DROP TABLE clients.payments;

CREATE TABLE clients.payments (
	id serial4 NOT NULL,
	booking_id int4 NOT NULL,
	amount float8 NOT NULL,
	payment_method varchar(20) NOT NULL,
	transaction_id varchar(100) NULL,
	status varchar(20) NULL,
	payment_provider_response text NULL,
	created_at timestamp NULL,
	updated_at timestamp NULL,
	CONSTRAINT payments_booking_id_key UNIQUE (booking_id),
	CONSTRAINT payments_pkey PRIMARY KEY (id),
	CONSTRAINT payments_transaction_id_key UNIQUE (transaction_id)
);


-- clients.transactions definition

-- Drop table

-- DROP TABLE clients.transactions;

CREATE TABLE clients.transactions (
	id uuid NOT NULL,
	client_id uuid NOT NULL,
	"type" clients."client_transaction_type" NOT NULL,
	amount float8 NOT NULL,
	departure varchar(100) NULL,
	arrival varchar(100) NULL,
	payment_method clients."client_payment_method" NULL,
	created_at timestamp NULL,
	updated_at timestamp NULL,
	CONSTRAINT transactions_pkey PRIMARY KEY (id)
);


-- clients.trips definition

-- Drop table

-- DROP TABLE clients.trips;

CREATE TABLE clients.trips (
	id uuid NOT NULL,
	client_id uuid NOT NULL,
	step_number int4 NOT NULL,
	created_at timestamp NULL,
	CONSTRAINT trips_pkey PRIMARY KEY (id)
);


-- clients.accounts foreign keys

ALTER TABLE clients.accounts ADD CONSTRAINT accounts_client_id_fkey FOREIGN KEY (client_id) REFERENCES clients.clients(id);


-- clients.bookings foreign keys

ALTER TABLE clients.bookings ADD CONSTRAINT bookings_trip_id_fkey FOREIGN KEY (trip_id) REFERENCES partners.scheduled_trips(id);
ALTER TABLE clients.bookings ADD CONSTRAINT bookings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


-- clients.clients foreign keys

ALTER TABLE clients.clients ADD CONSTRAINT clients_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


-- clients.payments foreign keys

ALTER TABLE clients.payments ADD CONSTRAINT payments_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES clients.bookings(id);


-- clients.transactions foreign keys

ALTER TABLE clients.transactions ADD CONSTRAINT transactions_client_id_fkey FOREIGN KEY (client_id) REFERENCES clients.clients(id);


-- clients.trips foreign keys

ALTER TABLE clients.trips ADD CONSTRAINT trips_client_id_fkey FOREIGN KEY (client_id) REFERENCES clients.clients(id);

-- DROP SCHEMA common;

CREATE SCHEMA common AUTHORIZATION "user";

-- DROP SCHEMA partners;

CREATE SCHEMA partners AUTHORIZATION "user";

-- DROP TYPE partners."partner_payment_method";

CREATE TYPE partners."partner_payment_method" AS ENUM (
	'WALLET',
	'OM',
	'MOMO',
	'MM',
	'WAVE',
	'CREDIT_CARD',
	'CASH');

-- DROP TYPE partners."partner_transaction_type";

CREATE TYPE partners."partner_transaction_type" AS ENUM (
	'TRANSPORT_FEES',
	'WITHDRAWL');

-- DROP SEQUENCE partners.scheduled_trips_id_seq;

CREATE SEQUENCE partners.scheduled_trips_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 2147483647
	START 1
	CACHE 1
	NO CYCLE;-- partners.scheduled_trips definition

-- Drop table

-- DROP TABLE partners.scheduled_trips;

CREATE TABLE partners.scheduled_trips (
	id serial4 NOT NULL,
	departure_city varchar(100) NOT NULL,
	arrival_city varchar(100) NOT NULL,
	departure_time timestamp NOT NULL,
	arrival_time timestamp NOT NULL,
	price float8 NOT NULL,
	available_seats int4 NOT NULL,
	total_seats int4 NOT NULL,
	driver_name varchar(100) NOT NULL,
	driver_phone varchar(20) NOT NULL,
	vehicle_number varchar(50) NOT NULL,
	status varchar(20) NULL,
	created_at timestamp NULL,
	CONSTRAINT scheduled_trips_pkey PRIMARY KEY (id)
);


-- partners.accounts definition

-- Drop table

-- DROP TABLE partners.accounts;

CREATE TABLE partners.accounts (
	id uuid NOT NULL,
	partner_id uuid NOT NULL,
	balance float8 NOT NULL,
	updated_at timestamp NULL,
	CONSTRAINT accounts_pkey PRIMARY KEY (id)
);


-- partners.partners definition

-- Drop table

-- DROP TABLE partners.partners;

CREATE TABLE partners.partners (
	id uuid NOT NULL,
	user_id int4 NOT NULL,
	created_at timestamp NULL,
	updated_at timestamp NULL,
	CONSTRAINT partners_pkey PRIMARY KEY (id)
);


-- partners.transactions definition

-- Drop table

-- DROP TABLE partners.transactions;

CREATE TABLE partners.transactions (
	id uuid NOT NULL,
	partner_id uuid NOT NULL,
	"type" partners."partner_transaction_type" NOT NULL,
	amount float8 NOT NULL,
	departure varchar(100) NULL,
	arrival varchar(100) NULL,
	payment_method partners."partner_payment_method" NULL,
	created_at timestamp NULL,
	updated_at timestamp NULL,
	CONSTRAINT transactions_pkey PRIMARY KEY (id)
);


-- partners.accounts foreign keys

ALTER TABLE partners.accounts ADD CONSTRAINT accounts_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES partners.partners(id);


-- partners.partners foreign keys

ALTER TABLE partners.partners ADD CONSTRAINT partners_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


-- partners.transactions foreign keys

ALTER TABLE partners.transactions ADD CONSTRAINT transactions_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES partners.partners(id);

-- DROP SCHEMA public;

CREATE SCHEMA public AUTHORIZATION pg_database_owner;

-- DROP SEQUENCE public.bookings_id_seq;

CREATE SEQUENCE public.bookings_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 2147483647
	START 1
	CACHE 1
	NO CYCLE;
-- DROP SEQUENCE public.payments_id_seq;

CREATE SEQUENCE public.payments_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 2147483647
	START 1
	CACHE 1
	NO CYCLE;
-- DROP SEQUENCE public.trips_id_seq;

CREATE SEQUENCE public.trips_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 2147483647
	START 1
	CACHE 1
	NO CYCLE;
-- DROP SEQUENCE public.users_id_seq;

CREATE SEQUENCE public.users_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 2147483647
	START 1
	CACHE 1
	NO CYCLE;-- public.trips definition

-- Drop table

-- DROP TABLE public.trips;

CREATE TABLE public.trips (
	id serial4 NOT NULL,
	departure_city varchar(100) NOT NULL,
	arrival_city varchar(100) NOT NULL,
	departure_time timestamp NOT NULL,
	arrival_time timestamp NOT NULL,
	price numeric(10, 2) NOT NULL,
	available_seats int4 DEFAULT 18 NOT NULL,
	total_seats int4 DEFAULT 18 NOT NULL,
	driver_name varchar(100) NOT NULL,
	driver_phone varchar(20) NOT NULL,
	vehicle_number varchar(50) NOT NULL,
	status varchar(20) DEFAULT 'active'::character varying NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT trips_pkey PRIMARY KEY (id)
);
CREATE INDEX idx_trips_arrival ON public.trips USING btree (arrival_city);
CREATE INDEX idx_trips_departure ON public.trips USING btree (departure_city);
CREATE INDEX idx_trips_departure_time ON public.trips USING btree (departure_time);


-- public.users definition

-- Drop table

-- DROP TABLE public.users;

CREATE TABLE public.users (
	id serial4 NOT NULL,
	"name" varchar(100) NOT NULL,
	phone varchar(20) NOT NULL,
	email varchar(100) NULL,
	password_hash varchar(255) NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT users_email_key UNIQUE (email),
	CONSTRAINT users_phone_key UNIQUE (phone),
	CONSTRAINT users_pkey PRIMARY KEY (id)
);


-- public.bookings definition

-- Drop table

-- DROP TABLE public.bookings;

CREATE TABLE public.bookings (
	id serial4 NOT NULL,
	user_id int4 NOT NULL,
	trip_id int4 NOT NULL,
	number_of_seats int4 DEFAULT 1 NOT NULL,
	total_price numeric(10, 2) NOT NULL,
	status varchar(20) DEFAULT 'pending'::character varying NULL,
	passenger_name varchar(100) NOT NULL,
	passenger_phone varchar(20) NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT bookings_pkey PRIMARY KEY (id),
	CONSTRAINT bookings_trip_id_fkey FOREIGN KEY (trip_id) REFERENCES public.trips(id) ON DELETE CASCADE,
	CONSTRAINT bookings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
);
CREATE INDEX idx_bookings_trip_id ON public.bookings USING btree (trip_id);
CREATE INDEX idx_bookings_user_id ON public.bookings USING btree (user_id);


-- public.payments definition

-- Drop table

-- DROP TABLE public.payments;

CREATE TABLE public.payments (
	id serial4 NOT NULL,
	booking_id int4 NOT NULL,
	amount numeric(10, 2) NOT NULL,
	payment_method varchar(20) NOT NULL,
	transaction_id varchar(100) NULL,
	status varchar(20) DEFAULT 'pending'::character varying NULL,
	payment_provider_response text NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT payments_booking_id_key UNIQUE (booking_id),
	CONSTRAINT payments_pkey PRIMARY KEY (id),
	CONSTRAINT payments_transaction_id_key UNIQUE (transaction_id),
	CONSTRAINT payments_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(id) ON DELETE CASCADE
);
CREATE INDEX idx_payments_booking_id ON public.payments USING btree (booking_id);
CREATE INDEX idx_payments_transaction_id ON public.payments USING btree (transaction_id);