"""cles d api hachees

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-07 21:14:43.478850

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Clés d'API : on remplace la clé en clair par son empreinte SHA-256."""
    op.add_column('machines', sa.Column('api_key_hash', sa.String(length=64), nullable=True))
    op.add_column('machines', sa.Column('api_key_prefix', sa.String(length=16), nullable=True))
    op.add_column('machines', sa.Column('api_key_created_at', sa.DateTime(), nullable=True))
    op.add_column('machines', sa.Column('api_key_revoked_at', sa.DateTime(), nullable=True))
    # Les clés existantes restent valables : on calcule leur empreinte dans PostgreSQL
    op.execute("""
        UPDATE machines SET
            api_key_hash = encode(sha256(convert_to(api_key, 'UTF8')), 'hex'),
            api_key_prefix = left(api_key, 12),
            api_key_created_at = created_at
    """)
    op.alter_column('machines', 'api_key_hash', nullable=False)
    op.alter_column('machines', 'api_key_prefix', nullable=False)
    op.drop_constraint(op.f('machines_api_key_key'), 'machines', type_='unique')
    op.create_unique_constraint('uq_machines_api_key_hash', 'machines', ['api_key_hash'])
    op.drop_column('machines', 'api_key')  # plus aucune clé en clair en base


def downgrade() -> None:
    """Impossible : une empreinte SHA-256 ne permet pas de retrouver la clé."""
    raise RuntimeError("Migration 0007 irréversible : les clés en clair n'existent plus. "
                       "Il faudrait régénérer les clés de toutes les machines.")
