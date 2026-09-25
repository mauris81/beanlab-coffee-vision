"""Rotas que devolvem páginas HTML."""
from flask import Blueprint, render_template
from sqlalchemy import select

from app.dominio import TipoAmostra
from app.extensions import db

web_bp = Blueprint('web', __name__)


@web_bp.get('/')
def inicio():
    tipos = db.session.scalars(select(TipoAmostra).order_by(TipoAmostra.ordem)).all()
    return render_template('inicio.html', tipos=tipos)
