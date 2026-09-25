"""Garantias do design system que não precisam de navegador.

- Contraste WCAG 2.2 AA de todos os pares de cor usados, nos dois temas.
- Os dois blocos do tema escuro em tokens.css são idênticos.
- Todo ícone usado existe no sprite.
- Nenhuma página carrega nada da internet (a plataforma precisa funcionar no campo).
- As macros de componentes geram HTML acessível.
"""
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app.dominio import StatusImagem, StatusJob
from app.web import apresentacao

APP = Path(__file__).resolve().parent.parent / 'app'
TOKENS = (APP / 'static/css/tokens.css').read_text(encoding='utf-8')
SPRITE = (APP / 'static/icones.svg').read_text(encoding='utf-8')


# ------------------------------------------------------------------ contraste

def _bloco(seletor_regex: str) -> str:
    inicio = re.search(seletor_regex + r'\s*\{', TOKENS)
    assert inicio, f'bloco {seletor_regex} não encontrado em tokens.css'
    profundidade, i = 1, inicio.end()
    while profundidade:
        profundidade += {'{': 1, '}': -1}.get(TOKENS[i], 0)
        i += 1
    return TOKENS[inicio.end():i - 1]


def _cores(bloco: str) -> dict[str, str]:
    return dict(re.findall(r'(--cor-[a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})', bloco))


CLARO = _cores(_bloco(r'(?m)^:root'))
ESCURO = {**CLARO, **_cores(_bloco(r':root\[data-theme="dark"\]'))}


def _luminancia(hexa: str) -> float:
    canais = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    claro, escuro = sorted([_luminancia(a), _luminancia(b)], reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


TEXTO, CONTORNO = 4.5, 3.0
PARES = [
    # (frente, fundo, mínimo) — texto 4,5:1; contornos, ícones e foco 3:1
    *[(t, f, TEXTO) for t in ('--cor-texto', '--cor-texto-suave')
      for f in ('--cor-fundo', '--cor-superficie', '--cor-superficie-2')],
    ('--cor-sobre-primaria', '--cor-primaria', TEXTO),
    ('--cor-sobre-primaria', '--cor-primaria-hover', TEXTO),
    ('--cor-primaria-texto', '--cor-superficie', TEXTO),
    ('--cor-primaria-texto', '--cor-fundo', TEXTO),
    ('--cor-primaria-texto', '--cor-primaria-suave', TEXTO),
    ('--cor-superficie', '--cor-perigo', TEXTO),        # texto do botão de perigo
    ('--cor-fundo', '--cor-texto', TEXTO),              # avisos rápidos (fundo invertido)
    ('--cor-perigo', '--cor-superficie', TEXTO),        # mensagem de erro de campo
    *[(f'--cor-{s}', f'--cor-{s}-suave', TEXTO) for s in ('sucesso', 'aviso', 'perigo', 'info')],
    ('--cor-borda-controle', '--cor-superficie', CONTORNO),
    ('--cor-borda-controle', '--cor-fundo', CONTORNO),
    ('--cor-primaria', '--cor-fundo', CONTORNO),
    ('--cor-foco', '--cor-superficie', CONTORNO),
    ('--cor-foco', '--cor-fundo', CONTORNO),
]


@pytest.mark.parametrize('nome_tema, cores', [('claro', CLARO), ('escuro', ESCURO)])
@pytest.mark.parametrize('frente, fundo, minimo', PARES)
def test_contraste_wcag_aa(nome_tema, cores, frente, fundo, minimo):
    razao = contraste(cores[frente], cores[fundo])
    assert razao >= minimo, (
        f'Tema {nome_tema}: {frente} ({cores[frente]}) sobre {fundo} ({cores[fundo]}) '
        f'tem contraste {razao:.2f}:1; o mínimo é {minimo}:1')


def test_os_dois_blocos_do_tema_escuro_sao_iguais():
    """tokens.css repete o tema escuro (preferência do sistema e escolha manual)."""
    pelo_sistema = _cores(_bloco(r':root:not\(\[data-theme="light"\]\)'))
    pela_escolha = _cores(_bloco(r':root\[data-theme="dark"\]'))
    assert pelo_sistema == pela_escolha


# --------------------------------------------------------------------- ícones

ICONES_EXISTENTES = set(re.findall(r'<symbol id="i-([a-z-]+)"', SPRITE))


def _icones_usados() -> set[str]:
    usados = set()
    for arquivo in (APP / 'templates').glob('*.html'):
        texto = arquivo.read_text(encoding='utf-8')
        usados |= set(re.findall(r"icone\('([a-z-]+)'", texto))
        usados |= set(re.findall(r"icone_nome='([a-z-]+)'", texto))
        usados |= set(re.findall(r"\(\s*'([a-z][a-z-]*)',\s*'[^']+',\s*'[^']+'\s*\)", texto))  # tuplas (ícone, título, texto)
    usados |= {a.icone for a in apresentacao._STATUS.values()}
    usados |= set(apresentacao._ICONE_POR_TIPO.values()) | {'imagem'}
    usados |= {nome for _, _, nome in apresentacao.ITENS_DE_NAVEGACAO}
    return usados


def test_todo_icone_usado_existe_no_sprite():
    faltando = _icones_usados() - ICONES_EXISTENTES
    assert not faltando, f'Ícones usados mas não desenhados em static/icones.svg: {sorted(faltando)}'


def test_todo_status_tem_apresentacao():
    assert set(StatusImagem) | set(StatusJob) <= set(apresentacao._STATUS)


# ------------------------------------------------------------ páginas offline

class _ColetorDeRecursos(HTMLParser):
    """Junta os endereços que o navegador BAIXA (não os links que a pessoa clica)."""

    def __init__(self):
        super().__init__()
        self.recursos = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'link' and attrs.get('rel') in ('stylesheet', 'icon', 'manifest', 'preconnect'):
            self.recursos.append(attrs.get('href'))
        elif tag in ('script', 'img', 'source', 'iframe') and attrs.get('src'):
            self.recursos.append(attrs['src'])
        elif tag == 'use':
            self.recursos.append(attrs.get('href'))


@pytest.mark.parametrize('caminho', ['/', '/guia-visual', '/nao-existe'])
def test_paginas_nao_dependem_de_internet(cliente, caminho):
    coletor = _ColetorDeRecursos()
    coletor.feed(cliente.get(caminho).get_data(as_text=True))
    externos = [r for r in coletor.recursos if r and re.match(r'^(https?:)?//', r)]
    assert coletor.recursos and not externos, f'Recursos externos em {caminho}: {externos}'


def test_estrutura_acessivel_da_pagina(cliente):
    html = cliente.get('/').get_data(as_text=True)
    assert '<html lang="pt-BR">' in html
    assert html.index('class="pular-para-conteudo"') < html.index('<header'), \
        '"Pular para o conteúdo" deve ser o primeiro item focável'
    assert '<main class="principal" id="conteudo"' in html
    assert 'aria-current="page"' in html


def test_pagina_404_e_amigavel(cliente):
    resposta = cliente.get('/pagina-que-nao-existe')
    html = resposta.get_data(as_text=True)
    assert resposta.status_code == 404
    assert 'Página não encontrada' in html and 'Voltar ao início' in html


def test_guia_visual_mostra_todos_os_icones(cliente):
    html = cliente.get('/guia-visual').get_data(as_text=True)
    for nome in ICONES_EXISTENTES:
        assert f'<code>{nome}</code>' in html


# ------------------------------------------------------------------- macros

def _renderizar(app, trecho: str) -> str:
    with app.test_request_context():
        return app.jinja_env.from_string(
            "{% import 'componentes.html' as c %}" + trecho).render()


def test_campo_liga_dica_e_erro_ao_input(app):
    html = _renderizar(app, "{{ c.campo('talhao', 'Talhão', dica='Ex.: 3', erro='Obrigatório') }}")
    assert 'for="campo-talhao"' in html and 'id="campo-talhao"' in html
    assert 'aria-describedby="campo-talhao-dica campo-talhao-erro"' in html
    assert 'id="campo-talhao-dica"' in html and 'id="campo-talhao-erro"' in html
    assert 'aria-invalid="true"' in html and 'required' in html


def test_campo_opcional_sem_erro(app):
    html = _renderizar(app, "{{ c.campo('obs', 'Observação', tipo='textarea', opcional=True) }}")
    assert '(opcional)' in html
    assert 'aria-invalid' not in html and 'required' not in html and 'aria-describedby' not in html


def test_botao_so_com_icone_tem_nome_acessivel(app):
    html = _renderizar(app, "{{ c.botao_icone('fechar', 'Fechar aviso') }}")
    assert 'aria-label="Fechar aviso"' in html and 'aria-hidden="true"' in html


def test_botao_com_href_vira_link_e_icone_pode_vir_depois(app):
    html = _renderizar(app, "{{ c.botao('Avançar', href='/x', icone_nome='avancar', icone_depois=True) }}")
    assert html.startswith('<a ') and 'href="/x"' in html
    assert html.index('Avançar') < html.index('<svg')


def test_progresso_tem_valores_para_leitor_de_tela(app):
    html = _renderizar(app, "{{ c.progresso(4, 309, 'Talhão 3') }}")
    assert 'role="progressbar"' in html and 'aria-valuenow="4"' in html
    assert 'aria-valuemax="309"' in html and '4 de 309' in html
