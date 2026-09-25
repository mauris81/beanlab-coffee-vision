"""Contas com login (Fase L1).

Pessoa ganha usuário, senha (cifrada), perfil (membro/administrador), bloqueio após
tentativas erradas e versão da sessão. O antigo nome_normalizado sai.

Pessoas que já existiam (do "Quem é você?" só com nome) recebem um usuário gerado a
partir do nome e ficam SEM senha: continuam donas das suas anotações, mas só entram
depois que um administrador definir uma senha.

Revision ID: baa7e39a6f5b
Revises: 8b71c2082e0f
Create Date: 2026-09-25 20:36:00.736984

"""
import re
import unicodedata

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'baa7e39a6f5b'
down_revision = '8b71c2082e0f'
branch_labels = None
depends_on = None


def _usuario_a_partir_do_nome(nome: str) -> str:
    sem_acento = unicodedata.normalize('NFKD', nome or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9._-]', '', re.sub(r'\s+', '.', sem_acento.strip().casefold()))[:55] or 'pessoa'


def upgrade():
    # 1. Colunas novas com valores padrão (as linhas existentes precisam de um valor).
    with op.batch_alter_table('pessoa', schema=None) as batch_op:
        batch_op.add_column(sa.Column('usuario', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('senha_hash', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('papel', sa.Enum('membro', 'administrador', name='papel', native_enum=False, length=20),
                                      nullable=False, server_default='membro'))
        batch_op.add_column(sa.Column('precisa_trocar_senha', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('ultimo_acesso', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('tentativas_falhas', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('bloqueada_ate', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('versao_sessao', sa.Integer(), nullable=False, server_default='1'))

    # 2. Usuário para quem já existia, sem repetir (maria, maria.2, maria.3...).
    conexao = op.get_bind()
    usados = set()
    for pessoa_id, nome in conexao.execute(sa.text('SELECT id, nome FROM pessoa ORDER BY id')).all():
        base = _usuario_a_partir_do_nome(nome)
        usuario, n = base, 1
        while usuario in usados:
            n += 1
            usuario = f'{base}.{n}'
        usados.add(usuario)
        conexao.execute(sa.text('UPDATE pessoa SET usuario = :u WHERE id = :i'), {'u': usuario, 'i': pessoa_id})

    # 3. Agora sim: usuário obrigatório e único; sai o nome_normalizado.
    with op.batch_alter_table('pessoa', schema=None) as batch_op:
        batch_op.alter_column('usuario', existing_type=sa.String(length=60), nullable=False)
        batch_op.drop_constraint(batch_op.f('uq_pessoa_nome_normalizado'), type_='unique')
        batch_op.create_unique_constraint(batch_op.f('uq_pessoa_usuario'), ['usuario'])
        batch_op.drop_column('nome_normalizado')


def downgrade():
    with op.batch_alter_table('pessoa', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nome_normalizado', sa.VARCHAR(length=120), nullable=True))
    conexao = op.get_bind()
    usados = set()
    for pessoa_id, nome in conexao.execute(sa.text('SELECT id, nome FROM pessoa ORDER BY id')).all():
        normalizado, n = ' '.join((nome or '').split()).casefold(), 1
        candidato = normalizado
        while candidato in usados:
            n += 1
            candidato = f'{normalizado} ({n})'
        usados.add(candidato)
        conexao.execute(sa.text('UPDATE pessoa SET nome_normalizado = :n WHERE id = :i'), {'n': candidato, 'i': pessoa_id})
    with op.batch_alter_table('pessoa', schema=None) as batch_op:
        batch_op.alter_column('nome_normalizado', existing_type=sa.VARCHAR(length=120), nullable=False)
        batch_op.drop_constraint(batch_op.f('uq_pessoa_usuario'), type_='unique')
        batch_op.create_unique_constraint(batch_op.f('uq_pessoa_nome_normalizado'), ['nome_normalizado'])
        for coluna in ('versao_sessao', 'bloqueada_ate', 'tentativas_falhas', 'ultimo_acesso',
                       'precisa_trocar_senha', 'papel', 'senha_hash', 'usuario'):
            batch_op.drop_column(coluna)
