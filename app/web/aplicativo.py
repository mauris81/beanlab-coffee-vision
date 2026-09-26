"""A plataforma como aplicativo no celular (PWA) e o uso sem sinal.

    /sw.js              "service worker": guarda no celular os arquivos da plataforma
                        e a página "Fotos no celular", e envia as fotos guardadas
                        quando a conexão volta. Gerado a partir de templates/sw.js.
    /fotos-no-celular   fotografar sem sinal e ver as fotos que esperam envio. Não tem
                        dado de ninguém (as fotos são lidas do próprio aparelho), por
                        isso pode ficar guardada no celular e abrir sem conexão.
    /ajuda              guia de uso. Com sinal, página normal (com menu); o celular guarda
                        a versão ?offline=1 (sem menu nem dados de ninguém) para o campo.

Como funciona, em palavras simples: docs/decisoes/0007-publicacao-e-aplicativo.md
"""
import hashlib
from pathlib import Path

from flask import current_app, make_response, render_template, request, url_for

from app.web import web_bp

# Arquivos da pasta static/ que o celular guarda (o resto, como licenças, fica de fora).
EXTENSOES_GUARDADAS = {'.css', '.js', '.woff2', '.svg', '.png', '.json'}


def arquivos_do_aplicativo() -> list[Path]:
    pasta = Path(current_app.static_folder)
    return sorted(p for p in pasta.rglob('*') if p.is_file() and p.suffix in EXTENSOES_GUARDADAS)


def _calcular_versao() -> str:
    """Resumo (hash) de todos os arquivos que vão para o celular e dos templates.
    Mudou qualquer um? A versão muda, e o celular baixa tudo de novo sozinho."""
    resumo = hashlib.sha256()
    templates = Path(current_app.root_path, current_app.template_folder)
    for arquivo in [*arquivos_do_aplicativo(), *sorted(templates.rglob('*.*'))]:
        resumo.update(arquivo.name.encode())
        resumo.update(arquivo.read_bytes())
    return resumo.hexdigest()[:12]


def versao_do_aplicativo() -> str:
    # No modo desenvolvimento os arquivos mudam o tempo todo: recalcula a cada pedido.
    if current_app.debug or 'versao_do_aplicativo' not in current_app.extensions:
        current_app.extensions['versao_do_aplicativo'] = _calcular_versao()
    return current_app.extensions['versao_do_aplicativo']


@web_bp.get('/sw.js')
def service_worker():
    static = Path(current_app.static_folder)
    arquivos = [url_for('static', filename=p.relative_to(static).as_posix()) for p in arquivos_do_aplicativo()]
    codigo = render_template(
        'sw.js', versao=versao_do_aplicativo(), arquivos=arquivos,
        pagina_sem_sinal=url_for('web.fotos_no_celular'),
        # Páginas que abrem sem sinal pelo próprio endereço (cópia guardada, genérica).
        paginas_guardadas={url_for('web.ajuda'): url_for('web.ajuda', offline=1)},
        fila=url_for('static', filename='js/fila-fotos.js'),
    )
    resposta = make_response(codigo)
    resposta.mimetype = 'text/javascript'
    # O navegador sempre confere se há versão nova (nunca usa uma cópia velha deste arquivo).
    resposta.headers['Cache-Control'] = 'no-cache'
    return resposta


@web_bp.get('/fotos-no-celular')
def fotos_no_celular():
    return render_template('fotos_no_celular.html')


@web_bp.get('/ajuda')
def ajuda():
    return render_template('ajuda.html', generica=request.args.get('offline') == '1')
