"""Tipos de amostra (grãos, folhas...) e as classes possíveis para cada um.

Estes registros são criados a partir dos arquivos em `taxonomias/*.yaml`
(ver app/servicos/taxonomias.py). Não são editados pela interface.
"""
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class TipoAmostra(db.Model):
    __tablename__ = 'tipo_amostra'

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)  # fixo, ex.: 'folhas'
    nome: Mapped[str] = mapped_column(String(80))                 # exibido, ex.: 'Folhas'
    descricao: Mapped[str | None] = mapped_column(Text)
    ordem: Mapped[int] = mapped_column(default=0)
    # Motor de segmentação automática (app/segmentacao). Vazio = ainda não há motor
    # para este tipo: as fotos precisam chegar já segmentadas.
    motor_padrao: Mapped[str | None] = mapped_column(String(40))

    classes: Mapped[list['Classe']] = relationship(
        back_populates='tipo_amostra', order_by='Classe.ordem'
    )

    @property
    def classes_ativas(self) -> list['Classe']:
        return [c for c in self.classes if c.ativa]

    def __repr__(self):
        return f'<TipoAmostra {self.codigo}>'


class Classe(db.Model):
    """Um rótulo possível para regiões de um tipo de amostra (ex.: 'Ferrugem')."""

    __tablename__ = 'classe'
    __table_args__ = (
        UniqueConstraint('tipo_amostra_id', 'codigo'),
        UniqueConstraint('tipo_amostra_id', 'tecla_atalho'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo_amostra_id: Mapped[int] = mapped_column(ForeignKey('tipo_amostra.id'))
    # O código nunca muda: renomear a classe (campo `nome`) não afeta dados antigos.
    codigo: Mapped[str] = mapped_column(String(40))
    nome: Mapped[str] = mapped_column(String(80))
    descricao: Mapped[str | None] = mapped_column(Text)
    cor: Mapped[str] = mapped_column(String(7))  # '#RRGGBB'
    tecla_atalho: Mapped[str | None] = mapped_column(String(1))
    ordem: Mapped[int] = mapped_column(default=0)
    # Classe retirada do YAML não é apagada (pode ter anotações): fica inativa.
    ativa: Mapped[bool] = mapped_column(default=True)

    tipo_amostra: Mapped[TipoAmostra] = relationship(back_populates='classes')

    def __repr__(self):
        return f'<Classe {self.codigo} ({self.tipo_amostra_id})>'
