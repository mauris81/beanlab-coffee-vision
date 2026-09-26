"""Exportar os dados anotados (só a administração): planilha, COCO, YOLO e recortes.

O .zip é montado num arquivo temporário (em <pasta de dados>/exportacoes), enviado e
apagado assim que o download termina. Regras e formatos: app/servicos/exportacao.py.
"""
import os
import tempfile
import time
from pathlib import Path

from flask import Response, abort, current_app, flash, redirect, render_template, request, url_for

from app.servicos.exportacao import (
    FORMATOS, PedidoDeExportacao, exportar, montar_conteudo, nome_do_arquivo, tamanho_estimado,
)
from app.servicos.painel import resumo_das_coletas
from app.web import web_bp
from app.web.identidade import exige_administrador, pessoa_atual
from app.web.paginas import tipos_de_amostra


class ArquivoQueSeApaga:
    """Envia um arquivo em pedaços e o apaga quando o envio termina (ou é interrompido).

    O servidor chama close() no fim de toda resposta. (O send_file do Flask não serve
    aqui: com ele, a limpeza registrada em call_on_close nunca roda, e o .zip ficaria no
    disco. Um teste confere.)
    """

    def __init__(self, caminho: Path):
        self.caminho = caminho
        self.arquivo = open(caminho, 'rb')

    def __iter__(self):
        return iter(lambda: self.arquivo.read(1 << 20), b'')

    def close(self):
        self.arquivo.close()
        self.caminho.unlink(missing_ok=True)


def _pasta_temporaria() -> Path:
    pasta = Path(current_app.config['PASTA_DADOS']) / 'exportacoes'
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in pasta.glob('*.zip'):  # sobras de downloads interrompidos (mais de 1 dia)
        if time.time() - antigo.stat().st_mtime > 86400:
            antigo.unlink(missing_ok=True)
    return pasta


@web_bp.get('/exportar')
@exige_administrador
def exportar_dados():
    tipos = tipos_de_amostra()
    tipo = next((t for t in tipos if t.codigo == request.args.get('tipo')), tipos[0] if tipos else None)
    if tipo is None:
        abort(404)
    padrao = PedidoDeExportacao(tipo=tipo, formatos=frozenset(FORMATOS))
    conteudo = montar_conteudo(padrao)
    return render_template('exportar.html', tipos=tipos, tipo=tipo, formatos=FORMATOS,
                           coletas=resumo_das_coletas(tipo.id), conteudo=conteudo,
                           tamanho=tamanho_estimado(padrao, conteudo))


@web_bp.post('/exportar')
@exige_administrador
def baixar_exportacao():
    tipo = next((t for t in tipos_de_amostra() if t.codigo == request.form.get('tipo')), None) or abort(400)
    ids = tuple(int(i) for i in request.form.getlist('coletas') if i.isdigit())
    if not ids:
        flash('Escolha pelo menos uma coleta para exportar.', 'aviso')
        return redirect(url_for('web.exportar_dados', tipo=tipo.codigo))
    pedido = PedidoDeExportacao(
        tipo=tipo, coleta_ids=ids,
        formatos=frozenset(f for f in request.form.getlist('formatos') if f in FORMATOS),
        sem_duvidas=bool(request.form.get('sem_duvidas')),
        so_fotos_completas=bool(request.form.get('so_fotos_completas')))

    descritor, caminho = tempfile.mkstemp(dir=_pasta_temporaria(), suffix='.zip')
    os.close(descritor)
    caminho = Path(caminho)
    try:
        exportar(pedido, caminho, exportado_por=pessoa_atual())
    except BaseException:
        caminho.unlink(missing_ok=True)
        raise
    tamanho = caminho.stat().st_size
    resposta = Response(ArquivoQueSeApaga(caminho), mimetype='application/zip', direct_passthrough=True)
    resposta.headers['Content-Length'] = str(tamanho)
    resposta.headers['Content-Disposition'] = f'attachment; filename="{nome_do_arquivo(pedido)}.zip"'
    resposta.headers['Cache-Control'] = 'no-store'
    return resposta
