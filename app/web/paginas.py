"""Páginas gerais: início, guia visual e páginas de erro."""
import re
from datetime import date, timedelta
from pathlib import Path

from flask import current_app, render_template, request
from sqlalchemy import select
from werkzeug.exceptions import BadRequest

from app.dominio import StatusImagem, StatusJob, TipoAmostra
from app.extensions import db
from app.segmentacao import obter_motor
from app.servicos.painel import Dia, Painel, fatias_do_tipo, montar_painel
from app.web import web_bp
from app.web.apresentacao import (
    apresentar_status, data_por_extenso, hora_local, icone, icone_do_tipo, itens_de_navegacao,
    nome_do_motor, numero, plural, porcentagem,
)
from app.web.identidade import pessoa_atual

# Funções disponíveis em todos os templates.
for _funcao in (icone, icone_do_tipo, apresentar_status, itens_de_navegacao, numero, plural,
                porcentagem, data_por_extenso, nome_do_motor):
    web_bp.add_app_template_global(_funcao)
web_bp.add_app_template_filter(hora_local)


@web_bp.app_template_global()
def dica_do_motor(nome_motor: str) -> str:
    return obter_motor(nome_motor).dica_foto


def tipos_de_amostra():
    return db.session.scalars(select(TipoAmostra).order_by(TipoAmostra.ordem)).all()


@web_bp.get('/')
def inicio():
    """Painel: como está o trabalho, no geral ou de um tipo de amostra (?tipo=graos)."""
    tipos = tipos_de_amostra()
    tipo = next((t for t in tipos if t.codigo == request.args.get('tipo')), None)
    pessoa = pessoa_atual()
    painel = montar_painel(tipos, tipo, pessoa, com_equipe=pessoa.eh_administrador)
    return render_template('painel.html', painel=painel, tipos=tipos, resumo=_resumo_em_uma_frase(painel),
                           primeiro_nome=pessoa.nome.split()[0])


def _resumo_em_uma_frase(painel: Painel) -> str:
    """A primeira coisa que a pessoa lê no painel: quanto falta."""
    numeros = painel.numeros
    if not numeros.coletas:
        return 'Nenhuma coleta ainda. Crie a primeira para começar.'
    if numeros.pendentes:
        falta = 'Falta' if numeros.pendentes == 1 else 'Faltam'
        return (f'{falta} {plural(numeros.pendentes, "região", "regiões")} para anotar em '
                f'{plural(painel.coletas_pendentes, "coleta")}.')
    if numeros.regioes:
        return f'Tudo anotado: {plural(numeros.anotadas, "região", "regiões")}. Bom trabalho!'
    return 'As fotos ainda não têm regiões para anotar.'


@web_bp.get('/guia-visual')
def guia_visual():
    """Vitrine do design system: cores, tipografia e componentes, com exemplos vivos."""
    tipos = tipos_de_amostra()
    sprite = Path(current_app.static_folder, 'icones.svg').read_text(encoding='utf-8')
    # Dados inventados para os exemplos de gráficos.
    exemplo_fatias = fatias_do_tipo(tipos[0], dict(zip((c.id for c in tipos[0].classes_ativas),
                                                       (120, 45, 32, 30, 13, 12, 8, 5, 2)))) if tipos else []
    hoje = date.today()
    exemplo_dias = [Dia(hoje - timedelta(days=13 - i), n)
                    for i, n in enumerate((0, 46, 0, 0, 52, 32, 0, 46, 59, 0, 55, 34, 55, 95))]
    return render_template(
        'guia_visual.html', tipos=tipos, exemplo_fatias=exemplo_fatias, exemplo_dias=exemplo_dias,
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
