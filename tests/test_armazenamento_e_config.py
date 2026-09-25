"""Gravação de fotos no disco e configuração. (Contas: tests/test_contas.py)"""
import pytest

from app.armazenamento import ArmazenamentoImagens
from app.config import ConfigTeste, carregar_chave_secreta


# ------------------------------------------------------------- armazenamento

def test_foto_e_guardada_pelo_hash_do_conteudo(tmp_path):
    armazenamento = ArmazenamentoImagens(tmp_path)
    salvo = armazenamento.salvar(b'conteudo da foto', 'JPEG')
    h = salvo.hash_sha256
    assert salvo.caminho == tmp_path / h[:2] / h[2:4] / f'{h}.jpg'
    assert salvo.caminho.read_bytes() == b'conteudo da foto'
    assert salvo.extensao == 'jpg' and not salvo.ja_existia


def test_mesma_foto_duas_vezes_ocupa_espaco_uma_vez(tmp_path):
    armazenamento = ArmazenamentoImagens(tmp_path)
    primeira = armazenamento.salvar(b'foto', 'jpg')
    segunda = armazenamento.salvar(b'foto', 'jpeg')
    assert segunda.ja_existia and segunda.caminho == primeira.caminho
    assert len([p for p in tmp_path.rglob('*') if p.is_file()]) == 1


def test_fotos_diferentes_com_mesmo_nome_nao_se_sobrescrevem(tmp_path):
    """Regressão: antes, dois 'IMG_0001.jpg' diferentes viravam um arquivo só."""
    armazenamento = ArmazenamentoImagens(tmp_path)
    a = armazenamento.salvar(b'foto A', 'jpg')
    b = armazenamento.salvar(b'foto B', 'jpg')
    assert a.caminho != b.caminho
    assert a.caminho.read_bytes() == b'foto A' and b.caminho.read_bytes() == b'foto B'
    assert not list(tmp_path.rglob('*.parcial'))


# ------------------------------------------------------------------ config

def test_chave_secreta_e_criada_uma_vez_e_reaproveitada(tmp_path, monkeypatch):
    monkeypatch.delenv('CAFE_SECRET_KEY', raising=False)
    primeira = carregar_chave_secreta(tmp_path)
    assert len(primeira) == 64
    assert carregar_chave_secreta(tmp_path) == primeira


def test_pasta_de_dados_pode_vir_de_variavel_de_ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv('CAFE_DATA_DIR', str(tmp_path / 'meus_dados'))
    config = ConfigTeste()
    assert config.PASTA_DADOS == tmp_path / 'meus_dados'
    assert config.SQLALCHEMY_DATABASE_URI.endswith('/meus_dados/beanlab.db')
