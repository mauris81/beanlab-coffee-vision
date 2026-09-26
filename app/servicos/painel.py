"""Números do painel (página inicial): progresso por tipo de amostra, distribuição das
classes, o que precisa de atenção e a atividade da equipe.

Tudo é contado direto no banco (COUNT/SUM agrupados), sem carregar fotos nem regiões.
Uma consulta resume cada coleta; os números por tipo saem da soma desses resumos. Com
20 mil regiões o painel inteiro leva cerca de 0,1 s (tests/test_painel.py confere que o número
de consultas não cresce com o número de coletas).

As regras são as mesmas do resto da plataforma (servicos/anotacoes.py):
- região ANOTADA = tem ao menos uma anotação; vale a classe da anotação VIGENTE (a de
  maior id da região);
- EM DÚVIDA = a anotação vigente tem confiança menor que 1 ("Tenho dúvida" na tela).
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field, fields
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import case, func, select

from app.dominio import Anotacao, Classe, Coleta, Imagem, Pessoa, Regiao, StatusImagem, TipoAmostra
from app.extensions import db

DIAS_DE_ATIVIDADE = 14
DIAS_POR_PESSOA = 30
MAXIMO_PARA_CONTINUAR = 5
MAXIMO_POR_AVISO = 5


# ------------------------------------------------------------------- números

@dataclass
class Numeros:
    coletas: int = 0
    fotos: int = 0
    fotos_na_fila: int = 0   # esperando ou em segmentação
    fotos_com_erro: int = 0
    regioes: int = 0
    anotadas: int = 0
    duvidas: int = 0

    @property
    def pendentes(self) -> int:
        return self.regioes - self.anotadas

    @property
    def percentual(self) -> float:
        return round(100 * self.anotadas / self.regioes, 1) if self.regioes else 0.0

    def __add__(self, outro: 'Numeros') -> 'Numeros':
        return Numeros(**{campo.name: getattr(self, campo.name) + getattr(outro, campo.name)
                          for campo in fields(self)})


def _vigentes():
    """Subconsulta: para cada região anotada, o id da anotação vigente."""
    return (select(Anotacao.regiao_id, func.max(Anotacao.id).label('anotacao_id'))
            .group_by(Anotacao.regiao_id).subquery())


def _em_duvida():
    """1 se a anotação vigente (já unida na consulta) está em dúvida; senão 0."""
    return func.coalesce(func.sum(case((Anotacao.confianca < 1, 1), else_=0)), 0)


def numeros_por_tipo(resumos: list['ColetaResumida'] | None = None) -> dict[int, Numeros]:
    """id do tipo de amostra -> seus números, somando os resumos das coletas."""
    numeros: dict[int, Numeros] = defaultdict(Numeros)
    for resumo in resumo_das_coletas() if resumos is None else resumos:
        numeros[resumo.coleta.tipo_amostra_id] += Numeros(
            coletas=1, fotos=resumo.fotos, fotos_na_fila=resumo.fotos_na_fila,
            fotos_com_erro=resumo.fotos_com_erro, regioes=resumo.regioes, anotadas=resumo.anotadas,
            duvidas=resumo.duvidas)
    return dict(numeros)


# ------------------------------------------------------------------- classes

@dataclass(frozen=True)
class FatiaDeClasse:
    classe: Classe
    quantidade: int      # regiões cuja anotação vigente é esta classe
    percentual: float    # das regiões anotadas do tipo


def contagem_por_classe() -> dict[int, int]:
    """id da classe -> nº de regiões cuja anotação vigente é essa classe (todos os tipos)."""
    vigentes = _vigentes()
    return dict(db.session.execute(
        select(Anotacao.classe_id, func.count(Anotacao.id)).select_from(vigentes)
        .join(Anotacao, Anotacao.id == vigentes.c.anotacao_id)
        .group_by(Anotacao.classe_id)).all())


def fatias_do_tipo(tipo: TipoAmostra, contagem: dict[int, int]) -> list[FatiaDeClasse]:
    """Classes do tipo na ordem da taxonomia, com quantidade e percentual. Classes
    desativadas só aparecem se ainda tiverem regiões anotadas com elas."""
    total = sum(contagem.get(classe.id, 0) for classe in tipo.classes)
    return [FatiaDeClasse(classe, contagem.get(classe.id, 0),
                          round(100 * contagem.get(classe.id, 0) / total, 1) if total else 0.0)
            for classe in tipo.classes if classe.ativa or contagem.get(classe.id)]


# ------------------------------------------------------------------- coletas

@dataclass(frozen=True)
class ColetaResumida:
    coleta: Coleta
    fotos: int
    fotos_na_fila: int
    fotos_com_erro: int
    regioes: int
    anotadas: int
    duvidas: int
    ultima_anotacao: datetime | None

    @property
    def pendentes(self) -> int:
        return self.regioes - self.anotadas

    @property
    def atividade_recente(self) -> datetime:
        """Para ordenar: a última anotação ou, se ainda não houver, a criação da coleta."""
        return self.ultima_anotacao or self.coleta.criada_em


def resumo_das_coletas(tipo_id: int | None = None) -> list[ColetaResumida]:
    vigentes = _vigentes()
    regioes = (
        select(Imagem.coleta_id.label('coleta_id'), func.count(Regiao.id).label('regioes'),
               func.count(vigentes.c.regiao_id).label('anotadas'), _em_duvida().label('duvidas'),
               func.max(Anotacao.criada_em).label('ultima'))
        .select_from(Regiao).join(Regiao.imagem)
        .outerjoin(vigentes, vigentes.c.regiao_id == Regiao.id)
        .outerjoin(Anotacao, Anotacao.id == vigentes.c.anotacao_id)
        .group_by(Imagem.coleta_id).subquery())
    na_fila = Imagem.status.in_([StatusImagem.AGUARDANDO, StatusImagem.SEGMENTANDO])
    fotos = (
        select(Imagem.coleta_id.label('coleta_id'), func.count(Imagem.id).label('fotos'),
               func.sum(case((na_fila, 1), else_=0)).label('na_fila'),
               func.sum(case((Imagem.status == StatusImagem.ERRO, 1), else_=0)).label('com_erro'))
        .group_by(Imagem.coleta_id).subquery())
    consulta = (
        select(Coleta, fotos.c.fotos, fotos.c.na_fila, fotos.c.com_erro, regioes.c.regioes,
               regioes.c.anotadas, regioes.c.duvidas, regioes.c.ultima)
        .outerjoin(fotos, fotos.c.coleta_id == Coleta.id)
        .outerjoin(regioes, regioes.c.coleta_id == Coleta.id)
        .order_by(Coleta.criada_em.desc()))
    if tipo_id is not None:
        consulta = consulta.where(Coleta.tipo_amostra_id == tipo_id)
    return [ColetaResumida(coleta, n_fotos or 0, na_fila or 0, com_erro or 0, n_regioes or 0,
                           anotadas or 0, duvidas or 0, ultima)
            for coleta, n_fotos, na_fila, com_erro, n_regioes, anotadas, duvidas, ultima
            in db.session.execute(consulta)]


# ------------------------------------------------------------------ atividade

@dataclass(frozen=True)
class Dia:
    data: date
    anotacoes: int


def _desde(dia: date) -> datetime:
    """Um limite seguro para a consulta: o banco guarda em UTC e o dia é o local, então
    começa um dia antes; a contagem por dia local acerta o resto."""
    return datetime.combine(dia - timedelta(days=1), time())


def _dia_local(hora_utc: str) -> date:
    """'2026-09-25 02' (hora em UTC) -> dia no fuso deste computador (ex.: 24/09 no Brasil)."""
    return datetime.strptime(hora_utc, '%Y-%m-%d %H').replace(tzinfo=timezone.utc).astimezone().date()


def atividade_por_dia(dias: int = DIAS_DE_ATIVIDADE, *, tipo_id: int | None = None,
                      pessoa_id: int | None = None, hoje: date | None = None) -> list[Dia]:
    """Anotações feitas em cada um dos últimos `dias` (no fuso deste computador, como na
    tela), do mais antigo para hoje. Conta trabalho feito: mudar a classe conta de novo."""
    hoje = hoje or date.today()  # no fuso deste computador
    primeiro = hoje - timedelta(days=dias - 1)
    # O banco agrupa por hora em UTC (poucas linhas, sem converter fuso linha a linha, que
    # é lento no SQLite); cada hora vira o dia local aqui. Fusos com meia hora (raros)
    # poderiam trocar de dia até 30 minutos de anotações; o Brasil não tem nenhum.
    hora_utc = func.strftime('%Y-%m-%d %H', Anotacao.criada_em)
    consulta = (select(hora_utc, func.count(Anotacao.id))
                .where(Anotacao.criada_em >= _desde(primeiro)).group_by(hora_utc))
    if tipo_id is not None:
        consulta = consulta.join(Anotacao.classe).where(Classe.tipo_amostra_id == tipo_id)
    if pessoa_id is not None:
        consulta = consulta.where(Anotacao.pessoa_id == pessoa_id)
    contagem = Counter()
    for hora, quantidade in db.session.execute(consulta):
        contagem[_dia_local(hora)] += quantidade
    return [Dia(primeiro + timedelta(days=i), contagem.get(primeiro + timedelta(days=i), 0)) for i in range(dias)]


def anotacoes_por_pessoa(dias: int = DIAS_POR_PESSOA, *, tipo_id: int | None = None) -> list[tuple[str, int]]:
    """(nome, anotações) nos últimos `dias`, de quem mais anotou para quem menos."""
    total = func.count(Anotacao.id)
    consulta = (select(Pessoa.nome, total).join(Anotacao.pessoa)
                .where(Anotacao.criada_em >= _desde(date.today() - timedelta(days=dias - 1)))
                .group_by(Pessoa.id).order_by(total.desc(), Pessoa.nome))
    if tipo_id is not None:
        consulta = consulta.join(Anotacao.classe).where(Classe.tipo_amostra_id == tipo_id)
    return [(nome, quantidade) for nome, quantidade in db.session.execute(consulta)]


# --------------------------------------------------------------------- painel

@dataclass
class ResumoDoTipo:
    tipo: TipoAmostra
    numeros: Numeros
    fatias: list[FatiaDeClasse]


@dataclass
class Painel:
    """Tudo o que a página inicial mostra, para `tipo` (ou para todos, se None)."""
    tipo: TipoAmostra | None
    numeros: Numeros
    por_tipo: list[ResumoDoTipo]
    fatias: list[FatiaDeClasse]                 # classes do tipo escolhido
    coletas_pendentes: int                      # quantas coletas têm regiões pendentes
    para_continuar: list[ColetaResumida]
    com_erro: list[ColetaResumida]
    com_duvidas: list[ColetaResumida]
    sem_fotos: list[ColetaResumida]
    atividade: list[Dia]
    minhas_hoje: int
    minhas_na_semana: int
    por_pessoa: list[tuple[str, int]] | None = field(default=None)  # só para a administração

    @property
    def precisa_de_atencao(self) -> bool:
        return bool(self.com_erro or self.com_duvidas or self.sem_fotos or self.numeros.fotos_na_fila)


def montar_painel(tipos: list[TipoAmostra], tipo: TipoAmostra | None, pessoa: Pessoa,
                  *, com_equipe: bool = False) -> Painel:
    todas = resumo_das_coletas()
    numeros = numeros_por_tipo(todas)
    contagem = contagem_por_classe()
    por_tipo = [ResumoDoTipo(t, numeros.get(t.id, Numeros()), fatias_do_tipo(t, contagem)) for t in tipos]
    escolhidos = [r for r in por_tipo if tipo is None or r.tipo.id == tipo.id]

    coletas = [c for c in todas if tipo is None or c.coleta.tipo_amostra_id == tipo.id]
    pendentes = sorted((c for c in coletas if c.pendentes), key=lambda c: c.atividade_recente, reverse=True)
    minhas = atividade_por_dia(7, pessoa_id=pessoa.id)
    tipo_id = tipo.id if tipo else None
    return Painel(
        tipo=tipo,
        numeros=sum((r.numeros for r in escolhidos), Numeros()),
        por_tipo=por_tipo,
        fatias=escolhidos[0].fatias if tipo else [],
        coletas_pendentes=len(pendentes),
        para_continuar=pendentes[:MAXIMO_PARA_CONTINUAR],
        com_erro=[c for c in coletas if c.fotos_com_erro][:MAXIMO_POR_AVISO],
        com_duvidas=sorted((c for c in coletas if c.duvidas), key=lambda c: c.duvidas, reverse=True)[:MAXIMO_POR_AVISO],
        sem_fotos=[c for c in coletas if not c.fotos][:MAXIMO_POR_AVISO],
        atividade=atividade_por_dia(tipo_id=tipo_id),
        minhas_hoje=minhas[-1].anotacoes,
        minhas_na_semana=sum(dia.anotacoes for dia in minhas),
        por_pessoa=anotacoes_por_pessoa(tipo_id=tipo_id) if com_equipe else None,
    )
