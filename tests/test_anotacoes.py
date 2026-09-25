"""Regras de anotação e cálculo de progresso."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.dominio import Anotacao
from app.extensions import db
from app.servicos.anotacoes import AnotacaoInvalida, anotar_regiao, progresso_da_coleta
from app.servicos.pessoas import obter_ou_criar_pessoa
from tests.conftest import classe, criar_coleta


def test_regiao_nova_e_pendente(app):
    coleta = criar_coleta(num_regioes=3)
    regiao = coleta.imagens[0].regioes[0]
    assert regiao.pendente
    assert regiao.anotacao_vigente is None

    progresso = progresso_da_coleta(coleta.id)
    assert (progresso.total, progresso.anotadas, progresso.pendentes) == (3, 0, 3)
    assert progresso.percentual == 0.0


def test_progresso_conta_so_o_que_foi_anotado(app):
    """Regressão do bug antigo: 'Pendente' contava como anotado e o painel mostrava 100%."""
    coleta = criar_coleta(num_regioes=3)
    regioes = coleta.imagens[0].regioes
    anotar_regiao(regioes[0], classe('graos', 'ardido'))
    anotar_regiao(regioes[1], classe('graos', 'verde'))
    db.session.commit()

    progresso = progresso_da_coleta(coleta.id)
    assert (progresso.total, progresso.anotadas, progresso.pendentes) == (3, 2, 1)
    assert progresso.percentual == 66.7
    assert progresso.por_classe == {'ardido': 1, 'verde': 1}


def test_mudar_de_ideia_guarda_historico_e_conta_so_a_ultima(app):
    coleta = criar_coleta(num_regioes=1)
    regiao = coleta.imagens[0].regioes[0]
    maria = obter_ou_criar_pessoa('Maria')
    anotar_regiao(regiao, classe('graos', 'verde'), pessoa=maria)
    anotar_regiao(regiao, classe('graos', 'ardido'), pessoa=maria, observacao='revisado')
    db.session.commit()

    assert [a.classe.codigo for a in regiao.anotacoes] == ['verde', 'ardido']
    assert regiao.anotacao_vigente.classe.codigo == 'ardido'
    progresso = progresso_da_coleta(coleta.id)
    assert progresso.anotadas == 1
    assert progresso.por_classe == {'ardido': 1}


def test_progresso_nao_mistura_coletas(app):
    coleta_a = criar_coleta(num_regioes=2, nome='A')
    coleta_b = criar_coleta(num_regioes=5, nome='B')
    anotar_regiao(coleta_b.imagens[0].regioes[0], classe('graos', 'preto'))
    db.session.commit()
    assert progresso_da_coleta(coleta_a.id).anotadas == 0
    assert progresso_da_coleta(coleta_b.id).total == 5


def test_classe_de_outro_tipo_de_amostra_e_recusada(app):
    regiao = criar_coleta('graos').imagens[0].regioes[0]
    with pytest.raises(AnotacaoInvalida, match='não é uma classe de Grãos'):
        anotar_regiao(regiao, classe('folhas', 'ferrugem'))


def test_classe_inativa_e_recusada(app):
    regiao = criar_coleta().imagens[0].regioes[0]
    preto = classe('graos', 'preto')
    preto.ativa = False
    with pytest.raises(AnotacaoInvalida, match='desativada'):
        anotar_regiao(regiao, preto)


@pytest.mark.parametrize('confianca', [-0.1, 1.5])
def test_confianca_fora_de_0_a_1_e_recusada(app, confianca):
    regiao = criar_coleta().imagens[0].regioes[0]
    with pytest.raises(AnotacaoInvalida, match='entre 0 e 1'):
        anotar_regiao(regiao, classe('graos', 'verde'), confianca=confianca)


def test_banco_tambem_recusa_confianca_invalida(app):
    """Proteção dupla: mesmo quem gravar sem passar pelo serviço é barrado."""
    regiao = criar_coleta().imagens[0].regioes[0]
    db.session.add(Anotacao(regiao=regiao, classe=classe('graos', 'verde'), confianca=2))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_observacao_em_branco_vira_vazia(app):
    regiao = criar_coleta().imagens[0].regioes[0]
    anotacao = anotar_regiao(regiao, classe('graos', 'verde'), observacao='   ')
    assert anotacao.observacao is None
