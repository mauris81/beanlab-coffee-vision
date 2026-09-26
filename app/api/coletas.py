"""/api/coletas: lista curta de coletas, que o celular guarda para fotografar sem sinal."""
from flask import url_for
from sqlalchemy import select

from app.api import api_bp
from app.dominio import Coleta
from app.extensions import db

LIMITE = 100  # as mais recentes bastam: no campo se fotografa para coletas novas


@api_bp.get('/coletas')
def listar_coletas():
    coletas = db.session.scalars(select(Coleta).order_by(Coleta.criada_em.desc()).limit(LIMITE)).all()
    return {'coletas': [{
        'id': coleta.id,
        'nome': coleta.nome,
        'tipo': coleta.tipo_amostra.nome,
        'data': coleta.data_coleta.isoformat() if coleta.data_coleta else None,
        'envio': url_for('web.enviar_fotos', coleta_id=coleta.id),
    } for coleta in coletas]}
