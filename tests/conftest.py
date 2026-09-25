"""Preparação comum dos testes.

Cada teste recebe uma aplicação nova, com banco e fotos numa pasta temporária,
criada pelas migrações de verdade (as mesmas que rodam em produção).
"""
import pytest

from app import create_app
from app.config import ConfigTeste
from app.dominio import Coleta, Imagem, OrigemImagem, OrigemRegiao, Regiao, TipoAmostra
from app.extensions import db
from app.servicos.banco import preparar_banco


@pytest.fixture
def app(tmp_path):
    aplicacao = create_app(ConfigTeste(pasta_dados=tmp_path / 'dados'))
    with aplicacao.app_context():
        preparar_banco()
        yield aplicacao
        db.session.remove()
        db.engine.dispose()  # no Windows, libera o arquivo do banco para a pasta ser apagada


@pytest.fixture
def cliente(app):
    return app.test_client()


def tipo(codigo: str) -> TipoAmostra:
    return db.session.scalars(db.select(TipoAmostra).filter_by(codigo=codigo)).one()


def classe(tipo_codigo: str, classe_codigo: str):
    return next(c for c in tipo(tipo_codigo).classes if c.codigo == classe_codigo)


def criar_coleta(tipo_codigo='graos', num_regioes=3, nome='Coleta de teste') -> Coleta:
    """Coleta com uma imagem e `num_regioes` regiões quadradas, ainda sem anotação."""
    coleta = Coleta(nome=nome, tipo_amostra=tipo(tipo_codigo))
    imagem = Imagem(
        coleta=coleta, hash_sha256=f'{nome}'.encode().hex().ljust(64, '0')[:64],
        extensao='jpg', nome_original='foto.jpg', largura=1000, altura=800,
        tamanho_bytes=1234, origem=OrigemImagem.ARQUIVO,
    )
    for i in range(num_regioes):
        x = 10 + i * 60
        imagem.regioes.append(Regiao.do_poligono(
            [[x, 10], [x + 50, 10], [x + 50, 60], [x, 60]],
            origem=OrigemRegiao.AUTOMATICA, motor='teste',
        ))
    db.session.add(coleta)
    db.session.commit()
    return coleta
