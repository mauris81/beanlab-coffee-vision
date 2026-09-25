"""Coletas (um conjunto de fotos tiradas juntas) e suas imagens."""
from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dominio.pessoa import Pessoa
from app.dominio.taxonomia import TipoAmostra
from app.dominio.tipos import OrigemImagem, StatusImagem, agora_utc, tipo_enum
from app.extensions import db


class Coleta(db.Model):
    """Ex.: "Folhas do talhão 3, fazenda Boa Vista, 12/03". Substitui o antigo 'Projeto'."""

    __tablename__ = 'coleta'

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo_amostra_id: Mapped[int] = mapped_column(ForeignKey('tipo_amostra.id'))
    nome: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(Text)
    fazenda: Mapped[str | None] = mapped_column(String(120))
    talhao: Mapped[str | None] = mapped_column(String(80))
    variedade: Mapped[str | None] = mapped_column(String(80))
    data_coleta: Mapped[date | None]
    coletor_id: Mapped[int | None] = mapped_column(ForeignKey('pessoa.id'))
    criada_em: Mapped[datetime] = mapped_column(default=agora_utc)
    atualizada_em: Mapped[datetime] = mapped_column(default=agora_utc, onupdate=agora_utc)

    tipo_amostra: Mapped[TipoAmostra] = relationship()
    coletor: Mapped[Pessoa | None] = relationship()
    imagens: Mapped[list['Imagem']] = relationship(
        back_populates='coleta', cascade='all, delete-orphan', passive_deletes=True,
        order_by='Imagem.id',
    )

    def __repr__(self):
        return f'<Coleta {self.id} {self.nome!r}>'


class Imagem(db.Model):
    """Uma foto. O arquivo fica no disco com o nome igual ao hash do conteúdo
    (ver app/armazenamento/imagens.py); aqui guardamos só os dados sobre ela."""

    __tablename__ = 'imagem'
    __table_args__ = (
        # A mesma foto não entra duas vezes na mesma coleta.
        UniqueConstraint('coleta_id', 'hash_sha256'),
        CheckConstraint('largura > 0 AND altura > 0', name='dimensoes_positivas'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    coleta_id: Mapped[int] = mapped_column(ForeignKey('coleta.id', ondelete='CASCADE'), index=True)
    hash_sha256: Mapped[str] = mapped_column(String(64), index=True)
    extensao: Mapped[str] = mapped_column(String(5))  # 'jpg', 'png'...
    nome_original: Mapped[str] = mapped_column(String(255))
    largura: Mapped[int]
    altura: Mapped[int]
    tamanho_bytes: Mapped[int]
    # Lidos do EXIF da foto, quando existem.
    capturada_em: Mapped[datetime | None]
    latitude: Mapped[float | None]
    longitude: Mapped[float | None]

    origem: Mapped[OrigemImagem] = mapped_column(tipo_enum(OrigemImagem))
    status: Mapped[StatusImagem] = mapped_column(
        tipo_enum(StatusImagem), default=StatusImagem.AGUARDANDO
    )
    # Verdadeiro quando a foto já chegou recortada/segmentada e não passa por um motor.
    ja_segmentada: Mapped[bool] = mapped_column(default=False)
    enviada_por_id: Mapped[int | None] = mapped_column(ForeignKey('pessoa.id'))
    enviada_em: Mapped[datetime] = mapped_column(default=agora_utc)

    coleta: Mapped[Coleta] = relationship(back_populates='imagens')
    enviada_por: Mapped[Pessoa | None] = relationship()
    regioes: Mapped[list['Regiao']] = relationship(  # noqa: F821 (definida em regiao.py)
        back_populates='imagem', cascade='all, delete-orphan', passive_deletes=True,
        order_by='Regiao.id',
    )
    jobs: Mapped[list['JobSegmentacao']] = relationship(  # noqa: F821 (definida em job.py)
        back_populates='imagem', cascade='all, delete-orphan', passive_deletes=True,
        order_by='JobSegmentacao.id',
    )

    def __repr__(self):
        return f'<Imagem {self.id} {self.nome_original!r}>'
