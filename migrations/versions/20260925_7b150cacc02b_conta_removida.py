"""Conta removida (exclusão de contas).

Adiciona pessoa.removida_em. Contas excluídas que já tinham trabalho perdem nome,
usuário e senha, mas o registro fica para as anotações continuarem ligadas a ele.
Não muda nenhum dado existente (a coluna nasce vazia).

Revision ID: 7b150cacc02b
Revises: c03c2a0e38cb
Create Date: 2026-09-25 23:18:17.456848

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b150cacc02b'
down_revision = 'c03c2a0e38cb'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('pessoa', schema=None) as batch_op:
        batch_op.add_column(sa.Column('removida_em', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('pessoa', schema=None) as batch_op:
        batch_op.drop_column('removida_em')
