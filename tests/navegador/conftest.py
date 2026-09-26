"""Testes que abrem as páginas num navegador de verdade (Chrome ou Edge instalado).

São mais lentos e precisam do Playwright (requirements-dev.txt), então só rodam
quando pedidos:
    .\\.venv\\Scripts\\python.exe -m pytest -m navegador

Sobem um servidor próprio, numa porta livre, com banco numa pasta temporária.
Nada toca em C:\\CafeData nem no servidor que estiver aberto.
"""
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from app import create_app
from app.config import ConfigTeste
from app.extensions import db
from app.dominio import Papel
from app.servicos.banco import preparar_banco
from app.servicos.contas import criar_conta

SENHA = 'senha-dos-testes-2026'
# (nome, usuário, perfil) das contas do servidor de teste
CONTAS = [('Maria Membro', 'membro', Papel.MEMBRO), ('Ana Admin', 'admin', Papel.ADMINISTRADOR)]

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # só quem roda estes testes precisa do Playwright
    sync_playwright = None


@pytest.fixture(scope='session')
def aplicacao(tmp_path_factory):
    """A aplicação por trás do servidor de teste (para preparar dados direto no banco)."""
    config = ConfigTeste(pasta_dados=tmp_path_factory.mktemp('dados'))
    config.SEGMENTACAO_SINCRONA = False  # fila em segundo plano, como no uso real
    app = create_app(config)
    with app.app_context():
        preparar_banco()
        for nome, usuario, papel in CONTAS:
            criar_conta(nome, usuario, papel, senha=SENHA)
        db.session.commit()
    yield app
    with app.app_context():
        db.engine.dispose()


@pytest.fixture(scope='session')
def endereco(aplicacao):
    """URL de um servidor da plataforma rodando só para os testes."""
    servidor = make_server('127.0.0.1', 0, aplicacao, threaded=True)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{servidor.server_port}'
    servidor.shutdown()


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


AXE = (Path(__file__).parent / 'axe.min.js').read_text(encoding='utf-8')
REGRAS_WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']


def violacoes_wcag(pagina) -> str:
    """Roda o axe-core na página aberta; devolve '' se não houver problemas."""
    # evaluate (e não uma tag <script>): a política de segurança da plataforma bloqueia,
    # com razão, qualquer script embutido na página, inclusive o de um teste.
    pagina.evaluate(AXE)
    resultado = pagina.evaluate(
        '(regras) => axe.run(document, {runOnly: {type: "tag", values: regras}})', REGRAS_WCAG)
    linhas = []
    for v in resultado['violations']:
        linhas.append(f"[{v['impact']}] {v['id']}: {v['help']} ({v['helpUrl']})")
        linhas += [f"    em {no['target']}" for no in v['nodes'][:5]]
    return '\n'.join(linhas)


TELAS = {'celular': {'width': 390, 'height': 844}, 'computador': {'width': 1366, 'height': 900}}


@pytest.fixture(scope='session')
def sessoes(navegador, endereco, tmp_path_factory):
    """Entra uma vez com cada conta e guarda os cookies, para os testes não repetirem o login."""
    pasta = tmp_path_factory.mktemp('sessoes')
    caminhos = {}
    for _, usuario, _ in CONTAS:
        contexto = navegador.new_context()
        pagina = contexto.new_page()
        pagina.goto(endereco + '/entrar')
        pagina.get_by_label('Usuário').fill(usuario)
        pagina.get_by_label('Senha', exact=True).fill(SENHA)
        pagina.get_by_role('button', name='Entrar').click()
        pagina.wait_for_url(lambda url: '/entrar' not in url)
        caminhos[usuario] = str(pasta / f'{usuario}.json')
        contexto.storage_state(path=caminhos[usuario])
        contexto.close()
    return caminhos


@pytest.fixture
def abrir(navegador, endereco, sessoes):
    """abrir('/guia-visual', tela='celular', tema='dark', como='membro') -> página carregada.

    como: 'membro', 'admin' ou None (sem login).
    """
    contextos = []

    def _abrir(caminho='/', tela='computador', tema='light', como='membro'):
        contexto = navegador.new_context(viewport=TELAS[tela], color_scheme=tema,
                                         has_touch=tela == 'celular', is_mobile=tela == 'celular',
                                         storage_state=sessoes[como] if como else None)
        contextos.append(contexto)
        pagina = contexto.new_page()
        pagina.erros_js = []
        pagina.on('pageerror', lambda erro: pagina.erros_js.append(str(erro)))
        # Algo bloqueado pela política de segurança (CSP) também conta como erro.
        pagina.on('console', lambda mensagem: pagina.erros_js.append(mensagem.text)
                  if 'Content Security Policy' in mensagem.text else None)
        pagina.goto(endereco + caminho, wait_until='networkidle')
        return pagina

    yield _abrir
    for contexto in contextos:
        contexto.close()
