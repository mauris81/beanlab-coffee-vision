"""Como as coisas aparecem na tela: ícones, menu e textos de status.

Tudo aqui fica disponível em qualquer template (registrado em web/rotas.py).
Manter isso num lugar só garante que "pronta" tenha sempre o mesmo texto, cor e
ícone em todas as telas.
"""
from dataclasses import dataclass

from flask import request, url_for
from markupsafe import Markup, escape

from app.dominio import StatusImagem, StatusJob


def icone(nome: str, rotulo: str | None = None, classe: str = '') -> Markup:
    """SVG do sprite static/icones.svg.

    Sem `rotulo`, o ícone é decorativo (o leitor de tela ignora). Com `rotulo`,
    ele é lido, e deve ser usado quando o ícone aparece SEM texto ao lado.
    """
    href = f"{url_for('static', filename='icones.svg')}#i-{nome}"
    acessibilidade = (f'role="img" aria-label="{escape(rotulo)}"' if rotulo
                      else 'aria-hidden="true" focusable="false"')
    return Markup(f'<svg class="icone {escape(classe)}" {acessibilidade}>'
                  f'<use href="{href}"></use></svg>')


def plural(quantidade: int, singular: str, forma_plural: str | None = None) -> str:
    """"1 foto", "3 fotos", "1.250 regiões": número com separador brasileiro + palavra certa."""
    palavra = singular if quantidade == 1 else (forma_plural or singular + 's')
    return f'{quantidade:,}'.replace(',', '.') + f' {palavra}'


_ICONE_POR_TIPO = {'graos': 'grao', 'folhas': 'folha', 'flores': 'flor', 'frutos': 'fruto'}


def icone_do_tipo(codigo_tipo: str) -> str:
    return _ICONE_POR_TIPO.get(codigo_tipo, 'imagem')


@dataclass(frozen=True)
class Apresentacao:
    texto: str
    variante: str  # neutro | sucesso | aviso | perigo | info
    icone: str
    animado: bool = False


_STATUS = {
    StatusImagem.AGUARDANDO: Apresentacao('Na fila', 'neutro', 'relogio'),
    StatusImagem.SEGMENTANDO: Apresentacao('Segmentando', 'info', 'processando', animado=True),
    StatusImagem.PRONTA: Apresentacao('Pronta', 'sucesso', 'sucesso'),
    StatusImagem.ERRO: Apresentacao('Erro', 'perigo', 'erro'),
    StatusJob.NA_FILA: Apresentacao('Na fila', 'neutro', 'relogio'),
    StatusJob.PROCESSANDO: Apresentacao('Processando', 'info', 'processando', animado=True),
    StatusJob.CONCLUIDO: Apresentacao('Concluído', 'sucesso', 'sucesso'),
    StatusJob.ERRO: Apresentacao('Erro', 'perigo', 'erro'),
}


def apresentar_status(status) -> Apresentacao:
    return _STATUS[status]


# --- Menu ----------------------------------------------------------------------
# Só entram páginas que já existem. Cada fase acrescenta as suas aqui.
# (endpoint, texto, ícone)
ITENS_DE_NAVEGACAO = [
    ('web.inicio', 'Início', 'inicio'),
    ('web.coletas', 'Coletas', 'imagem'),
    ('web.guia_visual', 'Guia visual', 'paleta'),
]

# Páginas "de dentro" de um item do menu: marcam o item como atual.
_SECAO_DO_ENDPOINT = {'web.nova_coleta': 'web.coletas', 'web.coleta': 'web.coletas'}


def itens_de_navegacao():
    return [
        {'url': url_for(endpoint), 'texto': texto, 'icone': nome_icone,
         'atual': _SECAO_DO_ENDPOINT.get(request.endpoint, request.endpoint) == endpoint}
        for endpoint, texto, nome_icone in ITENS_DE_NAVEGACAO
    ]
