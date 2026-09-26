"""Marcar na foto: criar regiões com um toque (ou um contorno enviado) e excluir as erradas.

Regiões criadas assim são MANUAIS (uma pessoa decidiu que ali há um objeto), com
motor "toque" quando o contorno veio do SAM. "Segmentar de novo" nunca mexe nelas.
"""
from flask import current_app
from sqlalchemy import func, select

from app.armazenamento import armazenamento_de_imagens
from app.dominio import Anotacao, Imagem, OrigemRegiao, Pessoa, Regiao
from app.dominio.geometria import PoligonoInvalido
from app.extensions import db
from app.segmentacao.toque import Candidato, MarcadorPorToque
from app.servicos.imagens import matriz_rgb

MOTOR_TOQUE, VERSAO_TOQUE = 'toque', 'sam2.1-tiny'


class MarcacaoInvalida(ValueError):
    """A região pedida não pode ser criada ou excluída. A mensagem explica."""


def marcador() -> MarcadorPorToque:
    return current_app.extensions['marcador']


def _dentro(imagem: Imagem, x: float, y: float) -> None:
    if not (0 <= x < imagem.largura and 0 <= y < imagem.altura):
        raise MarcacaoInvalida('O toque ficou fora da foto.')


def _ler_foto(imagem: Imagem):
    caminho = armazenamento_de_imagens().caminho(imagem.hash_sha256, imagem.extensao)
    return lambda: matriz_rgb(caminho)


def preparar_toque(imagem: Imagem, x: float, y: float) -> None:
    _dentro(imagem, x, y)
    marcador().preparar(imagem.hash_sha256, _ler_foto(imagem), (imagem.altura, imagem.largura), x, y)


def candidatos_do_toque(imagem: Imagem, x: float, y: float) -> tuple[list[Candidato], int]:
    _dentro(imagem, x, y)
    return marcador().candidatos(imagem.hash_sha256, _ler_foto(imagem), (imagem.altura, imagem.largura), x, y)


def criar_regiao(imagem: Imagem, poligono, *, veio_do_toque: bool = True) -> Regiao:
    """Cria a região com o contorno dado (em pixels da foto). Não confirma (commit)."""
    try:
        pontos = [[int(round(float(x))), int(round(float(y)))] for x, y in poligono]
    except (TypeError, ValueError):
        raise MarcacaoInvalida('Contorno em formato inválido.') from None
    if any(not (0 <= x <= imagem.largura and 0 <= y <= imagem.altura) for x, y in pontos):
        raise MarcacaoInvalida('O contorno passa da borda da foto.')
    try:
        regiao = Regiao.do_poligono(pontos, origem=OrigemRegiao.MANUAL,
                                    motor=MOTOR_TOQUE if veio_do_toque else None,
                                    versao_motor=VERSAO_TOQUE if veio_do_toque else None)
    except PoligonoInvalido as erro:
        raise MarcacaoInvalida(f'Contorno inválido: {erro}') from None
    imagem.regioes.append(regiao)
    db.session.flush()
    return regiao


def motivo_para_nao_excluir(regiao: Regiao, pessoa: Pessoa) -> str | None:
    """Excluir uma região apaga as anotações dela. A administração pode sempre; as outras
    pessoas, só se ninguém além delas mesmas anotou a região."""
    if pessoa.eh_administrador:
        return None
    de_outras = db.session.scalar(select(func.count(Anotacao.id)).where(
        Anotacao.regiao_id == regiao.id, (Anotacao.pessoa_id != pessoa.id) | Anotacao.pessoa_id.is_(None)))
    if de_outras:
        return 'Outra pessoa já anotou esta região. Só a administração pode excluí-la.'
    return None


def excluir_regiao(regiao: Regiao, pessoa: Pessoa) -> None:
    """Tira a região (e as anotações dela). Não confirma (commit)."""
    if motivo := motivo_para_nao_excluir(regiao, pessoa):
        raise MarcacaoInvalida(motivo)
    db.session.delete(regiao)
    db.session.flush()
