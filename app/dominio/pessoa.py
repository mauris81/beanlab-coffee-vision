"""Quem usa a plataforma: contas com usuário e senha, criadas pelo administrador.

Regras de acesso (quem cria contas, bloqueio após tentativas erradas...) ficam em
app/servicos/contas.py. Aqui só os dados.
"""
import enum
import re
import unicodedata
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.dominio.tipos import agora_utc, tipo_enum
from app.extensions import db


class Papel(enum.StrEnum):
    MEMBRO = 'membro'                # coleta e anota
    ADMINISTRADOR = 'administrador'  # também cuida das contas


class Pessoa(db.Model):
    __tablename__ = 'pessoa'

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))           # como aparece na tela
    usuario: Mapped[str] = mapped_column(String(60), unique=True)  # para entrar; ver normalizar_usuario
    senha_hash: Mapped[str | None] = mapped_column(String(255))    # vazio = ainda não pode entrar
    papel: Mapped[Papel] = mapped_column(tipo_enum(Papel), default=Papel.MEMBRO)
    ativa: Mapped[bool] = mapped_column(default=True)
    # Senha criada pelo administrador é provisória: a pessoa troca no primeiro acesso.
    precisa_trocar_senha: Mapped[bool] = mapped_column(default=False)
    criada_em: Mapped[datetime] = mapped_column(default=agora_utc)
    ultimo_acesso: Mapped[datetime | None]
    # Proteção contra quem tenta adivinhar senhas.
    tentativas_falhas: Mapped[int] = mapped_column(default=0)
    bloqueada_ate: Mapped[datetime | None]
    # Muda quando a senha é trocada ou a conta desativada: as sessões antigas (outros
    # aparelhos) deixam de valer na hora.
    versao_sessao: Mapped[int] = mapped_column(default=1)
    # Conta excluída que já tinha trabalho: nome, usuário e senha foram apagados, mas o
    # registro fica para as anotações continuarem ligadas a "alguém" (sem identificar).
    removida_em: Mapped[datetime | None]

    @property
    def eh_administrador(self) -> bool:
        return self.papel == Papel.ADMINISTRADOR

    @staticmethod
    def normalizar_usuario(texto: str) -> str:
        """'Maria Silva' -> 'maria.silva'. Minúsculas, sem acento, só letras, números, . _ -"""
        sem_acento = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode()
        return re.sub(r'[^a-z0-9._-]', '', re.sub(r'\s+', '.', sem_acento.strip().casefold()))[:60]

    def __repr__(self):
        return f'<Pessoa {self.usuario}>'
