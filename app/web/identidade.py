"""Quem está usando a plataforma, e proteção dos formulários.

Identificação: a pessoa diz o nome uma vez; ele fica guardado num cookie assinado
(sessão do Flask). Sem senha, por decisão do projeto (docs/ROADMAP.md).

CSRF: todo formulário que muda dados leva um código secreto da sessão
(`{{ campo_csrf() }}`). Sem ele, o pedido é recusado. Isso impede que outro site,
aberto no mesmo navegador, envie formulários para a plataforma em nome da pessoa.
"""
import secrets
from functools import wraps
from urllib.parse import urlsplit

from flask import abort, flash, g, redirect, render_template, request, session, url_for
from markupsafe import Markup
from sqlalchemy import select

from app.dominio import Pessoa
from app.extensions import db
from app.servicos.pessoas import obter_ou_criar_pessoa
from app.web import web_bp

# ------------------------------------------------------------------ pessoa atual


def pessoa_atual() -> Pessoa | None:
    # Guarda o resultado durante o pedido, mas só enquanto a sessão apontar para a
    # mesma pessoa (se ela sair ou trocar, busca de novo).
    pessoa_id = session.get('pessoa_id')
    guardada = g.get('_pessoa_atual')
    if guardada is None or guardada[0] != pessoa_id:
        g._pessoa_atual = (pessoa_id, db.session.get(Pessoa, pessoa_id) if pessoa_id else None)
    return g._pessoa_atual[1]


def exige_pessoa(rota):
    """Rotas que criam ou mudam dados precisam saber quem é a pessoa."""
    @wraps(rota)
    def envolvida(*args, **kwargs):
        if pessoa_atual() is None:
            flash('Antes, diga quem é você. Seu nome fica registrado no que você fizer.', 'info')
            return redirect(url_for('web.entrar', proximo=request.full_path.rstrip('?')))
        return rota(*args, **kwargs)
    return envolvida


def _destino_seguro(endereco: str | None) -> str:
    """Só aceita endereços desta plataforma (evita redirecionar para outro site)."""
    if endereco and endereco.startswith('/') and not endereco.startswith('//') \
            and not urlsplit(endereco).netloc:
        return endereco
    return url_for('web.inicio')


@web_bp.route('/entrar', methods=['GET', 'POST'])
def entrar():
    proximo = request.values.get('proximo')
    erro = None
    if request.method == 'POST':
        try:
            pessoa = obter_ou_criar_pessoa(request.form.get('nome', ''))
        except ValueError as problema:
            erro = str(problema)
        else:
            db.session.commit()
            session['pessoa_id'] = pessoa.id
            session.permanent = True
            flash(f'Olá, {pessoa.nome}!', 'sucesso')
            return redirect(_destino_seguro(proximo))
    conhecidas = db.session.scalars(
        select(Pessoa).filter_by(ativa=True).order_by(Pessoa.nome).limit(20)).all()
    return render_template('entrar.html', proximo=proximo, erro=erro, conhecidas=conhecidas,
                           nome=request.form.get('nome', ''))


@web_bp.post('/sair')
def sair():
    session.pop('pessoa_id', None)
    flash('Pronto. Diga seu nome de novo quando voltar.', 'info')
    return redirect(url_for('web.inicio'))


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
        abort(400, 'Formulário expirado ou inválido. Recarregue a página e tente de novo.')


web_bp.add_app_template_global(pessoa_atual)
web_bp.add_app_template_global(campo_csrf)
web_bp.add_app_template_global(token_csrf)
