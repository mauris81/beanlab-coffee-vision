"""Rotas que devolvem páginas HTML (o que as pessoas veem).

Um único blueprint, `web`, com as rotas separadas por assunto:
    paginas.py     início, guia visual, páginas de erro
    identidade.py  login (porta de entrada), primeiro acesso, minha conta, CSRF
    admin.py       administração de pessoas (contas)
    coletas.py     coletas, envio de fotos, fotos e miniaturas
    anotacao.py    anotar uma por vez e em lote; recortes e foto média
    aplicativo.py  aplicativo no celular: service worker e "Fotos no celular" (sem sinal)
"""
from flask import Blueprint

web_bp = Blueprint('web', __name__)

from app.web import admin, anotacao, aplicativo, coletas, identidade, paginas  # noqa: E402,F401  (registram as rotas)
