"""Rotas que devolvem dados em JSON (usadas pelo JavaScript das páginas)."""
from flask import Blueprint
from sqlalchemy import func, select

from app.dominio import Classe, TipoAmostra
from app.extensions import db

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.get('/saude')
def saude():
    """Confirma que o servidor e o banco respondem. Útil para testes e monitoramento."""
    return {
        'status': 'ok',
        'tipos_de_amostra': db.session.scalar(select(func.count(TipoAmostra.id))),
        'classes_ativas': db.session.scalar(select(func.count(Classe.id)).where(Classe.ativa)),
    }
