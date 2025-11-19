"""Add case-insensitive SKU unique index

Revision ID: 8793f5b13329
Revises: eb78c3354b97
Create Date: 2025-11-20 03:23:19.015581

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '8793f5b13329'
down_revision = 'eb78c3354b97'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create case-insensitive unique index on SKU
    op.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_products_sku_lower 
        ON products (LOWER(sku))
    """))


def downgrade() -> None:
    # Drop the case-insensitive unique index
    op.execute(text("DROP INDEX IF EXISTS ix_products_sku_lower"))

