"""Rotas que devolvem páginas HTML."""
import re
from pathlib import Path

from flask import Blueprint, current_app, render_template
from sqlalchemy import select

from app.dominio import StatusImagem, StatusJob, TipoAmostra
from app.extensions import db
from app.web.apresentacao import apresentar_status, icone, icone_do_tipo, itens_de_navegacao

web_bp = Blueprint('web', __name__)

# Funções disponíveis em todos os templates.
for _funcao in (icone, icone_do_tipo, apresentar_status, itens_de_navegacao):
    web_bp.add_app_template_global(_funcao)


def _tipos_de_amostra():
    return db.session.scalars(select(TipoAmostra).order_by(TipoAmostra.ordem)).all()


@web_bp.get('/')
def inicio():
    return render_template('inicio.html', tipos=_tipos_de_amostra())


@web_bp.get('/guia-visual')
def guia_visual():
    """Vitrine do design system: cores, tipografia e componentes, com exemplos vivos."""
    tipos = _tipos_de_amostra()
    sprite = Path(current_app.static_folder, 'icones.svg').read_text(encoding='utf-8')
    return render_template(
        'guia_visual.html', tipos=tipos,
        opcoes_tipos=[('', 'Escolha…')] + [(t.codigo, t.nome) for t in tipos],
        status_imagem=list(StatusImagem), status_job=list(StatusJob),
        nomes_icones=re.findall(r'<symbol id="i-([a-z-]+)"', sprite),
    )


# --- Páginas de erro ---------------------------------------------------------------

@web_bp.app_errorhandler(404)
def pagina_nao_encontrada(_erro):
    return render_template(
        'erro.html', codigo=404, titulo='Página não encontrada',
        mensagem='O endereço pode estar errado ou a página mudou de lugar.',
    ), 404


@web_bp.app_errorhandler(500)
def erro_interno(_erro):
    return render_template(
        'erro.html', codigo=500, titulo='Algo deu errado do nosso lado',
        mensagem='Nada do que você fez causou isso. Tente de novo em instantes; se '
                 'continuar, avise o responsável pela plataforma.',
    ), 500
