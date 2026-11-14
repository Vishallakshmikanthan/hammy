"""Initial schema with 16 core tables and constraints

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-14 07:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from infrastructure.database.connection import Base
import infrastructure.database.models  # Ensure all models are registered

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create all 16 tables defined in Base.metadata
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    # Drop tables in reverse dependency order
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

