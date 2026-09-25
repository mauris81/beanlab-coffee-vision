"""Rotas que devolvem páginas HTML (o que as pessoas veem).

Um único blueprint, `web`, com as rotas separadas por assunto:
    paginas.py     início, guia visual, páginas de erro
    identidade.py  "Quem é você?" (entrar/sair) e proteção de formulários (CSRF)
    coletas.py     coletas, envio de fotos, fotos e miniaturas
"""
from flask import Blueprint

web_bp = Blueprint('web', __name__)

from app.web import coletas, identidade, paginas  # noqa: E402,F401  (registram as rotas)
