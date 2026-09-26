"""Coletas: listar, criar, ver, enviar fotos; servir fotos e miniaturas."""
from datetime import date

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from sqlalchemy import func, select

from app.armazenamento import armazenamento_de_imagens
from app.dominio import Coleta, Imagem, JobSegmentacao, Regiao, StatusImagem, TipoAmostra
from app.extensions import db
from app.fila import fila
from app.servicos.anotacoes import progresso_da_coleta
from app.servicos.coletas import (
    ExclusaoRecusada, conteudo_da_coleta, excluir_coleta, motivo_para_nao_excluir,
)
from app.servicos.ingestao import (
    ImportacaoInvalida, excluir_imagem, importar_coco, receber_foto, receber_recorte,
)
from app.servicos.segmentacao import agendar_segmentacao, ultimo_erro
from app.web import web_bp
from app.web.apresentacao import plural
from app.web.identidade import pessoa_atual
from app.web.paginas import tipos_de_amostra

MODOS_DE_ENVIO = ('fotos', 'recortes', 'coco')
# Pela fila do celular (fotos guardadas sem sinal) cada arquivo vai sozinho; COCO precisa
# das fotos junto com o .json, então não entra na fila.
MODOS_DA_FILA = ('fotos', 'recortes')


def _coleta_ou_404(coleta_id: int) -> Coleta:
    return db.session.get(Coleta, coleta_id) or abort(404)


def _voltar_para(url: str):
    """Redireciona; se o envio veio do JavaScript (barra de progresso), responde o destino
    em JSON, para o navegador carregar a página de verdade e mostrar as mensagens."""
    if request.headers.get('X-Envio-Via') == 'js':
        return {'destino': url}
    return redirect(url)


def _via_fila() -> bool:
    """Envio feito pela fila de fotos guardadas no celular (static/js/fila-fotos.js).
    A fila mostra o resultado ela mesma: resposta em JSON, sem mensagens na sessão."""
    return request.headers.get('X-Envio-Via') == 'fila'


# --------------------------------------------------------------------- listar

@web_bp.get('/coletas')
def coletas():
    filtro = request.args.get('tipo')
    consulta = select(Coleta).order_by(Coleta.criada_em.desc())
    if filtro:
        consulta = consulta.join(Coleta.tipo_amostra).where(TipoAmostra.codigo == filtro)
    lista = db.session.scalars(consulta).all()
    fotos = dict(db.session.execute(
        select(Imagem.coleta_id, func.count(Imagem.id)).group_by(Imagem.coleta_id)).all())
    return render_template('coletas.html', coletas=lista, filtro=filtro, tipos=tipos_de_amostra(),
                           fotos=fotos, progresso={c.id: progresso_da_coleta(c.id) for c in lista})


# ---------------------------------------------------------------------- criar

@web_bp.route('/coletas/nova', methods=['GET', 'POST'])
def nova_coleta():
    tipos = tipos_de_amostra()
    dados = request.form if request.method == 'POST' else {
        'tipo': request.args.get('tipo', ''), 'data_coleta': date.today().isoformat()}
    erros = {}
    if request.method == 'POST':
        tipo = next((t for t in tipos if t.codigo == dados.get('tipo')), None)
        nome = ' '.join(dados.get('nome', '').split())
        if tipo is None:
            erros['tipo'] = 'Escolha o que foi fotografado.'
        if not nome:
            erros['nome'] = 'Dê um nome à coleta. Ex.: "Talhão 3, março".'
        data_coleta = None
        if dados.get('data_coleta'):
            try:
                data_coleta = date.fromisoformat(dados['data_coleta'])
            except ValueError:
                erros['data_coleta'] = 'Data inválida.'
        if not erros:
            opcional = lambda campo: ' '.join(dados.get(campo, '').split()) or None  # noqa: E731
            coleta = Coleta(
                tipo_amostra=tipo, nome=nome[:200], data_coleta=data_coleta,
                fazenda=opcional('fazenda'), talhao=opcional('talhao'),
                variedade=opcional('variedade'), descricao=opcional('descricao'),
                coletor=pessoa_atual(),
            )
            db.session.add(coleta)
            db.session.commit()
            flash('Coleta criada. Agora envie as fotos.', 'sucesso')
            return redirect(url_for('web.coleta', coleta_id=coleta.id) + '#enviar')
    return render_template('coleta_nova.html', tipos=tipos, dados=dados, erros=erros)


# ------------------------------------------------------------------------ ver

@web_bp.get('/coletas/<int:coleta_id>')
def coleta(coleta_id):
    coleta = _coleta_ou_404(coleta_id)
    regioes_por_imagem = dict(db.session.execute(
        select(Regiao.imagem_id, func.count(Regiao.id))
        .join(Regiao.imagem).where(Imagem.coleta_id == coleta.id)
        .group_by(Regiao.imagem_id)).all())
    conteudo = conteudo_da_coleta(coleta)
    return render_template(
        'coleta.html', coleta=coleta, progresso=progresso_da_coleta(coleta.id),
        regioes_por_imagem=regioes_por_imagem, conteudo=conteudo,
        motivo_para_nao_excluir=motivo_para_nao_excluir(coleta, pessoa_atual(), conteudo),
        erros={i.id: ultimo_erro(i) for i in coleta.imagens if i.status == StatusImagem.ERRO},
    )


# --------------------------------------------------------------------- enviar

@web_bp.post('/coletas/<int:coleta_id>/enviar')
def enviar_fotos(coleta_id):
    coleta = _coleta_ou_404(coleta_id)
    modo = request.form.get('modo', 'fotos')
    arquivos = [a for a in request.files.getlist('arquivos') if a and a.filename]
    if _via_fila():
        if modo not in MODOS_DA_FILA or not arquivos:
            return {'erro': 'Envio incompleto: guarde a foto de novo.'}, 400
    elif modo not in MODOS_DE_ENVIO:
        abort(400)
    if not arquivos:
        flash('Nenhum arquivo foi escolhido.', 'aviso')
        return _voltar_para(url_for('web.coleta', coleta_id=coleta.id) + '#enviar')

    pessoa = pessoa_atual()
    if modo == 'coco':
        jsons = [a for a in arquivos if a.filename.lower().endswith('.json')]
        if len(jsons) != 1:
            flash('No modo COCO, envie as fotos junto com UM arquivo .json de anotações.', 'aviso')
            return _voltar_para(url_for('web.coleta', coleta_id=coleta.id) + '#enviar')
        fotos = {a.filename: a.read() for a in arquivos if a is not jsons[0]}
        try:
            resumo = importar_coco(coleta, fotos, jsons[0].read(), pessoa=pessoa)
        except ImportacaoInvalida as erro:
            flash(str(erro), 'perigo')
            return _voltar_para(url_for('web.coleta', coleta_id=coleta.id) + '#enviar')
        resultados = resumo.resultados
        _avisar_importacao_coco(resumo)
    elif modo == 'recortes':
        resultados = [receber_recorte(coleta, a.read(), a.filename, pessoa=pessoa) for a in arquivos]
    else:
        resultados = [receber_foto(coleta, a.read(), a.filename, pessoa=pessoa) for a in arquivos]

    jobs = [agendar_segmentacao(r.imagem) for r in resultados if r.situacao == 'nova']
    db.session.commit()
    fila().enviar([j.id for j in jobs if j is not None])
    if _via_fila():
        return {'resultados': [{'nome': r.nome_arquivo, 'situacao': r.situacao, 'mensagem': r.mensagem}
                               for r in resultados]}
    _avisar_resultado(resultados, segmentando=any(jobs))
    return _voltar_para(url_for('web.coleta', coleta_id=coleta.id) + '#fotos')


def _lista_curta(nomes, limite=5):
    nomes = list(nomes)
    return ', '.join(nomes[:limite]) + (f' e mais {len(nomes) - limite}' if len(nomes) > limite else '')


def _avisar_resultado(resultados, segmentando: bool):
    novas = [r for r in resultados if r.situacao == 'nova']
    repetidas = [r for r in resultados if r.situacao == 'repetida']
    recusadas = [r for r in resultados if r.situacao == 'recusada']
    if novas:
        complemento = ' A segmentação começou; acompanhe abaixo.' if segmentando else ''
        flash(f'{plural(len(novas), "foto recebida", "fotos recebidas")}.{complemento}', 'sucesso')
    if repetidas:
        flash(f'{plural(len(repetidas), "foto já estava", "fotos já estavam")} nesta coleta e não '
              f'{"foi duplicada" if len(repetidas) == 1 else "foram duplicadas"}: '
              f'{_lista_curta(r.nome_arquivo for r in repetidas)}.', 'info')
    if recusadas:
        flash(f'{plural(len(recusadas), "arquivo não aceito", "arquivos não aceitos")}: '
              f'{_lista_curta(f"{r.nome_arquivo} ({r.mensagem})" for r in recusadas)}', 'perigo')


def _avisar_importacao_coco(resumo):
    partes = [plural(resumo.regioes, 'região importada', 'regiões importadas'),
              f'{resumo.anotacoes} já com classe']
    flash('COCO: ' + '; '.join(partes) + '.', 'sucesso' if resumo.regioes else 'aviso')
    if resumo.categorias_sem_classe:
        flash('Categorias sem classe correspondente (as regiões ficaram pendentes): '
              f'{_lista_curta(sorted(resumo.categorias_sem_classe))}.', 'aviso')
    if resumo.imagens_sem_arquivo:
        flash(f'O .json cita fotos que não foram enviadas: {_lista_curta(resumo.imagens_sem_arquivo)}.', 'aviso')
    if resumo.regioes_ignoradas:
        flash(f'{plural(resumo.regioes_ignoradas, "região ignorada", "regiões ignoradas")}: '
              'formato RLE ou contorno inválido.', 'aviso')


# ------------------------------------------------------------ excluir coleta

@web_bp.post('/coletas/<int:coleta_id>/excluir')
def excluir_a_coleta(coleta_id):
    coleta = _coleta_ou_404(coleta_id)
    nome, fotos = coleta.nome, len(coleta.imagens)
    try:
        apagar_arquivos = excluir_coleta(coleta, pessoa_atual(), request.form.get('confirmacao'))
    except ExclusaoRecusada as motivo:
        flash(str(motivo), 'perigo')
        return redirect(url_for('web.coleta', coleta_id=coleta.id) + '#excluir')
    db.session.commit()
    apagar_arquivos()
    flash(f'Coleta "{nome}" excluída, com {plural(fotos, "foto")}.', 'info')
    return redirect(url_for('web.coletas'))


# ------------------------------------------------------------- ações na foto

@web_bp.post('/imagens/<int:imagem_id>/excluir')
def excluir_foto(imagem_id):
    imagem = db.session.get(Imagem, imagem_id) or abort(404)
    coleta_id, nome = imagem.coleta_id, imagem.nome_original
    apagar_arquivo = excluir_imagem(imagem)
    db.session.commit()
    apagar_arquivo()
    flash(f'Foto "{nome}" excluída.', 'info')
    return redirect(url_for('web.coleta', coleta_id=coleta_id) + '#fotos')


@web_bp.post('/imagens/<int:imagem_id>/segmentar')
def segmentar_de_novo(imagem_id):
    imagem = db.session.get(Imagem, imagem_id) or abort(404)
    job = agendar_segmentacao(imagem)
    db.session.commit()
    if job:
        fila().enviar([job.id])
        flash(f'Segmentando "{imagem.nome_original}" de novo.', 'info')
    return redirect(url_for('web.coleta', coleta_id=imagem.coleta_id) + '#fotos')


# ------------------------------------------------------- arquivos das fotos

@web_bp.get('/imagens/<int:imagem_id>/arquivo')
def arquivo_da_foto(imagem_id):
    imagem = db.session.get(Imagem, imagem_id) or abort(404)
    caminho = armazenamento_de_imagens().caminho(imagem.hash_sha256, imagem.extensao)
    # O conteúdo de uma Imagem nunca muda (nome = hash): pode ficar no cache por 1 ano.
    return send_file(caminho, max_age=31536000, download_name=imagem.nome_original)


@web_bp.get('/imagens/<int:imagem_id>/miniatura')
def miniatura_da_foto(imagem_id):
    imagem = db.session.get(Imagem, imagem_id) or abort(404)
    caminho = armazenamento_de_imagens().caminho_miniatura(imagem.hash_sha256)
    if not caminho.is_file():
        abort(404)
    return send_file(caminho, mimetype='image/jpeg', max_age=31536000)


# ------------------------------------------------------ situação (para o JS)

@web_bp.get('/coletas/<int:coleta_id>/situacao.json')
def situacao_da_coleta(coleta_id):
    """Status de cada foto, para a página se atualizar sozinha durante a segmentação."""
    from app.web.apresentacao import apresentar_status
    coleta = _coleta_ou_404(coleta_id)
    regioes = dict(db.session.execute(
        select(Regiao.imagem_id, func.count(Regiao.id)).join(Regiao.imagem)
        .where(Imagem.coleta_id == coleta.id).group_by(Regiao.imagem_id)).all())
    imagens = []
    for imagem in coleta.imagens:
        a = apresentar_status(imagem.status)
        imagens.append({'id': imagem.id, 'status': imagem.status.value, 'regioes': regioes.get(imagem.id, 0),
                        'selo': {'texto': a.texto, 'variante': a.variante, 'icone': a.icone,
                                 'animado': a.animado}})
    pendentes = sum(i['status'] in ('aguardando', 'segmentando') for i in imagens)
    return {'imagens': imagens, 'pendentes': pendentes, 'regioes': sum(regioes.values()),
            'erros': sum(i['status'] == 'erro' for i in imagens)}
