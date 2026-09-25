"""Testes que abrem as páginas num navegador de verdade (Chrome ou Edge instalado).

São mais lentos e precisam do Playwright (requirements-dev.txt), então só rodam
quando pedidos:
    .\\.venv\\Scripts\\python.exe -m pytest -m navegador

Sobem um servidor próprio, numa porta livre, com banco numa pasta temporária.
Nada toca em C:\\CafeData nem no servidor que estiver aberto.
"""
import threading

import pytest
from werkzeug.serving import make_server

from app import create_app
from app.config import ConfigTeste
from app.extensions import db
from app.servicos.banco import preparar_banco

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # só quem roda estes testes precisa do Playwright
    sync_playwright = None


@pytest.fixture(scope='session')
def endereco(tmp_path_factory):
    """URL de um servidor da plataforma rodando só para os testes."""
    aplicacao = create_app(ConfigTeste(pasta_dados=tmp_path_factory.mktemp('dados')))
    with aplicacao.app_context():
        preparar_banco()
    servidor = make_server('127.0.0.1', 0, aplicacao, threaded=True)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{servidor.server_port}'
    servidor.shutdown()
    with aplicacao.app_context():
        db.engine.dispose()


@pytest.fixture(scope='session')
def navegador():
    if sync_playwright is None:
        pytest.skip('Playwright não instalado: pip install -r requirements-dev.txt')
    with sync_playwright() as p:
        for canal in ('chrome', 'msedge'):
            try:
                instancia = p.chromium.launch(channel=canal)
                break
            except Exception:  # canal não instalado neste computador
                continue
        else:
            pytest.skip('Nem Chrome nem Edge encontrados')
        yield instancia
        instancia.close()


TELAS = {'celular': {'width': 390, 'height': 844}, 'computador': {'width': 1366, 'height': 900}}


@pytest.fixture
def abrir(navegador, endereco):
    """abrir('/guia-visual', tela='celular', tema='dark') -> página já carregada."""
    contextos = []

    def _abrir(caminho='/', tela='computador', tema='light'):
        contexto = navegador.new_context(viewport=TELAS[tela], color_scheme=tema,
                                         has_touch=tela == 'celular', is_mobile=tela == 'celular')
        contextos.append(contexto)
        pagina = contexto.new_page()
        pagina.erros_js = []
        pagina.on('pageerror', lambda erro: pagina.erros_js.append(str(erro)))
        pagina.goto(endereco + caminho, wait_until='networkidle')
        return pagina

    yield _abrir
    for contexto in contextos:
        contexto.close()
