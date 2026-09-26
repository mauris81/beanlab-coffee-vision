"""Interações reais: teclado, tema, diálogo, avisos e layout no celular."""

import pytest

pytestmark = pytest.mark.navegador



def _foco(pagina) -> str:
    return pagina.evaluate('document.activeElement.textContent.trim()')


# --------------------------------------------------------------- teclado

def test_primeiro_tab_oferece_pular_para_o_conteudo(abrir):
    pagina = abrir('/guia-visual')
    pagina.keyboard.press('Tab')
    assert _foco(pagina) == 'Pular para o conteúdo'
    assert pagina.evaluate('document.activeElement.getBoundingClientRect().top >= 0'), \
        'o link precisa aparecer na tela quando recebe o foco'
    pagina.keyboard.press('Enter')
    assert pagina.evaluate('document.activeElement.id') == 'conteudo'


def test_foco_do_teclado_e_visivel(abrir):
    pagina = abrir('/')
    pagina.keyboard.press('Tab')
    pagina.keyboard.press('Tab')  # primeiro item depois do "pular": a marca
    contorno = pagina.evaluate('getComputedStyle(document.activeElement).outlineStyle')
    assert contorno == 'solid'


# ------------------------------------------------------------------ tema

def test_botao_de_tema_alterna_e_lembra_a_escolha(abrir):
    pagina = abrir('/', tema='light')
    botao = pagina.locator('#alternar-tema')
    assert botao.get_attribute('aria-label') == 'Usar tema escuro'

    botao.click()
    assert pagina.evaluate('document.documentElement.dataset.theme') == 'dark'
    assert pagina.evaluate('getComputedStyle(document.body).backgroundColor') == 'rgb(20, 17, 15)'
    assert botao.get_attribute('aria-label') == 'Usar tema claro'

    pagina.reload(wait_until='networkidle')
    assert pagina.evaluate('document.documentElement.dataset.theme') == 'dark'


def test_tema_segue_o_aparelho_quando_ninguem_escolheu(abrir):
    pagina = abrir('/', tema='dark')
    assert pagina.evaluate('document.documentElement.dataset.theme') is None
    assert pagina.evaluate('getComputedStyle(document.body).backgroundColor') == 'rgb(20, 17, 15)'


# --------------------------------------------------------------- diálogo

def test_dialogo_foca_a_acao_segura_e_fecha_com_esc(abrir):
    pagina = abrir('/guia-visual')
    pagina.click('text=Excluir coleta…')
    assert pagina.is_visible('#dialogo-exemplo')
    assert _foco(pagina) == 'Cancelar'
    pagina.keyboard.press('Escape')
    assert not pagina.is_visible('#dialogo-exemplo')


# ---------------------------------------------------------------- avisos

def test_avisos_somem_sozinhos_exceto_os_de_erro(abrir):
    pagina = abrir('/guia-visual')
    pagina.click('text=Aviso de sucesso')
    pagina.click('text=Aviso de erro')
    assert 'Anotação salva.' in pagina.inner_text('#avisos')
    assert pagina.get_attribute('.aviso--perigo', 'role') == 'alert'

    pagina.wait_for_timeout(5600)
    assert pagina.locator('.aviso--sucesso').count() == 0
    assert pagina.locator('.aviso--perigo').count() == 1, 'erro deve esperar a pessoa fechar'

    pagina.click('.aviso--perigo [aria-label="Fechar aviso"]')
    assert pagina.locator('.aviso--perigo').count() == 0


# --------------------------------------------------------- menu e layout

def test_menu_no_topo_no_computador(abrir):
    pagina = abrir('/coletas', 'computador')
    assert pagina.is_visible('.topo .navegacao')
    assert not pagina.is_visible('.navegacao-inferior')
    assert pagina.get_attribute('.topo [aria-current="page"]', 'href') == '/coletas'


def test_menu_na_base_da_tela_no_celular(abrir):
    pagina = abrir('/', 'celular')
    assert pagina.is_visible('.navegacao-inferior')
    assert not pagina.is_visible('.topo .navegacao')


def test_alvos_de_toque_tem_pelo_menos_44px_no_celular(abrir):
    pagina = abrir('/guia-visual', 'celular')
    pequenos = pagina.evaluate('''() =>
        [...document.querySelectorAll('a.botao, button, input, select, textarea, .navegacao__item')]
        .filter(e => e.offsetParent !== null)
        // Caixa de marcação e opção: o alvo é o rótulo inteiro (tocar no texto também marca).
        .map(e => (e.matches('input[type=checkbox], input[type=radio]') && e.closest('label')) || e)
        .map(e => [e.textContent.trim().slice(0, 30) || e.getAttribute('aria-label') || e.outerHTML.slice(0, 60),
                   Math.round(e.getBoundingClientRect().height)])
        .filter(([, altura]) => altura < 44)''')
    assert pequenos == []


def test_sem_rolagem_horizontal_no_celular(abrir):
    for caminho in ('/', '/guia-visual'):
        pagina = abrir(caminho, 'celular')
        assert pagina.evaluate('document.documentElement.scrollWidth') <= 390, caminho


def test_menu_de_baixo_nao_cobre_o_fim_da_pagina(abrir):
    pagina = abrir('/', 'celular')
    pagina.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    fim_do_conteudo = pagina.evaluate(
        "document.querySelector('.principal .conteudo').getBoundingClientRect().bottom")
    topo_do_menu = pagina.evaluate(
        "document.querySelector('.navegacao-inferior').getBoundingClientRect().top")
    assert fim_do_conteudo <= topo_do_menu
