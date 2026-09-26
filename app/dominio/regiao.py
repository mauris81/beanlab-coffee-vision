"""Regiões (um objeto dentro da foto) e as anotações feitas sobre elas.

Duas regras importantes:
- Uma região está PENDENTE quando não tem nenhuma anotação. Isso é calculado,
  nunca gravado como texto (o antigo 'Pendente' contava como anotado).
- Anotações só são ACRESCENTADAS, nunca editadas. Mudar de ideia cria uma nova
  anotação; a vigente é sempre a mais recente. Assim temos histórico completo.
"""
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dominio.coleta import Imagem
from app.dominio.geometria import area_do_poligono, bbox_do_poligono, validar_poligono
from app.dominio.pessoa import Pessoa
from app.dominio.taxonomia import Classe
from app.dominio.tipos import OrigemAnotacao, OrigemRegiao, agora_utc, tipo_enum
from app.extensions import db


class Regiao(db.Model):
    __tablename__ = 'regiao'
    __table_args__ = (
        CheckConstraint('area_px > 0', name='area_positiva'),
        CheckConstraint('pontuacao IS NULL OR (pontuacao >= 0 AND pontuacao <= 1)',
                        name='pontuacao_entre_0_e_1'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    imagem_id: Mapped[int] = mapped_column(ForeignKey('imagem.id', ondelete='CASCADE'), index=True)
    # Contorno: lista de [x, y] em pixels da imagem original. É a fonte da verdade;
    # recortes e máscaras são gerados a partir dele.
    poligono: Mapped[list] = mapped_column(JSON)
    # Retângulo envolvente (formato COCO), em colunas separadas para permitir consultas.
    bbox_x: Mapped[int]
    bbox_y: Mapped[int]
    bbox_largura: Mapped[int]
    bbox_altura: Mapped[int]
    area_px: Mapped[int]  # área real do objeto, não da caixa

    origem: Mapped[OrigemRegiao] = mapped_column(tipo_enum(OrigemRegiao))
    motor: Mapped[str | None] = mapped_column(String(40))         # ex.: 'classico'
    versao_motor: Mapped[str | None] = mapped_column(String(40))  # ex.: '1.0'
    pontuacao: Mapped[float | None]  # confiança do motor (0 a 1), quando ele informa
    criada_em: Mapped[datetime] = mapped_column(default=agora_utc)

    imagem: Mapped[Imagem] = relationship(back_populates='regioes')
    anotacoes: Mapped[list['Anotacao']] = relationship(
        back_populates='regiao', cascade='all, delete-orphan', passive_deletes=True,
        order_by='Anotacao.id',
    )

    @classmethod
    def do_poligono(cls, pontos, *, origem: OrigemRegiao, area_px: int | None = None,
                    **outros_campos) -> 'Regiao':
        """Cria a região a partir do contorno, calculando bbox e área.

        `area_px` pode ser informada pelo motor (contagem exata de pixels da máscara);
        senão, é calculada pelo polígono.
        """
        pontos = validar_poligono(pontos)
        x, y, largura, altura = bbox_do_poligono(pontos)
        return cls(
            poligono=pontos, bbox_x=x, bbox_y=y, bbox_largura=largura, bbox_altura=altura,
            area_px=area_px if area_px is not None else area_do_poligono(pontos),
            origem=origem, **outros_campos,
        )

    @property
    def bbox(self) -> list[int]:
        return [self.bbox_x, self.bbox_y, self.bbox_largura, self.bbox_altura]

    @property
    def anotacao_vigente(self) -> 'Anotacao | None':
        return self.anotacoes[-1] if self.anotacoes else None

    @property
    def pendente(self) -> bool:
        return not self.anotacoes

    def __repr__(self):
        return f'<Regiao {self.id} imagem={self.imagem_id}>'


class Anotacao(db.Model):
    """"Esta região é da classe X", dito por alguém em um momento."""

    __tablename__ = 'anotacao'
    __table_args__ = (
        CheckConstraint('confianca IS NULL OR (confianca >= 0 AND confianca <= 1)',
                        name='confianca_entre_0_e_1'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    regiao_id: Mapped[int] = mapped_column(ForeignKey('regiao.id', ondelete='CASCADE'), index=True)
    # RESTRICT: uma classe com anotações não pode ser apagada (só desativada).
    classe_id: Mapped[int] = mapped_column(ForeignKey('classe.id', ondelete='RESTRICT'), index=True)
    pessoa_id: Mapped[int | None] = mapped_column(ForeignKey('pessoa.id'), index=True)
    origem: Mapped[OrigemAnotacao] = mapped_column(
        tipo_enum(OrigemAnotacao), default=OrigemAnotacao.MANUAL
    )
    confianca: Mapped[float | None]  # quão segura a pessoa está (0 a 1)
    observacao: Mapped[str | None] = mapped_column(Text)
    # Índice: o painel conta as anotações dos últimos dias (app/servicos/painel.py).
    criada_em: Mapped[datetime] = mapped_column(default=agora_utc, index=True)

    regiao: Mapped[Regiao] = relationship(back_populates='anotacoes')
    classe: Mapped[Classe] = relationship()
    pessoa: Mapped[Pessoa | None] = relationship()

    def __repr__(self):
        return f'<Anotacao regiao={self.regiao_id} classe={self.classe_id}>'
