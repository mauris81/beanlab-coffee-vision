"""Regras para excluir uma coleta inteira (fotos, regiões e anotações).

Quem pode: a administração, sempre; quem criou a coleta, enquanto ninguém tiver
anotado nada nela (o caso comum: criou por engano ou com o tipo errado). Depois que
há anotações, apagar destrói trabalho da equipe, e isso fica com a administração.
"""
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import func, select

from app.armazenamento import armazenamento_de_imagens
from app.dominio import Anotacao, Coleta, Imagem, Pessoa, Regiao, StatusImagem
from app.extensions import db


class ExclusaoRecusada(ValueError):
    """A coleta não pode ser excluída agora. A mensagem explica por quê."""


@dataclass(frozen=True)
class ConteudoDaColeta:
    fotos: int
    regioes: int
    anotacoes: int


def conteudo_da_coleta(coleta: Coleta) -> ConteudoDaColeta:
    """O que se perde ao excluir (para mostrar antes de confirmar)."""
    da_coleta = Imagem.coleta_id == coleta.id
    return ConteudoDaColeta(
        fotos=db.session.scalar(select(func.count(Imagem.id)).where(da_coleta)),
        regioes=db.session.scalar(select(func.count(Regiao.id)).join(Regiao.imagem).where(da_coleta)),
        anotacoes=db.session.scalar(select(func.count(Anotacao.id)).join(Anotacao.regiao)
                                    .join(Regiao.imagem).where(da_coleta)),
    )


def motivo_para_nao_excluir(coleta: Coleta, pessoa: Pessoa,
                            conteudo: ConteudoDaColeta | None = None) -> str | None:
    """None se a pessoa pode excluir a coleta; senão, a explicação para mostrar."""
    if pessoa.eh_administrador:
        return None
    if coleta.coletor_id != pessoa.id:
        return 'Só quem criou esta coleta, ou a administração, pode excluí-la.'
    if (conteudo or conteudo_da_coleta(coleta)).anotacoes:
        return 'Esta coleta já tem anotações da equipe. Só a administração pode excluí-la.'
    return None


def nome_confere(digitado: str | None, coleta: Coleta) -> bool:
    """Confirmação digitada: o nome da coleta, sem ligar para maiúsculas e espaços."""
    normalizar = lambda texto: ' '.join((texto or '').split()).casefold()  # noqa: E731
    return normalizar(digitado) == normalizar(coleta.nome)


def excluir_coleta(coleta: Coleta, pessoa: Pessoa, confirmacao: str | None = None) -> Callable[[], None]:
    """Tira a coleta do banco com tudo o que há nela. Não confirma (commit).

    Devolve uma função que apaga os arquivos das fotos: chame-a só DEPOIS do commit
    (se o commit falhar, nada se perde). Um arquivo só é apagado se nenhuma outra
    coleta usar a mesma foto.

    Com anotações, exige `confirmacao` = nome da coleta (digitado pela pessoa).
    """
    conteudo = conteudo_da_coleta(coleta)
    if motivo := motivo_para_nao_excluir(coleta, pessoa, conteudo):
        raise ExclusaoRecusada(motivo)
    if any(imagem.status == StatusImagem.SEGMENTANDO for imagem in coleta.imagens):
        raise ExclusaoRecusada('Uma foto desta coleta está sendo segmentada agora. Espere terminar '
                               '(leva poucos segundos) e tente de novo.')
    if conteudo.anotacoes and not nome_confere(confirmacao, coleta):
        raise ExclusaoRecusada('Para confirmar, digite o nome da coleta exatamente como aparece.')

    arquivos = {(imagem.hash_sha256, imagem.extensao) for imagem in coleta.imagens}
    db.session.delete(coleta)  # fotos, regiões, anotações e segmentações vão junto (cascata)
    db.session.flush()

    def apagar_arquivos():
        armazenamento = armazenamento_de_imagens()
        for hash_sha256, extensao in arquivos:
            if not db.session.scalar(select(func.count(Imagem.id)).filter_by(hash_sha256=hash_sha256)):
                armazenamento.remover(hash_sha256, extensao)
    return apagar_arquivos
