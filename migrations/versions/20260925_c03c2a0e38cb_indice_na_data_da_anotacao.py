"""Índice na data da anotação (Fase 4).

O painel conta as anotações dos últimos dias; com o índice o banco lê só esses dias,
em vez da tabela inteira. Não muda nenhum dado.

Revision ID: c03c2a0e38cb
Revises: baa7e39a6f5b
Create Date: 2026-09-25 23:01:27.817050

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c03c2a0e38cb'
down_revision = 'baa7e39a6f5b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('anotacao', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_anotacao_criada_em'), ['criada_em'], unique=False)


def downgrade():
    with op.batch_alter_table('anotacao', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_anotacao_criada_em'))
