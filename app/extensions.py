"""Extensões compartilhadas por toda a aplicação (banco de dados e migrações)."""
import sqlite3

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    # Nomes previsíveis para chaves e restrições. Sem isso, o Alembic não consegue
    # alterar ou remover restrições no SQLite em migrações futuras.
    metadata = MetaData(naming_convention={
        'ix': 'ix_%(column_0_label)s',
        'uq': 'uq_%(table_name)s_%(column_0_N_name)s',
        'ck': 'ck_%(table_name)s_%(constraint_name)s',
        'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
        'pk': 'pk_%(table_name)s',
    })


db = SQLAlchemy(model_class=Base)
migrate = Migrate()


@event.listens_for(Engine, 'connect')
def _configurar_sqlite(conexao, _registro):
    """Liga, em toda conexão SQLite, duas proteções que vêm desligadas por padrão."""
    if not isinstance(conexao, sqlite3.Connection):
        return
    cursor = conexao.cursor()
    # Impede, por exemplo, uma anotação apontando para uma classe que não existe.
    cursor.execute('PRAGMA foreign_keys = ON')
    # Registro prévio das gravações: o banco resiste a quedas de energia e permite
    # ler enquanto outra pessoa grava.
    cursor.execute('PRAGMA journal_mode = WAL')
    cursor.close()
