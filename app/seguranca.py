"""Proteções para a plataforma publicada na internet (Tailscale Funnel).

Como o acesso chega (ver docs/decisoes/0007-publicacao-e-aplicativo.md):

    celular na internet ──HTTPS──> Tailscale (neste PC) ──http──> 127.0.0.1:5000 (waitress)
    celular no Wi-Fi ─────────────────http──────────────────────> 192.168.x.x:5000

O que este módulo faz:
- ProxyLocal: o Tailscale conta quem é o celular (X-Forwarded-For) e que o acesso foi
  por HTTPS (X-Forwarded-Proto). Esses cabeçalhos só valem vindos DESTE PC; do Wi-Fi
  são apagados, senão qualquer um fingiria outro endereço.
- SessaoComCookieSeguro: cookie da sessão com a marca "Secure" quando o acesso é HTTPS.
- Cabeçalhos de segurança em toda resposta (CSP e companhia).
- LimiteDeTentativas: tentativas erradas de login por endereço (IP).
- Modo desenvolvimento nunca atende quem vem pela internet.
"""
import threading
import time
from collections import deque

from flask import abort, current_app, has_request_context, request
from flask.sessions import SecureCookieSessionInterface
from werkzeug.middleware.proxy_fix import ProxyFix

# Só arquivos desta própria plataforma. 'unsafe-inline' vale apenas para o atributo
# style="" (usado em barras de progresso e cores das classes), nunca para scripts.
POLITICA_DE_CONTEUDO = '; '.join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "style-src-attr 'unsafe-inline'",
    "img-src 'self' data: blob:",  # blob: miniaturas das fotos guardadas no celular
    "font-src 'self'",
    "connect-src 'self'",
    "manifest-src 'self'",
    "worker-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

CABECALHOS_DE_SEGURANCA = {
    'Content-Security-Policy': POLITICA_DE_CONTEUDO,
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',  # o mesmo que frame-ancestors, para navegadores antigos
    'Referrer-Policy': 'same-origin',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Permissions-Policy': 'camera=(self), geolocation=(self), microphone=(), payment=(), usb=()',
}


class ProxyLocal:
    """Lê os cabeçalhos X-Forwarded-* só quando o pedido vem deste PC (do Tailscale)."""

    LOCAIS = frozenset({'127.0.0.1', '::1'})
    CABECALHOS = ('HTTP_X_FORWARDED_FOR', 'HTTP_X_FORWARDED_PROTO', 'HTTP_X_FORWARDED_HOST',
                  'HTTP_X_FORWARDED_PORT', 'HTTP_X_FORWARDED_PREFIX', 'HTTP_FORWARDED')

    def __init__(self, wsgi_app):
        self.direto = wsgi_app
        self.pelo_proxy = ProxyFix(wsgi_app, x_for=1, x_proto=1, x_host=1)

    def __call__(self, environ, start_response):
        if environ.get('REMOTE_ADDR') in self.LOCAIS:
            if environ.get('HTTP_X_FORWARDED_FOR'):
                environ['beanlab.pela_internet'] = True
            return self.pelo_proxy(environ, start_response)
        for cabecalho in self.CABECALHOS:
            environ.pop(cabecalho, None)
        return self.direto(environ, start_response)


class SessaoComCookieSeguro(SecureCookieSessionInterface):
    """Marca o cookie da sessão como "Secure" (só viaja por HTTPS) quando o acesso é HTTPS.

    Não dá para ligar sempre: pelo Wi-Fi o acesso é http, e o login deixaria de funcionar.
    Os dois endereços são sites diferentes para o navegador, então os cookies não se misturam.
    """

    def get_cookie_secure(self, app):
        return bool(app.config['SESSION_COOKIE_SECURE'] or (has_request_context() and request.is_secure))


class LimiteDeTentativas:
    """Conta tentativas erradas por chave (o IP) numa janela de tempo. Fica na memória:
    reiniciar a plataforma zera a contagem, o que é aceitável para este uso."""

    def __init__(self, maximo: int, janela_segundos: float):
        self.maximo = maximo
        self.janela = janela_segundos
        self._tentativas: dict[str, deque] = {}
        self._trava = threading.Lock()

    def _recentes(self, chave: str, agora: float) -> deque:
        fila = self._tentativas.setdefault(chave, deque())
        while fila and agora - fila[0] > self.janela:
            fila.popleft()
        return fila

    def excedido(self, chave: str) -> bool:
        with self._trava:
            return len(self._recentes(chave, time.monotonic())) >= self.maximo

    def registrar(self, chave: str) -> None:
        with self._trava:
            agora = time.monotonic()
            self._recentes(chave, agora).append(agora)
            if len(self._tentativas) > 10_000:  # não deixa a memória crescer sem limite
                for antiga in [c for c, f in self._tentativas.items() if not self._recentes(c, agora)]:
                    del self._tentativas[antiga]


def limite_de_login() -> LimiteDeTentativas:
    return current_app.extensions['limite_de_login']


def endereco_de_quem_pede() -> str:
    """IP do celular/computador (o real, mesmo vindo pelo Tailscale)."""
    return request.remote_addr or 'desconhecido'


def instalar(app) -> None:
    """Liga as proteções na aplicação (chamado por create_app)."""
    app.wsgi_app = ProxyLocal(app.wsgi_app)
    app.session_interface = SessaoComCookieSeguro()
    app.extensions['limite_de_login'] = LimiteDeTentativas(
        app.config['LOGIN_MAXIMO_POR_IP'], app.config['LOGIN_JANELA_POR_IP'].total_seconds())

    @app.before_request
    def recusar_internet_no_modo_desenvolvimento():
        # O modo desenvolvimento mostra erros detalhados e tem um depurador: nunca
        # pode ser alcançado pela internet, mesmo que o Funnel esteja ligado.
        if current_app.debug and request.environ.get('beanlab.pela_internet'):
            abort(403)

    @app.after_request
    def cabecalhos_de_seguranca(resposta):
        for nome, valor in CABECALHOS_DE_SEGURANCA.items():
            resposta.headers.setdefault(nome, valor)
        if request.is_secure:
            # "Daqui a um ano, só abra este endereço por HTTPS."
            resposta.headers.setdefault('Strict-Transport-Security', 'max-age=31536000')
        if resposta.mimetype == 'text/html':
            # Páginas mostram dados da pessoa: o navegador confere com o servidor antes
            # de reaproveitar (ninguém vê a página de outra conta pelo "voltar").
            resposta.headers.setdefault('Cache-Control', 'private, no-cache')
        return resposta
