"""API da tela "Marcar na foto": tocar para criar regiões, excluir as erradas.

    GET  /api/imagens/<id>/marcacao   foto, classes e regiões desta foto
    POST /api/imagens/<id>/preparar   analisa a parte da foto em volta de {x, y} (antes do toque)
    POST /api/imagens/<id>/toque      contornos possíveis para o objeto em {x, y}
    POST /api/imagens/<id>/regioes    cria a região {poligono} e, se vier {classe}, já anota
    POST /api/regioes/<id>/excluir    exclui a região (e as anotações dela)
"""
from dataclasses import asdict

from flask import abort, request, url_for
from sqlalchemy import select

from app.api import api_bp
from app.api.anotacao import _pessoa_ou_401, _progresso, _url_recorte
from app.dominio import Classe, Imagem, Regiao
from app.extensions import db
from app.segmentacao.ia import MotorIndisponivel
from app.servicos.anotacoes import CONFIANCA_DUVIDA, AnotacaoInvalida, anotar_regiao, situacao_das_regioes
from app.servicos.marcacao import (
    MarcacaoInvalida, candidatos_do_toque, criar_regiao, excluir_regiao, marcador, preparar_toque,
)

SEM_IA = ('Marcar com um toque precisa da segmentação com IA instalada neste computador '
          '("Instalar IA.bat"). Dá para selecionar, reclassificar e excluir regiões.')


def _imagem_ou_404(imagem_id: int) -> Imagem:
    return db.session.get(Imagem, imagem_id) or abort(404)


def _situacao(imagem: Imagem, ids: set[int] | None = None) -> list[dict]:
    return [{**asdict(s), 'recorte': _url_recorte(s.id, s.bbox)}
            for s in situacao_das_regioes(imagem.coleta_id)
            if s.imagem_id == imagem.id and (ids is None or s.id in ids)]


def _ponto():
    dados = request.get_json(silent=True) or {}
    try:
        return float(dados['x']), float(dados['y'])
    except (KeyError, TypeError, ValueError):
        abort(400)


@api_bp.get('/imagens/<int:imagem_id>/marcacao')
def dados_da_marcacao(imagem_id):
    _pessoa_ou_401()
    imagem = _imagem_ou_404(imagem_id)
    fotos = [i.id for i in imagem.coleta.imagens]
    posicao = fotos.index(imagem.id)
    return {
        'tipo_amostra': imagem.coleta.tipo_amostra.codigo,
        'imagem': {'id': imagem.id, 'nome': imagem.nome_original, 'largura': imagem.largura,
                   'altura': imagem.altura, 'media': url_for('web.media_da_foto', imagem_id=imagem.id),
                   'original': url_for('web.arquivo_da_foto', imagem_id=imagem.id)},
        'classes': [{'codigo': c.codigo, 'nome': c.nome, 'cor': c.cor, 'tecla': c.tecla_atalho}
                    for c in imagem.coleta.tipo_amostra.classes_ativas],
        'regioes': _situacao(imagem),
        'toque_disponivel': marcador().disponivel(),
        'aviso_sem_ia': SEM_IA,
        'fotos': {'posicao': posicao + 1, 'total': len(fotos),
                  'anterior': fotos[posicao - 1] if posicao > 0 else None,
                  'proxima': fotos[posicao + 1] if posicao + 1 < len(fotos) else None},
    }


@api_bp.post('/imagens/<int:imagem_id>/preparar')
def preparar(imagem_id):
    _pessoa_ou_401()
    imagem = _imagem_ou_404(imagem_id)
    x, y = _ponto()
    if not marcador().disponivel():
        return {'erro': SEM_IA}, 409
    try:
        preparar_toque(imagem, x, y)
    except MarcacaoInvalida as erro:
        return {'erro': str(erro)}, 422
    return {'pronto': True}


@api_bp.post('/imagens/<int:imagem_id>/toque')
def toque(imagem_id):
    _pessoa_ou_401()
    imagem = _imagem_ou_404(imagem_id)
    x, y = _ponto()
    if not marcador().disponivel():
        return {'erro': SEM_IA}, 409
    try:
        candidatos, melhor = candidatos_do_toque(imagem, x, y)
    except (MarcacaoInvalida, MotorIndisponivel) as erro:
        return {'erro': str(erro)}, 422
    return {'candidatos': [asdict(c) for c in candidatos], 'sugerido': melhor}


@api_bp.post('/imagens/<int:imagem_id>/regioes')
def criar(imagem_id):
    pessoa = _pessoa_ou_401()
    imagem = _imagem_ou_404(imagem_id)
    dados = request.get_json(silent=True) or {}
    classe = None
    if dados.get('classe'):
        classe = db.session.scalar(select(Classe).filter_by(
            tipo_amostra_id=imagem.coleta.tipo_amostra_id, codigo=dados['classe']))
        if classe is None:
            return {'erro': f'Classe "{dados["classe"]}" não existe para este tipo de amostra.'}, 422
    try:
        regiao = criar_regiao(imagem, dados.get('poligono') or [], veio_do_toque=dados.get('origem') != 'desenho')
        if classe:
            anotar_regiao(regiao, classe, pessoa=pessoa,
                          confianca=CONFIANCA_DUVIDA if dados.get('duvida') else None,
                          observacao=str(dados.get('observacao') or '')[:2000])
    except (MarcacaoInvalida, AnotacaoInvalida) as erro:
        db.session.rollback()
        return {'erro': str(erro)}, 422
    db.session.commit()
    return {'regiao': _situacao(imagem, {regiao.id})[0], 'progresso': _progresso(imagem.coleta_id)}, 201


@api_bp.post('/regioes/<int:regiao_id>/excluir')
def excluir(regiao_id):
    pessoa = _pessoa_ou_401()
    regiao = db.session.get(Regiao, regiao_id) or abort(404)
    coleta_id = regiao.imagem.coleta_id
    try:
        excluir_regiao(regiao, pessoa)
    except MarcacaoInvalida as erro:
        return {'erro': str(erro)}, 403
    db.session.commit()
    return {'excluida': regiao_id, 'progresso': _progresso(coleta_id)}
