"""Proteções para a plataforma publicada na internet (app/seguranca.py)."""
import re

import pytest

from app.dominio import Papel
from app.extensions import db
from app.seguranca import LimiteDeTentativas
from tests.conftest import SENHA, TOKEN, criar_coleta, criar_pessoa, entrar_como

TAILSCALE = {'REMOTE_ADDR': '127.0.0.1'}  # o Funnel repassa os acessos a partir deste PC
WIFI = {'REMOTE_ADDR': '192.168.0.50'}


def _pela_internet(ip='203.0.113.9'):
    return {'X-Forwarded-For': ip, 'X-Forwarded-Proto': 'https', 'X-Forwarded-Host': 'pc.rede.ts.net'}


def _entrar(cliente, usuario, senha=SENHA, ambiente=None, cabecalhos=None):
    with cliente.session_transaction() as sessao:
        sessao['_csrf'] = TOKEN
    return cliente.post('/entrar', data={'_csrf': TOKEN, 'usuario': usuario, 'senha': senha},
                        environ_base=ambiente or WIFI, headers=cabecalhos or {})


# ---------------------------------------------------------------- cabeçalhos

def test_cabecalhos_de_seguranca_em_toda_resposta(logado):
    for caminho in ('/', '/entrar', '/static/css/base.css', '/api/saude'):
        cabecalhos = logado.get(caminho).headers
        politica = cabecalhos['Content-Security-Policy']
        assert "script-src 'self'" in politica and "frame-ancestors 'none'" in politica
        assert "'unsafe-inline'" not in politica.split('style-src-attr')[0]  # nunca para scripts
        assert cabecalhos['X-Content-Type-Options'] == 'nosniff'
        assert cabecalhos['X-Frame-Options'] == 'DENY'
        assert cabecalhos['Referrer-Policy'] == 'same-origin'
        assert 'Strict-Transport-Security' not in cabecalhos  # acesso por http (Wi-Fi)


def test_paginas_com_dados_nao_ficam_guardadas_sem_conferir(logado):
    assert logado.get('/coletas').headers['Cache-Control'] == 'private, no-cache'


def _paginas_para_conferir():
    coleta = criar_coleta()
    return ('/', '/coletas', '/coletas/nova', '/guia-visual', '/conta', '/fotos-no-celular',
                f'/coletas/{coleta.id}', f'/coletas/{coleta.id}/anotar', f'/coletas/{coleta.id}/lote')


def test_nenhuma_pagina_tem_codigo_embutido(logado):
    """A política de segurança bloqueia scripts escritos dentro da página (é assim que um
    ataque XSS injeta código). Então a plataforma não pode ter nenhum."""
    script_embutido = re.compile(r'<script(?![^>]*\bsrc=)[^>]*>', re.I)
    evento_embutido = re.compile(r'<[^>]+\s on[a-z]+\s*=', re.I)
    for caminho in _paginas_para_conferir():
        html = logado.get(caminho).get_data(as_text=True)
        assert not script_embutido.search(html), caminho
        assert not evento_embutido.search(html), caminho
        assert 'javascript:' not in html, caminho


# ------------------------------------------------------ proxy (Tailscale)

def test_acesso_pela_internet_vira_https(cliente, administracao):
    resposta = cliente.get('/entrar', environ_base=TAILSCALE, headers=_pela_internet())
    assert resposta.headers['Strict-Transport-Security'] == 'max-age=31536000'
    cookie = resposta.headers['Set-Cookie']
    assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=Lax' in cookie


def test_cabecalhos_de_proxy_vindos_do_wifi_sao_ignorados(cliente, administracao):
    """Alguém no Wi-Fi não pode fingir ser outro endereço nem dizer que usa HTTPS."""
    resposta = cliente.get('/entrar', environ_base=WIFI, headers=_pela_internet())
    assert 'Strict-Transport-Security' not in resposta.headers
    assert 'Secure' not in resposta.headers['Set-Cookie']


def test_no_wifi_o_cookie_funciona_sem_https(cliente, administracao):
    criar_pessoa('Ana')
    resposta = _entrar(cliente, 'ana')
    assert resposta.status_code == 302 and 'Secure' not in resposta.headers['Set-Cookie']


def test_modo_desenvolvimento_nunca_atende_pela_internet(app, cliente, administracao):
    app.debug = True
    try:
        assert cliente.get('/entrar', environ_base=TAILSCALE, headers=_pela_internet()).status_code == 403
        assert cliente.get('/entrar', environ_base=TAILSCALE).status_code == 200  # no próprio PC, sim
    finally:
        app.debug = False


# -------------------------------------------------- limite de tentativas por IP

@pytest.fixture
def limite_pequeno(app):
    app.extensions['limite_de_login'] = LimiteDeTentativas(maximo=3, janela_segundos=900)


def test_limite_por_endereco_protege_varias_contas(cliente, administracao, limite_pequeno):
    """Errar 3 vezes (em contas diferentes) bloqueia o endereço, mesmo com a senha certa depois."""
    criar_pessoa('Ana')
    for usuario in ('bruno', 'carla', 'davi'):
        assert _entrar(cliente, usuario, 'chute-errado-1').status_code == 401
    resposta = _entrar(cliente, 'ana')
    assert resposta.status_code == 429
    assert 'Muitas tentativas erradas' in resposta.get_data(as_text=True)
    # Outra pessoa, em outro endereço (pela internet), continua entrando.
    outra = _entrar(cliente, 'ana', ambiente=TAILSCALE, cabecalhos=_pela_internet('198.51.100.7'))
    assert outra.status_code == 302


def test_endereco_real_pela_internet_e_o_do_celular(cliente, administracao, limite_pequeno):
    """Pelo Funnel todos os pedidos chegam de 127.0.0.1; o limite usa o IP real do celular."""
    for _ in range(3):
        _entrar(cliente, 'ninguem', 'errada-123', ambiente=TAILSCALE, cabecalhos=_pela_internet('203.0.113.9'))
    assert _entrar(cliente, 'x', 'y', ambiente=TAILSCALE, cabecalhos=_pela_internet('203.0.113.9')).status_code == 429
    assert _entrar(cliente, 'x', 'y', ambiente=TAILSCALE, cabecalhos=_pela_internet('203.0.113.10')).status_code == 401


def test_codigo_de_primeiro_acesso_nao_pode_ser_adivinhado(cliente, limite_pequeno):
    with cliente.session_transaction() as sessao:
        sessao['_csrf'] = TOKEN
    dados = {'_csrf': TOKEN, 'codigo': '0000-0000', 'nome': 'Intruso', 'usuario': 'intruso',
             'senha': 'senha-longa-9', 'confirmacao': 'senha-longa-9'}
    for _ in range(3):
        assert cliente.post('/primeiro-acesso', data=dados, environ_base=WIFI).status_code == 200
    assert cliente.post('/primeiro-acesso', data=dados, environ_base=WIFI).status_code == 429


def test_limite_esquece_tentativas_antigas(monkeypatch):
    relogio = [1000.0]
    monkeypatch.setattr('app.seguranca.time.monotonic', lambda: relogio[0])
    limite = LimiteDeTentativas(maximo=2, janela_segundos=60)
    limite.registrar('1.2.3.4')
    limite.registrar('1.2.3.4')
    assert limite.excedido('1.2.3.4') and not limite.excedido('5.6.7.8')
    relogio[0] += 61
    assert not limite.excedido('1.2.3.4')


# ------------------------------------------ respostas para o JavaScript (JSON)

def test_envio_pela_fila_sem_login_responde_401_em_json(cliente, administracao):
    coleta = criar_coleta()
    resposta = cliente.post(f'/coletas/{coleta.id}/enviar', headers={'X-Envio-Via': 'fila'})
    assert resposta.status_code == 401 and 'erro' in resposta.get_json()


def test_codigo_csrf_errado_responde_json_para_o_javascript(logado):
    coleta = criar_coleta()
    resposta = logado.post(f'/coletas/{coleta.id}/enviar', headers={'X-Envio-Via': 'fila', 'X-CSRF': 'velho'})
    assert resposta.status_code == 400 and resposta.get_json()['motivo'] == 'csrf'


def test_formulario_comum_com_csrf_errado_continua_em_pagina(logado):
    coleta = criar_coleta()
    resposta = logado.post(f'/coletas/{coleta.id}/enviar', data={'_csrf': 'velho'})
    assert resposta.status_code == 400 and resposta.mimetype == 'text/html'


def test_senha_provisoria_bloqueia_a_fila_em_json(cliente, administracao):
    pessoa = criar_pessoa('Nova', Papel.MEMBRO)
    pessoa.precisa_trocar_senha = True
    db.session.commit()
    entrar_como(cliente, pessoa)
    coleta = criar_coleta()
    resposta = cliente.post(f'/coletas/{coleta.id}/enviar', headers={'X-Envio-Via': 'fila', 'X-CSRF': TOKEN})
    assert resposta.status_code == 403 and 'erro' in resposta.get_json()
