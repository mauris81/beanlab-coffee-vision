"""Proteções do próprio banco de dados (valem mesmo se o código tiver um erro)."""
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.dominio import Anotacao, Coleta, Imagem, OrigemImagem, Regiao
from app.extensions import db
from app.servicos.anotacoes import anotar_regiao
from tests.conftest import classe, criar_coleta


def contar(modelo):
    return db.session.scalar(select(func.count()).select_from(modelo))


def test_chaves_estrangeiras_estao_ligadas(app):
    regiao = criar_coleta().imagens[0].regioes[0]
    db.session.add(Anotacao(regiao_id=regiao.id, classe_id=99999))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_modo_wal_esta_ligado(app):
    assert db.session.execute(text('PRAGMA journal_mode')).scalar() == 'wal'


def test_apagar_coleta_apaga_tudo_que_depende_dela(app):
    coleta = criar_coleta(num_regioes=2)
    anotar_regiao(coleta.imagens[0].regioes[0], classe('graos', 'verde'))
    db.session.commit()

    # Direto no banco (sem o ORM), para provar que o ON DELETE CASCADE funciona.
    db.session.execute(text('DELETE FROM coleta WHERE id = :id'), {'id': coleta.id})
    db.session.commit()
    assert (contar(Coleta), contar(Imagem), contar(Regiao), contar(Anotacao)) == (0, 0, 0, 0)


def test_classe_com_anotacoes_nao_pode_ser_apagada(app):
    anotar_regiao(criar_coleta().imagens[0].regioes[0], classe('graos', 'verde'))
    db.session.commit()
    with pytest.raises(IntegrityError):
        db.session.execute(text('DELETE FROM classe WHERE id = :id'),
                           {'id': classe('graos', 'verde').id})


def test_mesma_foto_duas_vezes_na_mesma_coleta_e_recusada(app):
    coleta = criar_coleta(num_regioes=0)
    repetida = coleta.imagens[0]
    db.session.add(Imagem(
        coleta=coleta, hash_sha256=repetida.hash_sha256, extensao='jpg',
        nome_original='outra.jpg', largura=10, altura=10, tamanho_bytes=1,
        origem=OrigemImagem.ARQUIVO,
    ))
    with pytest.raises(IntegrityError):
        db.session.commit()
