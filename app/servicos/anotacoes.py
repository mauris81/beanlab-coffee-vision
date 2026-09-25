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


# ------------------------------------------------------------- tela de anotação

CONFIANCA_DUVIDA = 0.5  # "Tenho dúvida" na tela vira esta confiança


@dataclass(frozen=True)
class SituacaoRegiao:
    """Uma região e sua anotação vigente (se houver), para montar a tela de anotação."""
    id: int
    imagem_id: int
    bbox: list[int]
    poligono: list[list[int]]
    anotacao_id: int | None
    classe: str | None          # código da classe vigente
    duvida: bool
    observacao: str | None


def situacao_das_regioes(coleta_id: int) -> list[SituacaoRegiao]:
    """Todas as regiões da coleta, na ordem de anotação (foto, depois região), numa consulta só."""
    vigentes = (
        select(Anotacao.regiao_id, func.max(Anotacao.id).label('anotacao_id'))
        .group_by(Anotacao.regiao_id).subquery()
    )
    linhas = db.session.execute(
        select(Regiao, Anotacao, Classe.codigo)
        .join(Regiao.imagem)
        .outerjoin(vigentes, vigentes.c.regiao_id == Regiao.id)
        .outerjoin(Anotacao, Anotacao.id == vigentes.c.anotacao_id)
        .outerjoin(Classe, Classe.id == Anotacao.classe_id)
        .where(Imagem.coleta_id == coleta_id)
        .order_by(Imagem.id, Regiao.id)
    ).all()
    return [
        SituacaoRegiao(
            id=regiao.id, imagem_id=regiao.imagem_id, bbox=regiao.bbox, poligono=regiao.poligono,
            anotacao_id=anotacao.id if anotacao else None, classe=codigo,
            duvida=bool(anotacao and anotacao.confianca is not None
                        and anotacao.confianca < 1),
            observacao=anotacao.observacao if anotacao else None,
        )
        for regiao, anotacao, codigo in linhas
    ]


def anotar_em_lote(regioes: list[Regiao], classe: Classe, *, pessoa: Pessoa | None = None) -> list[Anotacao]:
    """Aplica a mesma classe a várias regiões. Não confirma (commit)."""
    return [anotar_regiao(regiao, classe, pessoa=pessoa) for regiao in regioes]


def desfazer_anotacoes(ids: list[int], pessoa: Pessoa) -> int:
    """Apaga anotações recém-feitas, para corrigir um engano. Não confirma (commit).

    Só apaga as que forem da própria pessoa E ainda forem a vigente da região: ninguém
    desfaz o trabalho de outra pessoa, nem uma anotação que já foi substituída.
    Mudar de ideia depois não é "desfazer": é anotar de novo (fica no histórico).
    Devolve quantas foram apagadas.
    """
    apagadas = 0
    for anotacao in db.session.scalars(select(Anotacao).where(Anotacao.id.in_(ids))).all():
        vigente = db.session.scalar(
            select(func.max(Anotacao.id)).where(Anotacao.regiao_id == anotacao.regiao_id))
        if anotacao.pessoa_id == pessoa.id and anotacao.id == vigente:
            db.session.delete(anotacao)
            apagadas += 1
    db.session.flush()
    return apagadas
