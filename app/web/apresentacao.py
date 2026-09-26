"""Como as coisas aparecem na tela: ícones, menu e textos de status.

Tudo aqui fica disponível em qualquer template (registrado em web/rotas.py).
Manter isso num lugar só garante que "pronta" tenha sempre o mesmo texto, cor e
ícone em todas as telas.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone

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


def numero(quantidade: int) -> str:
    """1250 -> "1.250" (separador de milhar brasileiro)."""
    return f'{quantidade:,}'.replace(',', '.')


def plural(quantidade: int, singular: str, forma_plural: str | None = None) -> str:
    """"1 foto", "3 fotos", "1.250 regiões": número com separador brasileiro + palavra certa."""
    palavra = singular if quantidade == 1 else (forma_plural or singular + 's')
    return f'{numero(quantidade)} {palavra}'


def hora_local(valor: datetime | None, formato: str = '%d/%m/%Y %H:%M') -> str:
    """Datas do banco estão em UTC; na tela, no fuso do computador que roda a plataforma."""
    if valor is None:
        return ''
    return valor.replace(tzinfo=timezone.utc).astimezone().strftime(formato)


_MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto',
          'setembro', 'outubro', 'novembro', 'dezembro']
_DIAS_DA_SEMANA = ['segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira',
                   'sábado', 'domingo']


def data_por_extenso(dia: date) -> str:
    """"quarta-feira, 24 de setembro", sem depender do idioma configurado no Windows."""
    return f'{_DIAS_DA_SEMANA[dia.weekday()]}, {dia.day} de {_MESES[dia.month - 1]}'


def porcentagem(valor: float) -> str:
    """"35%"; abaixo de 1% (mas acima de zero), "menos de 1%", para não parecer que é zero."""
    if 0 < valor < 1:
        return 'menos de 1%'
    return f'{round(valor)}%'


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
# O guia visual (ferramenta de quem programa) fica no rodapé, fora do menu.
ITENS_DE_NAVEGACAO = [
    ('web.inicio', 'Início', 'inicio'),
    ('web.coletas', 'Coletas', 'imagem'),
]
ITENS_DA_ADMINISTRACAO = [
    ('web.pessoas', 'Pessoas', 'usuario'),
]

# Páginas "de dentro" de um item do menu: marcam o item como atual.
_SECAO_DO_ENDPOINT = {'web.nova_coleta': 'web.coletas', 'web.coleta': 'web.coletas',
                      'web.anotar': 'web.coletas', 'web.anotar_lote': 'web.coletas'}


def itens_de_navegacao(pessoa=None):
    """Itens do menu para esta pessoa. Sem login ou com senha provisória: nenhum (os
    links não funcionariam até trocar a senha). A administração também vê "Pessoas"."""
    if pessoa is None or pessoa.precisa_trocar_senha:
        return []
    itens = ITENS_DE_NAVEGACAO + (ITENS_DA_ADMINISTRACAO if pessoa.eh_administrador else [])
    return [
        {'url': url_for(endpoint), 'texto': texto, 'icone': nome_icone,
         'atual': _SECAO_DO_ENDPOINT.get(request.endpoint, request.endpoint) == endpoint}
        for endpoint, texto, nome_icone in itens
    ]
