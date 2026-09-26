"""Excluir coleta e conta no navegador: diálogo acessível, confirmação e resultado."""
import pytest

from app.dominio import Coleta, Papel, Pessoa, TipoAmostra
from app.extensions import db
from app.servicos.anotacoes import anotar_regiao
from app.servicos.contas import criar_conta
from app.servicos.ingestao import receber_foto
from app.servicos.segmentacao import agendar_segmentacao, executar_job
from tests.fabrica_imagens import foto_de_graos
from tests.navegador.conftest import violacoes_wcag

pytestmark = pytest.mark.navegador


@pytest.fixture
def coleta_anotada(aplicacao):
    with aplicacao.app_context():
        graos = db.session.scalars(db.select(TipoAmostra).filter_by(codigo='graos')).one()
        coleta = Coleta(nome='Para excluir', tipo_amostra=graos)
        db.session.add(coleta)
        db.session.flush()
        imagem = receber_foto(coleta, foto_de_graos(semente=77, linhas=2, colunas=2), 'bandeja.png').imagem
        job = agendar_segmentacao(imagem)
        db.session.commit()
        executar_job(job.id)
        anotar_regiao(imagem.regioes[0], graos.classes[0])
        db.session.commit()
        return coleta.id


def test_excluir_coleta_pedindo_o_nome(abrir, aplicacao, coleta_anotada):
    pagina = abrir(f'/coletas/{coleta_anotada}', 'celular', como='admin')
    pagina.get_by_role('button', name='Excluir coleta').click()
    dialogo = pagina.get_by_role('dialog', name='Excluir a coleta "Para excluir"?')
    assert dialogo.is_visible()
    assert pagina.evaluate('document.activeElement.textContent.trim()') == 'Cancelar'  # foco na opção segura
    assert violacoes_wcag(pagina) == ''

    dialogo.get_by_label('Para confirmar, digite o nome da coleta').fill('para excluir')
    dialogo.get_by_role('button', name='Excluir coleta').click()
    pagina.wait_for_url('**/coletas')
    assert 'Coleta "Para excluir" excluída, com 1 foto.' in pagina.inner_text('main')
    with aplicacao.app_context():
        assert db.session.get(Coleta, coleta_anotada) is None
    assert pagina.erros_js == []


def test_excluir_conta_nunca_usada(abrir, aplicacao):
    with aplicacao.app_context():
        pessoa, _ = criar_conta('Conta Engano', 'conta.engano', Papel.MEMBRO)
        db.session.commit()
        pessoa_id = pessoa.id
    pagina = abrir('/pessoas', como='admin')
    pagina.get_by_role('button', name='Excluir a conta de Conta Engano').click()
    dialogo = pagina.get_by_role('dialog', name='Excluir a conta de Conta Engano?')
    assert 'some por completo' in dialogo.inner_text()
    assert violacoes_wcag(pagina) == ''
    dialogo.get_by_role('button', name='Excluir conta').click()
    pagina.wait_for_selector('text=Conta de Conta Engano excluída.')
    with aplicacao.app_context():
        assert db.session.get(Pessoa, pessoa_id) is None
