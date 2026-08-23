"""Trigger guard: wallet_entries.balance_after must match the wallet balance

Revision ID: b3c4d5e6f7a8
Revises: a7b8c9d0e1f2
Create Date: 2026-08-05 10:10:00.000000

Filet de sécurité (§ 4.3 de la spec) : rejette toute écriture dont le
balance_after ne correspond pas au solde courant du wallet plus ou moins le
montant. L'invariant de conservation est ainsi garanti par la base, et pas
seulement par la convention « tout passe par post_entry() ».

Le trigger est un BEFORE INSERT : il s'exécute donc AVANT que
SupabaseWalletRepository.post_entry() ne mette à jour wallets.balance, et lit
bien le solde d'avant le mouvement.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b3c4d5e6f7a8'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        create or replace function public.wallet_entry_balance_guard()
        returns trigger
        language plpgsql
        set search_path = public
        as $$
        declare
            current_balance bigint;
            expected_balance bigint;
        begin
            select balance into current_balance
            from public.wallets
            where id = new.wallet_id
            for update;

            if current_balance is null then
                raise exception 'wallet % not found', new.wallet_id;
            end if;

            if new.direction = 'credit' then
                expected_balance := current_balance + new.amount;
            else
                expected_balance := current_balance - new.amount;
            end if;

            if new.balance_after is distinct from expected_balance then
                raise exception
                    'wallet_entries.balance_after % does not match expected % '
                    '(wallet %, balance %, % of %)',
                    new.balance_after, expected_balance, new.wallet_id,
                    current_balance, new.direction, new.amount;
            end if;

            if expected_balance < 0 then
                raise exception 'wallet % would go negative (% - %)',
                    new.wallet_id, current_balance, new.amount;
            end if;

            return new;
        end;
        $$;
        """
    )
    op.execute(
        """
        drop trigger if exists wallet_entry_balance_guard on public.wallet_entries;
        create trigger wallet_entry_balance_guard
            before insert on public.wallet_entries
            for each row execute function public.wallet_entry_balance_guard();
        """
    )


def downgrade():
    op.execute("drop trigger if exists wallet_entry_balance_guard on public.wallet_entries;")
    op.execute("drop function if exists public.wallet_entry_balance_guard();")
