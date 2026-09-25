"""Tela de anotação no navegador: teclado, toque, desfazer, lote e acessibilidade."""
import re

import pytest

from app.dominio import Coleta, TipoAmostra
from app.extensions import db
from app.servicos.ingestao import receber_foto
from app.servicos.segmentacao import agendar_segmentacao, executar_job
from tests.fabrica_imagens import foto_de_graos
from tests.navegador.conftest import violacoes_wcag

pytestmark = pytest.mark.navegador

_contador = iter(range(1000))


@pytest.fixture
def coleta_pronta(aplicacao):
    """Coleta de grãos com uma foto já segmentada."""
    n = next(_contador)
    with aplicacao.app_context():
        graos = db.session.scalars(db.select(TipoAmostra).filter_by(codigo='graos')).one()
        coleta = Coleta(nome=f'Coleta {n}', tipo_amostra=graos)
        db.session.add(coleta)
        db.session.flush()
        imagem = receber_foto(coleta, foto_de_graos(semente=100 + n), f'foto{n}.png').imagem
        job = agendar_segmentacao(imagem)
        db.session.commit()
        executar_job(job.id)
        total = len(imagem.regioes)
        return {'id': coleta.id, 'total': total}


def entrar_e_abrir(abrir, coleta, caminho, tela='computador'):
    return abrir(caminho, tela)  # já entra como "membro" (sessão guardada no conftest)


def progresso(pagina) -> str:
    return pagina.inner_text('[data-progresso] .progresso__legenda strong')


# ------------------------------------------------------------ uma por vez

def test_anotar_pelo_teclado_com_duvida_e_desfazer(abrir, coleta_pronta):
    total = coleta_pronta['total']
    pagina = entrar_e_abrir(abrir, coleta_pronta, f"/coletas/{coleta_pronta['id']}/anotar")
    pagina.wait_for_selector('[data-area]:not([hidden])')
    assert pagina.inner_text('[data-legenda]').startswith(f'Região 1 de {total}')

    pagina.keyboard.press('3')  # Ardido
    assert pagina.inner_text('[data-legenda]').startswith(f'Região 2 de {total}')
    assert 'Região 1: Ardido.' in pagina.inner_text('[data-ultima]')
    pagina.wait_for_function(f"document.querySelector('[data-progresso] strong').textContent.startsWith('1 de {total}')")

    pagina.keyboard.press('d')  # dúvida
    assert pagina.is_checked('[data-duvida]')
    pagina.keyboard.press('1')  # Sem defeito, com dúvida
    assert 'Região 2: Sem defeito (com dúvida).' in pagina.inner_text('[data-ultima]')
    assert pagina.inner_text('[data-legenda]').startswith(f'Região 3 de {total}')

    pagina.keyboard.press('z')  # desfaz a região 2
    pagina.wait_for_function("document.querySelector('[data-legenda]').textContent.startsWith('Região 2 ')")
    pagina.wait_for_function(f"document.querySelector('[data-progresso] strong').textContent.startsWith('1 de {total}')")
    assert pagina.get_attribute('[data-classe="sem_defeito"]', 'aria-pressed') == 'false'

    pagina.keyboard.press('ArrowLeft')  # volta para a 1: continua Ardido
    assert pagina.inner_text('[data-legenda]').startswith('Região 1 ')
    assert pagina.get_attribute('[data-classe="ardido"]', 'aria-pressed') == 'true'

    # O que ficou gravado no servidor bate com a tela
    pagina.reload(wait_until='networkidle')
    assert progresso(pagina).startswith(f'1 de {total}')
    assert pagina.erros_js == []


def test_atalhos_nao_disparam_enquanto_digita_observacao(abrir, coleta_pronta):
    pagina = entrar_e_abrir(abrir, coleta_pronta, f"/coletas/{coleta_pronta['id']}/anotar")
    pagina.wait_for_selector('[data-area]:not([hidden])')
    pagina.click('text=Observação')
    pagina.fill('[data-observacao]', 'furo 3 perto da ponta')
    pagina.keyboard.press('3')  # digitando: não pode anotar
    assert pagina.inner_text('[data-legenda]').startswith('Região 1 ')
    assert progresso(pagina).startswith('0 de')


def test_anotar_pelo_toque_no_celular(abrir, coleta_pronta):
    pagina = entrar_e_abrir(abrir, coleta_pronta, f"/coletas/{coleta_pronta['id']}/anotar", 'celular')
    pagina.wait_for_selector('[data-area]:not([hidden])')
    pagina.get_by_role('button', name=re.compile('^Brocado')).tap()
    assert pagina.inner_text('[data-legenda]').startswith('Região 2 ')
    assert violacoes_wcag(pagina) == ''
    assert pagina.evaluate('document.documentElement.scrollWidth') <= 390


@pytest.mark.parametrize('tema', ['light', 'dark'])
def test_tela_de_anotacao_acessivel(abrir, coleta_pronta, tema):
    pagina = abrir(f"/coletas/{coleta_pronta['id']}/anotar", 'computador', tema)
    pagina.wait_for_selector('[data-area]:not([hidden])')
    assert violacoes_wcag(pagina) == ''


# ------------------------------------------------------------------ em lote

def test_lote_marcar_todas_aplicar_e_desfazer(abrir, coleta_pronta):
    total = coleta_pronta['total']
    pagina = entrar_e_abrir(abrir, coleta_pronta, f"/coletas/{coleta_pronta['id']}/lote")
    assert violacoes_wcag(pagina) == ''
    pagina.get_by_role('button', name='Marcar todas desta página').click()
    assert pagina.inner_text('[data-contagem]') == f'{total} marcadas'
    pagina.get_by_role('button', name=re.compile('^Sem defeito')).click()
    pagina.wait_for_selector(f'text={total} regiões anotadas como Sem defeito.')
    assert pagina.is_visible('text=Nenhuma região pendente')

    pagina.get_by_role('button', name='Desfazer').click()
    pagina.wait_for_selector(f'text=Desfeito: {total} regiões voltaram a ficar pendente.')
    assert pagina.locator('[data-item]').count() == total


def test_lote_shift_clique_marca_intervalo(abrir, coleta_pronta):
    pagina = entrar_e_abrir(abrir, coleta_pronta, f"/coletas/{coleta_pronta['id']}/lote")
    itens = pagina.locator('[data-item]')
    itens.nth(0).click()
    itens.nth(3).click(modifiers=['Shift'])
    assert pagina.inner_text('[data-contagem]') == '4 marcadas'
    pagina.keyboard.press('2')  # tecla da classe "Preto" aplica às marcadas
    pagina.wait_for_selector('text=4 regiões anotadas como Preto.')
