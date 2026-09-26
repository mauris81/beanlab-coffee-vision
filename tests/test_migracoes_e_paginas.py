"""Migrações do banco e páginas que já existem."""
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect

from app.extensions import db


def test_modelos_e_migracoes_estao_em_sincronia(app):
    """Falha se alguém mudou um modelo em app/dominio/ e esqueceu de gerar a migração.

    Para corrigir: .venv\\Scripts\\flask.exe --app app db migrate -m "descreva a mudança"
    """
    with db.engine.connect() as conexao:
        diferencas = compare_metadata(MigrationContext.configure(conexao), db.metadata)
    assert diferencas == []


def test_migracoes_podem_ser_desfeitas_e_refeitas(app):
    db.session.remove()
    downgrade(revision='base')
    assert inspect(db.engine).get_table_names() == ['alembic_version']
    upgrade()
    assert 'anotacao' in inspect(db.engine).get_table_names()


def test_desfazer_ultima_migracao_com_dados_no_banco(app):
    """Alterar uma tabela que outras referenciam (com dados) não pode falhar nem quebrar
    as referências; e as chaves estrangeiras precisam voltar ligadas depois."""
    from tests.conftest import criar_coleta
    criar_coleta(num_regioes=2)
    db.session.remove()
    downgrade(revision='-1')
    upgrade()
    with db.engine.connect() as conexao:
        assert conexao.exec_driver_sql('PRAGMA foreign_keys').scalar() == 1
        assert conexao.exec_driver_sql('PRAGMA foreign_key_check').fetchall() == []


def test_painel_mostra_tipos_e_as_classes_de_cada_um(logado):
    resposta = logado.get('/')
    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)
    for texto in ['Grãos', 'Folhas', 'Flores', 'Frutos']:
        assert texto in html
    # As classes de cada tipo aparecem no painel do tipo, mesmo sem nada anotado.
    assert 'Ferrugem' in logado.get('/?tipo=folhas').get_data(as_text=True)
    assert 'Verde-cana' in logado.get('/?tipo=frutos').get_data(as_text=True)


def test_api_de_saude(cliente):
    resposta = cliente.get('/api/saude')
    assert resposta.status_code == 200
    assert resposta.get_json() == {'status': 'ok', 'tipos_de_amostra': 4, 'classes_ativas': 29}
