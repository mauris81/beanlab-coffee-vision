"""Páginas gerais: início, guia visual e páginas de erro."""
import re
from pathlib import Path

from flask import current_app, render_template
from sqlalchemy import select
from werkzeug.exceptions import BadRequest

from app.dominio import StatusImagem, StatusJob, TipoAmostra
from app.extensions import db
from app.segmentacao import obter_motor
from app.web import web_bp
from app.web.apresentacao import (
    apresentar_status, hora_local, icone, icone_do_tipo, itens_de_navegacao, plural,
)

# Funções disponíveis em todos os templates.
for _funcao in (icone, icone_do_tipo, apresentar_status, itens_de_navegacao, plural):
    web_bp.add_app_template_global(_funcao)
web_bp.add_app_template_filter(hora_local)


@web_bp.app_template_global()
def dica_do_motor(nome_motor: str) -> str:
    return obter_motor(nome_motor).dica_foto


def tipos_de_amostra():
    return db.session.scalars(select(TipoAmostra).order_by(TipoAmostra.ordem)).all()


@web_bp.get('/')
def inicio():
    return render_template('inicio.html', tipos=tipos_de_amostra())


@web_bp.get('/guia-visual')
def guia_visual():
    """Vitrine do design system: cores, tipografia e componentes, com exemplos vivos."""
    tipos = tipos_de_amostra()
    sprite = Path(current_app.static_folder, 'icones.svg').read_text(encoding='utf-8')
    return render_template(
        'guia_visual.html', tipos=tipos,
        opcoes_tipos=[('', 'Escolha…')] + [(t.codigo, t.nome) for t in tipos],
        status_imagem=list(StatusImagem), status_job=list(StatusJob),
        nomes_icones=re.findall(r'<symbol id="i-([a-z-]+)"', sprite),
    )


# --- Páginas de erro ---------------------------------------------------------------

def _pagina_de_erro(codigo, titulo, mensagem):
    return render_template('erro.html', codigo=codigo, titulo=titulo, mensagem=mensagem), codigo


@web_bp.app_errorhandler(400)
def pedido_invalido(erro):
    # Mensagem própria (ex.: abort(400, '...')) ou uma genérica em português,
    # nunca o texto padrão do Werkzeug, que é em inglês.
    mensagem = erro.description if erro.description != BadRequest.description \
        else 'O pedido veio incompleto. Volte e tente de novo.'
    return _pagina_de_erro(400, 'Não foi possível concluir', mensagem)


@web_bp.app_errorhandler(403)
def sem_permissao(_erro):
    return _pagina_de_erro(403, 'Esta página é só para a administração',
                           'Se você precisa fazer isso, peça a quem administra a plataforma.')


@web_bp.app_errorhandler(404)
def pagina_nao_encontrada(_erro):
    return _pagina_de_erro(404, 'Página não encontrada',
                           'O endereço pode estar errado ou a página mudou de lugar.')


@web_bp.app_errorhandler(413)
def envio_grande_demais(_erro):
    limite_mb = current_app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    return _pagina_de_erro(413, 'Envio grande demais',
                           f'Cada envio pode ter até {limite_mb} MB. Volte e envie as fotos '
                           'em partes menores (por exemplo, 10 de cada vez).')


@web_bp.app_errorhandler(500)
def erro_interno(_erro):
    return _pagina_de_erro(500, 'Algo deu errado do nosso lado',
                           'Nada do que você fez causou isso. Tente de novo em instantes; se '
                           'continuar, avise o responsável pela plataforma.')
