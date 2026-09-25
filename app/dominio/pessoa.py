"""Quem coleta e quem anota.

Por enquanto cada pessoa se identifica só pelo nome, sem senha (decisão no
docs/ROADMAP.md). Campos de login entram por migração se isso for decidido.
"""
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.dominio.tipos import agora_utc
from app.extensions import db


class Pessoa(db.Model):
    __tablename__ = 'pessoa'

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    # Nome em minúsculas e sem espaços extras: "Maria  Silva" e "maria silva"
    # são a mesma pessoa.
    nome_normalizado: Mapped[str] = mapped_column(String(120), unique=True)
    ativa: Mapped[bool] = mapped_column(default=True)
    criada_em: Mapped[datetime] = mapped_column(default=agora_utc)

    @staticmethod
    def normalizar(nome: str) -> str:
        return ' '.join(nome.split()).casefold()

    def __repr__(self):
        return f'<Pessoa {self.nome}>'
