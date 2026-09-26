"""Quem está usando a plataforma: login, primeiro acesso, minha conta, e proteção CSRF.

PORTA DE ENTRADA (proteger_paginas): toda página exige login, menos as das listas
PAGINAS_PUBLICAS e SEMPRE_LIBERADAS. Assim uma página nova nasce protegida, sem
precisar lembrar. Pedidos do JavaScript recebem erros em JSON (pedido_do_javascript).
Enquanto não existir administrador, tudo leva para "Primeiro acesso".

CSRF: todo formulário que muda dados leva um código secreto da sessão
(`{{ campo_csrf() }}`); pedidos do JavaScript mandam no cabeçalho X-CSRF.
"""
import secrets
from functools import wraps
from urllib.parse import urlsplit

from flask import (
    abort, current_app, flash, g, redirect, render_template, request, session, url_for,
)
from markupsafe import Markup

from app.dominio import Pessoa
from app.extensions import db
from app.seguranca import endereco_de_quem_pede, limite_de_login
from app.servicos.contas import (
    ContaInvalida, FalhaDeLogin, autenticar, codigo_de_primeiro_acesso, criar_primeiro_administrador,
    existe_administrador, trocar_senha,
)
from app.web import web_bp

PAGINAS_PUBLICAS = {'web.entrar', 'web.primeiro_acesso'}
# Liberadas sempre, até antes de existir administração: arquivos estáticos, o teste de
# conexão, a ajuda e as peças do aplicativo que o celular guarda para usar sem sinal (sem
# dados de ninguém: a página "Fotos no celular" lê as fotos do próprio aparelho).
SEMPRE_LIBERADAS = {'static', 'api.saude', 'web.service_worker', 'web.fotos_no_celular', 'web.ajuda'}
# Com senha provisória, só dá para trocar a senha (ou sair).
PERMITIDAS_COM_SENHA_PROVISORIA = {'web.minha_conta', 'web.sair', 'static'}


# ------------------------------------------------------------------ pessoa atual

def pessoa_atual() -> Pessoa | None:
    """A pessoa logada, ou None. Sessão de conta desativada ou com senha trocada em
    outro aparelho (versão diferente) não vale mais."""
    chave = (session.get('pessoa_id'), session.get('versao'))
    guardada = g.get('_pessoa_atual')
    if guardada is None or guardada[0] != chave:
        pessoa = db.session.get(Pessoa, chave[0]) if chave[0] else None
        if pessoa is not None and (not pessoa.ativa or pessoa.versao_sessao != chave[1]):
            pessoa = None
        g._pessoa_atual = (chave, pessoa)
    return g._pessoa_atual[1]


def exige_administrador(rota):
    @wraps(rota)
    def envolvida(*args, **kwargs):
        pessoa = pessoa_atual()
        if pessoa is None or not pessoa.eh_administrador:
            abort(403)
        return rota(*args, **kwargs)
    return envolvida


def _iniciar_sessao(pessoa: Pessoa) -> None:
    session.clear()  # nada da sessão anterior passa para a nova (evita "fixação de sessão")
    session['pessoa_id'] = pessoa.id
    session['versao'] = pessoa.versao_sessao
    session.permanent = True  # continua conectado no celular, como um aplicativo


def pedido_do_javascript() -> bool:
    """O pedido veio do JavaScript (API, envio com barra de progresso ou fila de fotos)?
    Nesses casos erros voltam em JSON, nunca como página ou redirecionamento."""
    return request.blueprint == 'api' or bool(request.headers.get('X-Envio-Via'))


def _destino_seguro(endereco: str | None) -> str:
    """Só aceita endereços desta plataforma (evita redirecionar para outro site)."""
    if endereco and endereco.startswith('/') and not endereco.startswith('//') \
            and not urlsplit(endereco).netloc and not endereco.startswith('/entrar'):
        return endereco
    return url_for('web.inicio')


# --------------------------------------------------------------- porta de entrada

@web_bp.before_app_request
def proteger_paginas():
    endpoint = request.endpoint
    if endpoint in SEMPRE_LIBERADAS:
        return None
    if not existe_administrador():  # plataforma recém-instalada
        return None if endpoint == 'web.primeiro_acesso' else redirect(url_for('web.primeiro_acesso'))
    if endpoint in PAGINAS_PUBLICAS or endpoint is None:  # None = página inexistente (404)
        return None

    pessoa = pessoa_atual()
    if pessoa is None:
        if pedido_do_javascript():
            return {'erro': 'Sua sessão terminou. Entre de novo (recarregue a página).'}, 401
        destino = request.full_path.rstrip('?') if request.method == 'GET' else None
        return redirect(url_for('web.entrar', proximo=destino))
    if pessoa.precisa_trocar_senha and endpoint not in PERMITIDAS_COM_SENHA_PROVISORIA:
        if pedido_do_javascript():
            return {'erro': 'Troque a senha provisória antes de continuar.'}, 403
        return redirect(url_for('web.minha_conta'))
    return None


# ----------------------------------------------------------------- entrar/sair

@web_bp.route('/entrar', methods=['GET', 'POST'])
def entrar():
    proximo = request.values.get('proximo')
    erro = None
    if request.method == 'POST':
        if limite_de_login().excedido(endereco_de_quem_pede()):
            return _muitas_tentativas('entrar.html', proximo=proximo,
                                      usuario=request.form.get('usuario', ''))
        try:
            pessoa = autenticar(request.form.get('usuario', ''), request.form.get('senha', ''))
        except FalhaDeLogin as falha:
            db.session.commit()  # registra a tentativa errada (conta para o bloqueio)
            limite_de_login().registrar(endereco_de_quem_pede())
            erro = str(falha)
        else:
            db.session.commit()
            _iniciar_sessao(pessoa)
            if pessoa.precisa_trocar_senha:
                flash('Boas-vindas! Antes de começar, crie a sua senha.', 'info')
                return redirect(url_for('web.minha_conta'))
            return redirect(_destino_seguro(proximo))
    elif pessoa_atual():
        return redirect(_destino_seguro(proximo))
    return render_template('entrar.html', proximo=proximo, erro=erro,
                           usuario=request.form.get('usuario', '')), (401 if erro else 200)


def _muitas_tentativas(template, **contexto):
    minutos = int(current_app.config['LOGIN_JANELA_POR_IP'].total_seconds() // 60)
    erro = (f'Muitas tentativas erradas a partir desta conexão. Espere {minutos} minutos e '
            'tente de novo. Se esqueceu a senha, peça uma nova à administração.')
    return render_template(template, erro=erro, **contexto), 429


@web_bp.post('/sair')
def sair():
    session.clear()
    flash('Você saiu. Até a próxima!', 'info')
    return redirect(url_for('web.entrar'))


# ------------------------------------------------------------- primeiro acesso

@web_bp.route('/primeiro-acesso', methods=['GET', 'POST'])
def primeiro_acesso():
    pasta = current_app.config['PASTA_DADOS']
    if codigo_de_primeiro_acesso(pasta) is None:
        return redirect(url_for('web.entrar'))
    erro = None
    if request.method == 'POST':
        if limite_de_login().excedido(endereco_de_quem_pede()):
            return _muitas_tentativas('primeiro_acesso.html', dados=request.form)
        senha, confirmacao = request.form.get('senha', ''), request.form.get('confirmacao', '')
        try:
            if senha != confirmacao:
                raise ContaInvalida('As duas senhas não são iguais.')
            pessoa = criar_primeiro_administrador(pasta, request.form.get('codigo', ''),
                                                  request.form.get('nome', ''),
                                                  request.form.get('usuario', ''), senha)
        except ContaInvalida as problema:
            limite_de_login().registrar(endereco_de_quem_pede())  # protege o código de adivinhação
            erro = str(problema)
        else:
            db.session.commit()
            _iniciar_sessao(pessoa)
            flash(f'Pronto, {pessoa.nome}! Sua conta de administração está criada. '
                  'Agora crie as contas da equipe.', 'sucesso')
            return redirect(url_for('web.pessoas'))
    return render_template('primeiro_acesso.html', erro=erro, dados=request.form)


# ----------------------------------------------------------------- minha conta

@web_bp.route('/conta', methods=['GET', 'POST'])
def minha_conta():
    pessoa = pessoa_atual()
    erro = None
    if request.method == 'POST':
        nova, confirmacao = request.form.get('senha_nova', ''), request.form.get('confirmacao', '')
        try:
            if nova != confirmacao:
                raise ContaInvalida('As duas senhas novas não são iguais.')
            trocar_senha(pessoa, request.form.get('senha_atual', ''), nova)
        except ContaInvalida as problema:
            erro = str(problema)
        else:
            db.session.commit()
            _iniciar_sessao(pessoa)  # continua conectado neste aparelho; os outros saem
            flash('Senha trocada. Sua conta foi desconectada dos outros aparelhos.', 'sucesso')
            return redirect(url_for('web.inicio'))
    return render_template('conta.html', pessoa=pessoa, erro=erro)


# ------------------------------------------------------------------------ CSRF

def token_csrf() -> str:
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(32)
    return session['_csrf']


def campo_csrf() -> Markup:
    return Markup(f'<input type="hidden" name="_csrf" value="{token_csrf()}">')


@web_bp.before_app_request
def conferir_csrf():
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return
    enviado = request.form.get('_csrf') or request.headers.get('X-CSRF')
    if not enviado or not secrets.compare_digest(enviado, session.get('_csrf', '')):
        mensagem = 'Formulário expirado ou inválido. Recarregue a página e tente de novo.'
        if pedido_do_javascript():
            return {'erro': mensagem, 'motivo': 'csrf'}, 400
        abort(400, mensagem)


web_bp.add_app_template_global(pessoa_atual)
web_bp.add_app_template_global(campo_csrf)
web_bp.add_app_template_global(token_csrf)
