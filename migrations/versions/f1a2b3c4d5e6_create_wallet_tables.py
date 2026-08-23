"""Create wallet tables (wallets, wallet_entries, wallet_topups)

Revision ID: f1a2b3c4d5e6
Revises: e39e99f5e548
Create Date: 2026-08-05 10:00:00.000000

Le schéma vivant (public.*) est géré en SQL brut par
infrastructure/supabase_write_repositories.py : cette révision utilise
op.execute() plutôt que l'autogénération, qui tenterait de réconcilier les
modèles morts de models/clients.py avec la base.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'e39e99f5e548'
branch_labels = None
depends_on = None


def upgrade():
    # gen_random_uuid() est natif sur Supabase ; sur une base locale l'extension
    # doit être présente (elle l'est déjà via local_db/01_schema.sql).
    op.execute("create extension if not exists pgcrypto;")

    op.execute(
        """
        create table if not exists public.wallets (
            id            uuid primary key default gen_random_uuid(),
            customer_id   uuid not null unique references public.customers(id) on delete restrict,
            currency      char(3) not null default 'XOF',
            balance       bigint  not null default 0 check (balance >= 0),
            status        text    not null default 'active' check (status in ('active','frozen')),
            created_at    timestamptz not null default timezone('utc', now()),
            updated_at    timestamptz not null default timezone('utc', now())
        );
        """
    )

    op.execute(
        """
        create table if not exists public.wallet_entries (
            id                  uuid primary key default gen_random_uuid(),
            wallet_id           uuid not null references public.wallets(id) on delete restrict,
            direction           text not null check (direction in ('credit','debit')),
            entry_type          text not null check (entry_type in (
                                    'topup','booking_payment','booking_refund',
                                    'topup_reversal','adjustment','promo_credit')),
            amount              bigint not null check (amount > 0),
            balance_after       bigint not null,
            reference_type      text check (reference_type in ('topup','booking','payment','manual')),
            reference_id        uuid,
            idempotency_key     text not null unique,
            description         text,
            metadata            jsonb,
            created_at          timestamptz not null default timezone('utc', now())
        );
        """
    )
    op.execute(
        """
        create index if not exists ix_wallet_entries_wallet_created
            on public.wallet_entries (wallet_id, created_at desc);
        """
    )
    op.execute(
        """
        create index if not exists ix_wallet_entries_reference
            on public.wallet_entries (reference_type, reference_id);
        """
    )

    op.execute(
        """
        create table if not exists public.wallet_topups (
            id                    uuid primary key default gen_random_uuid(),
            wallet_id             uuid not null references public.wallets(id) on delete restrict,
            customer_id           uuid not null references public.customers(id) on delete restrict,
            amount                bigint not null check (amount > 0),
            currency              char(3) not null default 'XOF',
            provider              text not null,
            provider_method       text,
            provider_reference    text not null unique,
            provider_payment_url  text,
            status                text not null default 'pending'
                                    check (status in ('pending','success','failed','expired')),
            raw_provider_response jsonb,
            credited_at           timestamptz,
            created_at            timestamptz not null default timezone('utc', now()),
            updated_at            timestamptz not null default timezone('utc', now())
        );
        """
    )
    op.execute(
        """
        create index if not exists ix_wallet_topups_customer_created
            on public.wallet_topups (customer_id, created_at desc);
        """
    )
    op.execute(
        """
        create index if not exists ix_wallet_topups_status
            on public.wallet_topups (status) where status = 'pending';
        """
    )


def downgrade():
    op.execute("drop table if exists public.wallet_topups;")
    op.execute("drop table if exists public.wallet_entries;")
    op.execute("drop table if exists public.wallets;")
