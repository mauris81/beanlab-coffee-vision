"""Regras para anotar regiões e medir o progresso de uma coleta."""
from dataclasses import dataclass

from sqlalchemy import func, select

from app.dominio import Anotacao, Classe, Imagem, OrigemAnotacao, Pessoa, Regiao
from app.extensions import db


class AnotacaoInvalida(ValueError):
    """A anotação pedida quebra alguma regra. A mensagem explica qual."""


def anotar_regiao(regiao: Regiao, classe: Classe, *, pessoa: Pessoa | None = None,
                  confianca: float | None = None, observacao: str | None = None,
                  origem: OrigemAnotacao = OrigemAnotacao.MANUAL) -> Anotacao:
    """Registra que `regiao` é da `classe`. Não confirma (commit): quem chama decide.

    Não altera anotações anteriores: acrescenta uma nova, que passa a ser a vigente.
    """
    tipo = regiao.imagem.coleta.tipo_amostra
    if classe.tipo_amostra_id != tipo.id:
        raise AnotacaoInvalida(f'A classe "{classe.nome}" não é uma classe de {tipo.nome}.')
    if not classe.ativa:
        raise AnotacaoInvalida(f'A classe "{classe.nome}" foi desativada e não aceita novas anotações.')
    if confianca is not None and not 0 <= confianca <= 1:
        raise AnotacaoInvalida(f'A confiança deve estar entre 0 e 1 (recebeu {confianca}).')

    anotacao = Anotacao(
        regiao=regiao, classe=classe, pessoa=pessoa, confianca=confianca,
        observacao=(observacao or '').strip() or None, origem=origem,
    )
    db.session.add(anotacao)
    db.session.flush()
    return anotacao


@dataclass(frozen=True)
class Progresso:
    total: int
    anotadas: int
    por_classe: dict[str, int]  # código da classe -> nº de regiões cuja anotação vigente é ela

    @property
    def pendentes(self) -> int:
        return self.total - self.anotadas

    @property
    def percentual(self) -> float:
        return round(100 * self.anotadas / self.total, 1) if self.total else 0.0


def progresso_da_coleta(coleta_id: int) -> Progresso:
    """Conta regiões anotadas e pendentes de uma coleta, direto no banco.

    "Anotada" = tem ao menos uma anotação. A classe que conta é a da anotação
    vigente, ou seja, a de maior id da região (ids só crescem, e anotações nunca
    são editadas).
    """
    da_coleta = Imagem.coleta_id == coleta_id

    total = db.session.scalar(
        select(func.count(Regiao.id)).join(Regiao.imagem).where(da_coleta))

    anotadas = db.session.scalar(
        select(func.count(func.distinct(Anotacao.regiao_id)))
        .join(Anotacao.regiao).join(Regiao.imagem).where(da_coleta))

    vigentes = (
        select(func.max(Anotacao.id))
        .join(Anotacao.regiao).join(Regiao.imagem).where(da_coleta)
        .group_by(Anotacao.regiao_id)
    )
    por_classe = dict(db.session.execute(
        select(Classe.codigo, func.count(Anotacao.id))
        .join(Anotacao.classe)
        .where(Anotacao.id.in_(vigentes))
        .group_by(Classe.codigo)
    ).all())

    return Progresso(total=total, anotadas=anotadas, por_classe=por_classe)
