"""Rotas que devolvem dados em JSON (usadas pelo JavaScript das páginas).

Um único blueprint, `api` (prefixo /api), com as rotas separadas por assunto:
    saude.py     /api/saude: confirma que servidor e banco respondem
    anotacao.py  regiões de uma coleta, anotar, desfazer (tela de anotação)

Erros voltam como JSON: {"erro": "mensagem para a pessoa"}.
"""
from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')

from app.api import anotacao, saude  # noqa: E402,F401  (registram as rotas)
