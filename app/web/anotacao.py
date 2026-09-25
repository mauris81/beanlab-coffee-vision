"""Páginas de anotação (uma por vez e em lote) e as imagens que elas usam."""
from flask import abort, flash, redirect, render_template, request, send_file, session, url_for
from sqlalchemy import select

from app.dominio import Classe, Coleta, Imagem, Regiao
from app.extensions import db
from app.servicos.anotacoes import (
    anotar_em_lote, desfazer_anotacoes, progresso_da_coleta, situacao_das_regioes,
)
from app.servicos.recortes import media_da_imagem, recorte_da_regiao
from app.web import web_bp
from app.web.apresentacao import plural
from app.web.identidade import pessoa_atual

POR_PAGINA_LOTE = 120


def _coleta_ou_404(coleta_id: int) -> Coleta:
    return db.session.get(Coleta, coleta_id) or abort(404)


# ------------------------------------------------------------ uma por vez

@web_bp.get('/coletas/<int:coleta_id>/anotar')
def anotar(coleta_id):
    coleta = _coleta_ou_404(coleta_id)
    return render_template('anotar.html', coleta=coleta, classes=coleta.tipo_amostra.classes_ativas,
                           progresso=progresso_da_coleta(coleta.id),
                           regiao_inicial=request.args.get('regiao', type=int))


# ---------------------------------------------------------------- em lote

@web_bp.get('/coletas/<int:coleta_id>/lote')
def anotar_lote(coleta_id):
    coleta = _coleta_ou_404(coleta_id)
    mostrar = request.args.get('mostrar', 'pendentes')
    regioes = situacao_das_regioes(coleta.id)
    if mostrar == 'pendentes':
        regioes = [r for r in regioes if r.classe is None]
    elif mostrar != 'todas':
        regioes = [r for r in regioes if r.classe == mostrar]
    pagina = max(1, request.args.get('pagina', 1, type=int))
    total_paginas = max(1, -(-len(regioes) // POR_PAGINA_LOTE))
    visiveis = regioes[(pagina - 1) * POR_PAGINA_LOTE: pagina * POR_PAGINA_LOTE]

    ultimo_lote = session.pop('ultimo_lote', None)
    if ultimo_lote and ultimo_lote.get('coleta') != coleta.id:
        ultimo_lote = None
    return render_template(
        'lote.html', coleta=coleta, classes=coleta.tipo_amostra.classes_ativas,
        regioes=visiveis, quantidade=len(regioes), mostrar=mostrar, pagina=pagina,
        total_paginas=total_paginas, por_pagina=POR_PAGINA_LOTE, progresso=progresso_da_coleta(coleta.id),
        nomes_classes={c.codigo: c for c in coleta.tipo_amostra.classes},
        ultimo_lote=ultimo_lote,
    )


@web_bp.post('/coletas/<int:coleta_id>/lote')
def aplicar_lote(coleta_id):
    coleta = _coleta_ou_404(coleta_id)
    voltar = url_for('web.anotar_lote', coleta_id=coleta.id,
                     mostrar=request.form.get('mostrar', 'pendentes'), pagina=request.form.get('pagina', 1))
    ids = [int(i) for i in request.form.getlist('regioes') if i.isdigit()]
    classe = db.session.scalar(select(Classe).filter_by(
        tipo_amostra_id=coleta.tipo_amostra_id, codigo=request.form.get('classe'), ativa=True))
    if not ids:
        flash('Marque pelo menos uma região antes de escolher a classe.', 'aviso')
        return redirect(voltar)
    if classe is None:
        abort(400, 'Classe inválida para este tipo de amostra.')
    regioes = db.session.scalars(
        select(Regiao).join(Regiao.imagem).where(Regiao.id.in_(ids), Imagem.coleta_id == coleta.id)).all()
    anotacoes = anotar_em_lote(regioes, classe, pessoa=pessoa_atual())
    db.session.commit()
    session['ultimo_lote'] = {'coleta': coleta.id, 'ids': [a.id for a in anotacoes],
                              'texto': f'{plural(len(anotacoes), "região anotada", "regiões anotadas")} '
                                       f'como {classe.nome}.'}
    return redirect(voltar)


@web_bp.post('/coletas/<int:coleta_id>/lote/desfazer')
def desfazer_lote(coleta_id):
    coleta = _coleta_ou_404(coleta_id)
    ids = [int(i) for i in request.form.getlist('anotacoes') if i.isdigit()]
    desfeitas = desfazer_anotacoes(ids, pessoa_atual())
    db.session.commit()
    flash(f'Desfeito: {plural(desfeitas, "região voltou", "regiões voltaram")} a ficar pendente.'
          if desfeitas else 'Nada para desfazer (as anotações já tinham sido alteradas).', 'info')
    return redirect(url_for('web.anotar_lote', coleta_id=coleta.id,
                            mostrar=request.form.get('mostrar', 'pendentes')))


# ------------------------------------------------------------- imagens

@web_bp.get('/regioes/<int:regiao_id>/recorte.jpg', endpoint='recorte_da_regiao')
def servir_recorte(regiao_id):
    regiao = db.session.get(Regiao, regiao_id) or abort(404)
    # O endereço leva a geometria (?v=x_y_l_a): mudou o contorno, muda o endereço.
    return send_file(recorte_da_regiao(regiao), mimetype='image/jpeg', max_age=31536000)


@web_bp.get('/imagens/<int:imagem_id>/media.jpg')
def media_da_foto(imagem_id):
    imagem = db.session.get(Imagem, imagem_id) or abort(404)
    return send_file(media_da_imagem(imagem), mimetype='image/jpeg', max_age=31536000)
