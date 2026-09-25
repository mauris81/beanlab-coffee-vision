"""Recebimento de fotos, recortes prontos, COCO e exclusão."""
import pytest
from sqlalchemy import func, select

from app.armazenamento import armazenamento_de_imagens
from app.dominio import Anotacao, Coleta, Imagem, OrigemRegiao, StatusImagem
from app.extensions import db
from app.servicos.imagens import abrir_orientada
from app.servicos.ingestao import (
    ImportacaoInvalida, excluir_imagem, importar_coco, receber_foto, receber_recorte,
)
from tests.conftest import tipo
from tests.fabrica_imagens import coco, foto_jpeg, png


def nova_coleta(tipo_codigo='graos', nome='Talhão 3') -> Coleta:
    coleta = Coleta(nome=nome, tipo_amostra=tipo(tipo_codigo))
    db.session.add(coleta)
    db.session.flush()
    return coleta


def test_foto_valida_e_guardada_com_miniatura(app):
    resultado = receber_foto(nova_coleta(), foto_jpeg(400, 300), 'IMG_0001.jpg')
    imagem = resultado.imagem
    assert resultado.situacao == 'nova'
    assert (imagem.largura, imagem.altura, imagem.extensao) == (400, 300, 'jpg')
    assert imagem.status == StatusImagem.AGUARDANDO
    armazenamento = armazenamento_de_imagens()
    assert armazenamento.caminho(imagem.hash_sha256, 'jpg').is_file()
    assert armazenamento.caminho_miniatura(imagem.hash_sha256).is_file()


def test_foto_de_celular_deitada_e_considerada_de_pe(app):
    """EXIF orientação 6 = gravada deitada, deve ser vista girada 90°."""
    resultado = receber_foto(nova_coleta(), foto_jpeg(400, 300, orientacao=6), 'celular.jpg')
    assert (resultado.imagem.largura, resultado.imagem.altura) == (300, 400)
    miniatura = abrir_orientada(armazenamento_de_imagens().caminho_miniatura(resultado.imagem.hash_sha256))
    assert miniatura.height > miniatura.width


def test_data_e_gps_da_foto_sao_lidos(app):
    foto = foto_jpeg(data='2026:03:12 09:41:00', gps=(-21.2345, -45.0012))
    imagem = receber_foto(nova_coleta(), foto, 'campo.jpg').imagem
    assert imagem.capturada_em.isoformat() == '2026-03-12T09:41:00'
    assert imagem.latitude == pytest.approx(-21.2345, abs=1e-4)
    assert imagem.longitude == pytest.approx(-45.0012, abs=1e-4)


def test_arquivo_que_nao_e_imagem_e_recusado_com_mensagem(app):
    resultado = receber_foto(nova_coleta(), b'isto nao e uma foto', 'planilha.jpg')
    assert resultado.situacao == 'recusada'
    assert 'não é uma imagem' in resultado.mensagem
    assert db.session.scalar(select(func.count(Imagem.id))) == 0


def test_formato_vem_do_conteudo_nao_do_nome(app):
    resultado = receber_foto(nova_coleta(), png(), 'na-verdade-png.jpg')
    assert resultado.imagem.extensao == 'png'


def test_foto_repetida_na_mesma_coleta_nao_duplica(app):
    coleta = nova_coleta()
    foto = foto_jpeg()
    primeira = receber_foto(coleta, foto, 'a.jpg')
    segunda = receber_foto(coleta, foto, 'copia.jpg')
    assert segunda.situacao == 'repetida' and segunda.imagem is primeira.imagem
    assert '"a.jpg"' in segunda.mensagem
    outra_coleta = receber_foto(nova_coleta(nome='Outra'), foto, 'a.jpg')
    assert outra_coleta.situacao == 'nova'


def test_nome_do_arquivo_nao_leva_pastas(app):
    resultado = receber_foto(nova_coleta(), foto_jpeg(), '../../segredo/IMG_1.jpg')
    assert resultado.imagem.nome_original == 'IMG_1.jpg'


# ------------------------------------------------------------------ recortes

def test_recorte_com_fundo_transparente_vira_regiao_com_contorno(app):
    imagem = receber_recorte(nova_coleta('folhas'), png(200, 150, transparente=True), 'folha.png').imagem
    [regiao] = imagem.regioes
    assert imagem.status == StatusImagem.PRONTA and imagem.ja_segmentada
    assert regiao.origem == OrigemRegiao.IMPORTADA
    raio = 50  # min(200, 150) // 3
    assert regiao.area_px == pytest.approx(3.1416 * raio ** 2, rel=0.05)


def test_recorte_sem_transparencia_vira_regiao_da_imagem_toda(app):
    imagem = receber_recorte(nova_coleta('folhas'), png(200, 150), 'folha.png').imagem
    [regiao] = imagem.regioes
    assert regiao.bbox == [0, 0, 200, 150] and regiao.area_px == 200 * 150


# ---------------------------------------------------------------------- COCO

def _coco_de_exemplo():
    quadrado = [10, 10, 110, 10, 110, 60, 10, 60]
    return coco(
        imagens=[(1, 'pasta/a.jpg'), (2, 'b.jpg'), (3, 'sumiu.jpg')],
        anotacoes=[
            {'id': 1, 'image_id': 1, 'category_id': 1, 'segmentation': [quadrado], 'area': 5000},
            {'id': 2, 'image_id': 1, 'category_id': 2, 'segmentation': [quadrado]},
            {'id': 3, 'image_id': 2, 'category_id': 1, 'segmentation': {'counts': 'x', 'size': [1, 1]}},
        ],
        categorias={1: 'ARDIDO', 2: 'Categoria sem par'},
    )


def test_importar_coco(app):
    arquivos = {'a.jpg': foto_jpeg(cor=(1, 2, 3)), 'b.jpg': foto_jpeg(cor=(4, 5, 6)),
                'extra.jpg': foto_jpeg(cor=(7, 8, 9))}
    resumo = importar_coco(nova_coleta(), arquivos, _coco_de_exemplo())
    db.session.commit()

    assert [r.situacao for r in resumo.resultados] == ['nova', 'nova']
    assert resumo.regioes == 2 and resumo.regioes_ignoradas == 1  # a 3ª é RLE
    assert resumo.anotacoes == 1  # "ARDIDO" casa com a classe Ardido
    assert resumo.categorias_sem_classe == {'Categoria sem par'}
    assert resumo.imagens_sem_arquivo == ['sumiu.jpg']
    assert resumo.arquivos_sem_anotacao == ['extra.jpg']
    anotacao = db.session.scalars(select(Anotacao)).one()
    assert anotacao.classe.codigo == 'ardido' and anotacao.origem.value == 'importada'
    assert anotacao.regiao.area_px == 5000


def test_coco_invalido_gera_mensagem_clara(app):
    with pytest.raises(ImportacaoInvalida, match='formato COCO'):
        importar_coco(nova_coleta(), {}, b'{"sem": "imagens"}')


# ------------------------------------------------------------------- exclusão

def test_excluir_foto_apaga_arquivo_so_depois_do_commit_e_se_ninguem_usa(app):
    foto = foto_jpeg()
    usada_em_duas = receber_foto(nova_coleta(), foto, 'a.jpg').imagem
    receber_foto(nova_coleta(nome='Outra'), foto, 'a.jpg')
    caminho = armazenamento_de_imagens().caminho(usada_em_duas.hash_sha256, 'jpg')
    db.session.commit()

    apagar_arquivo = excluir_imagem(usada_em_duas)
    assert caminho.is_file(), 'o arquivo não pode sumir antes do commit'
    db.session.commit()
    apagar_arquivo()
    assert caminho.is_file(), 'a outra coleta ainda usa a mesma foto'

    [restante] = db.session.scalars(select(Imagem)).all()
    apagar_arquivo = excluir_imagem(restante)
    db.session.commit()
    apagar_arquivo()
    assert not caminho.is_file()
