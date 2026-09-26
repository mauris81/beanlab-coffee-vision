"""Marcar na foto, num navegador de verdade (com um marcador falso no lugar do SAM)."""
import re

import pytest

from app.dominio import Coleta, Regiao, TipoAmostra
from app.extensions import db
from app.servicos.ingestao import receber_foto
from tests.fabrica_imagens import foto_jpeg
from tests.navegador.conftest import violacoes_wcag
from tests.test_marcacao import MarcadorFalso

pytestmark = pytest.mark.navegador

_contador = iter(range(1000))


@pytest.fixture
def foto(aplicacao):
    original = aplicacao.extensions['marcador']
    aplicacao.extensions['marcador'] = MarcadorFalso()
    n = next(_contador)
    with aplicacao.app_context():
        flores = db.session.scalars(db.select(TipoAmostra).filter_by(codigo='flores')).one()
        coleta = Coleta(nome=f'Florada {n}', tipo_amostra=flores)
        db.session.add(coleta)
        db.session.flush()
        imagem = receber_foto(coleta, foto_jpeg(400, 300, cor=(30, 90 + n, 40)), 'planta.jpg', ja_segmentada=True).imagem
        db.session.commit()
        yield imagem.id
    aplicacao.extensions['marcador'] = original


def regioes_da_foto(aplicacao, imagem_id):
    with aplicacao.app_context():
        return db.session.query(Regiao).filter_by(imagem_id=imagem_id).count()


def centro_do_visor(pagina):
    caixa = pagina.locator('[data-visor]').bounding_box()
    return caixa['x'] + caixa['width'] / 2, caixa['y'] + caixa['height'] / 2


@pytest.mark.parametrize('tela', ['computador', 'celular'])
def test_tocar_escolher_classe_e_excluir(abrir, aplicacao, foto, tela):
    pagina = abrir(f'/imagens/{foto}/marcar', tela)
    pagina.wait_for_function('() => document.querySelector("[data-contornos]").getAttribute("viewBox")')
    x, y = centro_do_visor(pagina)

    # 1. Toque num lugar vazio: aparece o contorno proposto
    if tela == 'celular':
        pagina.touchscreen.tap(x, y)
    else:
        pagina.mouse.click(x, y)
    pagina.locator('.contorno--previa').wait_for()
    assert pagina.get_by_role('heading', name='Nova região: o que é?').is_visible()
    assert violacoes_wcag(pagina) == ''

    # 2. Menor/Maior trocam o contorno
    assert 'Contorno 2 de 2' in pagina.inner_text('[data-texto-painel]')
    pagina.get_by_role('button', name='Menor').click()
    assert 'Contorno 1 de 2' in pagina.inner_text('[data-texto-painel]')

    # 3. Escolher a classe salva a região já anotada
    pagina.get_by_role('button', name=re.compile('Flor aberta')).click()
    pagina.wait_for_selector('text=Região marcada: Flor aberta.')
    assert '1 região nesta foto' in pagina.inner_text('[data-contagem]')
    assert regioes_da_foto(aplicacao, foto) == 1

    # 4. Tocar no contorno seleciona; dá para excluir (no celular a página rolou até os
    #    botões: toca onde a foto está agora)
    pagina.locator('[data-visor]').scroll_into_view_if_needed()
    x, y = centro_do_visor(pagina)
    if tela == 'celular':
        pagina.touchscreen.tap(x, y)
    else:
        pagina.mouse.click(x, y)
    pagina.get_by_role('heading', name='Região selecionada').wait_for()
    assert 'Classe atual: Flor aberta' in pagina.inner_text('[data-texto-painel]')
    pagina.get_by_role('button', name='Excluir região').click()
    pagina.get_by_role('dialog').get_by_role('button', name='Excluir região').click()
    pagina.wait_for_selector('text=Região excluída.')
    assert regioes_da_foto(aplicacao, foto) == 0
    assert pagina.erros_js == []


def test_lembra_o_tamanho_preferido(abrir, aplicacao, foto):
    """Salvou com "Menor"? O próximo toque já começa no menor."""
    pagina = abrir(f'/imagens/{foto}/marcar')
    pagina.wait_for_function('() => document.querySelector("[data-contornos]").getAttribute("viewBox")')
    caixa = pagina.locator('[data-visor]').bounding_box()
    pagina.mouse.click(caixa['x'] + caixa['width'] * 0.3, caixa['y'] + caixa['height'] * 0.5)
    pagina.locator('.contorno--previa').wait_for()
    assert 'Contorno 2 de 2' in pagina.inner_text('[data-texto-painel]')  # o sugerido
    pagina.get_by_role('button', name='Menor').click()
    pagina.get_by_role('button', name=re.compile('Botão floral')).click()
    pagina.wait_for_selector('text=Região marcada: Botão floral.')
    pagina.mouse.click(caixa['x'] + caixa['width'] * 0.7, caixa['y'] + caixa['height'] * 0.5)
    pagina.locator('.contorno--previa').wait_for()
    assert 'Contorno 1 de 2' in pagina.inner_text('[data-texto-painel]')
    pagina.keyboard.press('Escape')
    assert pagina.erros_js == []


def test_zoom_e_teclado(abrir, aplicacao, foto):
    pagina = abrir(f'/imagens/{foto}/marcar')
    pagina.wait_for_function('() => document.querySelector("[data-contornos]").getAttribute("viewBox")')
    antes = pagina.locator('[data-camada]').bounding_box()
    pagina.get_by_role('button', name='Aproximar').click()
    depois = pagina.locator('[data-camada]').bounding_box()
    assert depois['width'] > antes['width'] * 1.4
    # Teclado: foco na foto, Enter marca o que está na mira (centro)
    pagina.locator('[data-visor]').focus()
    pagina.keyboard.press('Enter')
    pagina.locator('.contorno--previa').wait_for()
    pagina.keyboard.press('2')  # tecla da classe "Flor aberta"
    pagina.wait_for_selector('text=Região marcada: Flor aberta.')
    pagina.keyboard.press('Escape')
    assert regioes_da_foto(aplicacao, foto) == 1
    assert pagina.erros_js == []


def test_sem_ia_explica(abrir, aplicacao, foto):
    aplicacao.extensions['marcador'].disponivel = lambda: False
    pagina = abrir(f'/imagens/{foto}/marcar', tema='dark')
    pagina.get_by_text('Marcar com um toque não está disponível').wait_for()
    assert violacoes_wcag(pagina) == ''
