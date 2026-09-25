"""API da tela de anotação: regiões da coleta, anotar e desfazer.

Todas exigem saber quem é a pessoa (401 se não) e, nas que mudam dados, o código
CSRF no cabeçalho X-CSRF (conferido em app/web/identidade.py).
"""
from dataclasses import asdict

from flask import abort, request, url_for
from sqlalchemy import select

from app.api import api_bp
from app.dominio import Anotacao, Classe, Coleta, Regiao
from app.extensions import db
from app.servicos.anotacoes import (
    CONFIANCA_DUVIDA, AnotacaoInvalida, anotar_regiao, desfazer_anotacoes, progresso_da_coleta,
    situacao_das_regioes,
)
from app.web.identidade import pessoa_atual


def _pessoa_ou_401():
    pessoa = pessoa_atual()
    if pessoa is None:
        abort(401)
    return pessoa


@api_bp.errorhandler(401)
def _nao_identificado(_erro):
    return {'erro': 'Sua sessão terminou. Entre de novo (recarregue a página).'}, 401


@api_bp.errorhandler(404)
def _nao_encontrado(_erro):
    return {'erro': 'Não encontrado. Talvez tenha sido excluído; recarregue a página.'}, 404


def _progresso(coleta_id: int) -> dict:
    p = progresso_da_coleta(coleta_id)
    return {'total': p.total, 'anotadas': p.anotadas, 'pendentes': p.pendentes, 'percentual': p.percentual}


def _url_recorte(regiao_id: int, bbox: list[int]) -> str:
    # A geometria vai no endereço: se o contorno mudar, o navegador busca o recorte novo.
    return url_for('web.recorte_da_regiao', regiao_id=regiao_id, v='_'.join(map(str, bbox)))


@api_bp.get('/coletas/<int:coleta_id>/regioes')
def regioes_da_coleta(coleta_id):
    _pessoa_ou_401()
    coleta = db.session.get(Coleta, coleta_id) or abort(404)
    return {
        'coleta': {'id': coleta.id, 'nome': coleta.nome},
        'classes': [{'codigo': c.codigo, 'nome': c.nome, 'cor': c.cor, 'tecla': c.tecla_atalho}
                    for c in coleta.tipo_amostra.classes_ativas],
        'imagens': {i.id: {'nome': i.nome_original, 'largura': i.largura, 'altura': i.altura,
                           'media': url_for('web.media_da_foto', imagem_id=i.id)}
                    for i in coleta.imagens},
        'regioes': [{**asdict(s), 'recorte': _url_recorte(s.id, s.bbox)}
                    for s in situacao_das_regioes(coleta.id)],
        'progresso': _progresso(coleta.id),
    }


@api_bp.post('/regioes/<int:regiao_id>/anotar')
def anotar(regiao_id):
    pessoa = _pessoa_ou_401()
    regiao = db.session.get(Regiao, regiao_id) or abort(404)
    dados = request.get_json(silent=True) or {}
    tipo = regiao.imagem.coleta.tipo_amostra
    classe = db.session.scalar(select(Classe).filter_by(tipo_amostra_id=tipo.id, codigo=dados.get('classe')))
    if classe is None:
        return {'erro': f'Classe "{dados.get("classe")}" não existe para {tipo.nome}.'}, 422
    try:
        anotacao = anotar_regiao(
            regiao, classe, pessoa=pessoa,
            confianca=CONFIANCA_DUVIDA if dados.get('duvida') else None,
            observacao=str(dados.get('observacao') or '')[:2000],
        )
    except AnotacaoInvalida as erro:
        return {'erro': str(erro)}, 422
    db.session.commit()
    return {'anotacao_id': anotacao.id, 'classe': classe.codigo,
            'duvida': bool(dados.get('duvida')), 'progresso': _progresso(regiao.imagem.coleta_id)}


@api_bp.post('/anotacoes/desfazer')
def desfazer():
    """Corpo: {"ids": [..]}. Devolve o novo estado das regiões afetadas."""
    pessoa = _pessoa_ou_401()
    ids = [int(i) for i in (request.get_json(silent=True) or {}).get('ids', []) if str(i).isdigit()]
    regioes = {a.regiao_id for a in db.session.scalars(select(Anotacao).where(Anotacao.id.in_(ids)))}
    desfeitas = desfazer_anotacoes(ids, pessoa)
    db.session.commit()
    if not regioes:
        return {'desfeitas': 0, 'regioes': [], 'progresso': None}
    coleta_id = db.session.get(Regiao, next(iter(regioes))).imagem.coleta_id
    estado = [asdict(s) for s in situacao_das_regioes(coleta_id) if s.id in regioes]
    return {'desfeitas': desfeitas, 'regioes': estado, 'progresso': _progresso(coleta_id)}
