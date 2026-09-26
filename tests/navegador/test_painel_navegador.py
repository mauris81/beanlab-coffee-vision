"""Painel no navegador: acessibilidade com dados de verdade e os caminhos que ele abre."""
import re

import pytest

from app.dominio import Coleta, Pessoa, StatusImagem, TipoAmostra
from app.extensions import db
from app.servicos.anotacoes import CONFIANCA_DUVIDA, anotar_regiao
from app.servicos.ingestao import receber_foto
from app.servicos.segmentacao import agendar_segmentacao, executar_job
from tests.fabrica_imagens import foto_de_graos, foto_jpeg
from tests.navegador.conftest import violacoes_wcag

pytestmark = pytest.mark.navegador


@pytest.fixture(scope='module')
def coleta_do_painel(aplicacao):
    """Coleta de grãos segmentada, com uma região anotada, uma em dúvida e uma foto com erro."""
    with aplicacao.app_context():
        graos = db.session.scalars(db.select(TipoAmostra).filter_by(codigo='graos')).one()
        coleta = Coleta(nome='Painel: talhão 9', tipo_amostra=graos)
        db.session.add(coleta)
        db.session.flush()
        imagem = receber_foto(coleta, foto_de_graos(semente=900), 'bandeja.png').imagem
        com_erro = receber_foto(coleta, foto_jpeg(cor=(1, 2, 3)), 'escura.jpg').imagem
        com_erro.status = StatusImagem.ERRO
        job = agendar_segmentacao(imagem)
        db.session.commit()
        executar_job(job.id)
        membro = db.session.scalars(db.select(Pessoa).filter_by(usuario='membro')).one()
        classes = {c.codigo: c for c in graos.classes}
        r1, r2 = imagem.regioes[:2]
        anotar_regiao(r1, classes['sem_defeito'], pessoa=membro)
        anotar_regiao(r2, classes['preto'], pessoa=membro, confianca=CONFIANCA_DUVIDA)
        db.session.commit()
        return {'id': coleta.id, 'nome': coleta.nome}


@pytest.mark.parametrize('tema', ['light', 'dark'])
@pytest.mark.parametrize('tela', ['celular', 'computador'])
@pytest.mark.parametrize('caminho', ['/', '/?tipo=graos'])
def test_painel_acessivel_com_dados(abrir, coleta_do_painel, caminho, tela, tema):
    pagina = abrir(caminho, tela, tema, como='admin')
    assert pagina.get_by_role('heading', name='Quem anotou').is_visible()
    assert violacoes_wcag(pagina) == ''
    assert pagina.erros_js == []
    if tela == 'celular':
        assert pagina.evaluate('document.documentElement.scrollWidth <= window.innerWidth')


def test_continuar_anotando_abre_uma_coleta_com_pendencias(abrir, coleta_do_painel):
    pagina = abrir('/', 'celular')
    pagina.get_by_role('link', name='Continuar anotando').click()
    pagina.wait_for_url(re.compile(r'/coletas/\d+/anotar$'))


def test_filtrar_por_tipo_mostra_as_classes(abrir, coleta_do_painel):
    pagina = abrir('/')
    pagina.get_by_role('navigation', name='Mostrar o painel de').get_by_role('link', name='Grãos').click()
    pagina.wait_for_url(re.compile(r'\?tipo=graos'))
    assert pagina.get_by_role('heading', name='Painel de grãos', level=1).is_visible()
    tabela = pagina.get_by_role('table', name='Regiões de grãos por classe')
    assert tabela.get_by_role('rowheader', name='Sem defeito').is_visible()


def test_revisar_duvidas_abre_o_lote_filtrado(abrir, coleta_do_painel):
    pagina = abrir('/')
    pagina.get_by_role('link', name=f'Revisar dúvidas de {coleta_do_painel["nome"]}').click()
    pagina.wait_for_url(re.compile(rf'/coletas/{coleta_do_painel["id"]}/lote\?mostrar=duvidas'))
    atual = pagina.locator('.filtros [aria-current="page"]')
    assert atual.inner_text().startswith('Em dúvida (1)')
    assert pagina.locator('input[name="regioes"]').count() == 1
