"""Add password resets table

Revision ID: e39e99f5e548
Revises: 2af3af56326c
Create Date: 2026-06-13 18:59:42.496636

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e39e99f5e548'
down_revision = '2af3af56326c'
branch_labels = None
depends_on = None


def upgrade():
    # Only create the password_resets table in auth schema
    op.create_table('password_resets',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('phone', sa.String(length=50), nullable=False),
    sa.Column('email', sa.String(length=100), nullable=False),
    sa.Column('otp_code', sa.String(length=10), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='auth'
    )
    with op.batch_alter_table('password_resets', schema='auth') as batch_op:
        batch_op.create_index(batch_op.f('ix_auth_password_resets_email'), ['email'], unique=False)
        batch_op.create_index(batch_op.f('ix_auth_password_resets_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_auth_password_resets_phone'), ['phone'], unique=False)


def downgrade():
    with op.batch_alter_table('password_resets', schema='auth') as batch_op:
        batch_op.drop_index(batch_op.f('ix_auth_password_resets_phone'))
        batch_op.drop_index(batch_op.f('ix_auth_password_resets_expires_at'))
        batch_op.drop_index(batch_op.f('ix_auth_password_resets_email'))

    op.drop_table('password_resets', schema='auth')
