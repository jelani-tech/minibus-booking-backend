"""Audit: sales deadline and pending hold expiry index.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
"""
from alembic import op

revision = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None

def upgrade():
    # PostgreSQL needs the enum value committed before it can be used.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE public.booking_status ADD VALUE IF NOT EXISTS 'expired'")
    op.execute("ALTER TABLE public.trips ADD COLUMN IF NOT EXISTS booking_close_at timestamptz")
    op.execute("CREATE INDEX IF NOT EXISTS bookings_pending_expiry_idx ON public.bookings (trip_id, expires_at) WHERE booking_status = 'pending'")

def downgrade():
    # Retain the enum value: removing it would destroy historical state.
    op.execute("DROP INDEX IF EXISTS public.bookings_pending_expiry_idx")
    op.execute("ALTER TABLE public.trips DROP COLUMN IF EXISTS booking_close_at")
