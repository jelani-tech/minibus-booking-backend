"""Backfill one wallet per existing customer

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-08-05 10:05:00.000000

Un wallet actif pour chaque client existant, afin que GET /api/wallet réponde
sans écriture au premier appel. Rejouable sans effet de bord.

La création paresseuse côté applicatif (SupabaseWalletRepository.get_or_create)
reste indispensable malgré ce backfill : les clients créés après la migration
n'y sont pas.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a7b8c9d0e1f2'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        insert into public.wallets (customer_id)
        select c.id from public.customers c
        on conflict (customer_id) do nothing;
        """
    )


def downgrade():
    # Ne supprime que les wallets vierges : un wallet avec un solde ou des
    # écritures représente de l'argent client, jamais effacé par un downgrade.
    op.execute(
        """
        delete from public.wallets w
        where w.balance = 0
          and not exists (
              select 1 from public.wallet_entries e where e.wallet_id = w.id
          )
          and not exists (
              select 1 from public.wallet_topups t where t.wallet_id = w.id
          );
        """
    )
