"""Motor clássico, jobs de segmentação e fila."""
import io

import cv2
import numpy as np
import pytest
from PIL import Image

from app import segmentacao as pacote_segmentacao
from app.dominio import JobSegmentacao, OrigemRegiao, Regiao, StatusImagem, StatusJob
from app.dominio.geometria import area_do_poligono
from app.extensions import db
from app.fila import fila
from app.segmentacao.classico import MotorClassico, ParametrosClassico
from app.servicos.imagens import abrir_orientada, matriz_rgb, recortar
from app.servicos.ingestao import receber_foto
from app.servicos.segmentacao import agendar_segmentacao, executar_job
from tests.fabrica_imagens import centros_dos_graos, foto_de_graos, foto_jpeg
from tests.test_ingestao import nova_coleta


def enviar_e_segmentar(tipo_codigo='graos', conteudo=None):
    imagem = receber_foto(nova_coleta(tipo_codigo), conteudo or foto_de_graos(), 'bandeja.png').imagem
    job = agendar_segmentacao(imagem)
    db.session.commit()
    if job:
        fila().enviar([job.id])  # nos testes, roda na hora
    db.session.refresh(imagem)
    return imagem, job


# ------------------------------------------------------------- motor clássico

def _grao_por_regiao(regioes, centros) -> list[int]:
    """Para cada grão, em quantas regiões o seu centro cai (o certo é exatamente 1)."""
    return [sum(cv2.pointPolygonTest(np.array(r.poligono, np.int32), centro, False) >= 0 for r in regioes)
            for centro in centros]


@pytest.mark.parametrize('espacamento', ['separados', 'encostados'])
@pytest.mark.parametrize('semente', [1, 2, 3])
def test_motor_classico_encontra_cada_grao_uma_vez(espacamento, semente):
    rgb = matriz_rgb(foto_de_graos(semente, espacamento=espacamento))
    regioes = MotorClassico().segmentar(rgb)
    centros = centros_dos_graos(semente, espacamento=espacamento)
    assert _grao_por_regiao(regioes, centros) == [1] * len(centros)  # 48 grãos, 48 regiões
    assert len(regioes) == len(centros)  # nenhuma região a mais (fundo)
    altura, largura = rgb.shape[:2]
    for regiao in regioes:
        xs, ys = zip(*regiao.poligono)
        assert 0 <= min(xs) and max(xs) <= largura and 0 <= min(ys) and max(ys) <= altura
        # a área real (pixels) e a do contorno simplificado devem ser parecidas
        assert abs(area_do_poligono(regiao.poligono) - regiao.area_px) / regiao.area_px < 0.25


def test_modo_antigo_so_via_o_maior_grupo_de_graos():
    """Documenta a limitação do algoritmo antigo (corrigida na versão 2.1): com grãos
    separados, ele só enxergava um deles."""
    rgb = matriz_rgb(foto_de_graos(1, espacamento='separados'))
    antigo = MotorClassico(ParametrosClassico(somente_maior_grupo=True)).segmentar(rgb)
    assert len(antigo) == 1


def test_recorte_preserva_as_cores():
    """Regressão do bug antigo: recortes saíam com vermelho e azul trocados."""
    imagem = Image.new('RGB', (100, 80), (0, 0, 255))
    imagem.paste((255, 0, 0), (20, 10, 60, 50))
    saida = io.BytesIO()
    imagem.save(saida, 'PNG')
    pedaco = np.asarray(recortar(abrir_orientada(saida.getvalue()), [20, 10, 40, 40]))
    assert pedaco.shape == (40, 40, 3)
    assert np.all(pedaco == [255, 0, 0]), 'o recorte deve continuar vermelho (não azul)'


# ------------------------------------------------------------------- jobs

def test_foto_de_graos_e_segmentada_e_fica_pronta(app):
    imagem, job = enviar_e_segmentar('graos')
    db.session.refresh(job)
    assert job.status == StatusJob.CONCLUIDO and job.num_regioes == len(imagem.regioes) > 0
    assert imagem.status == StatusImagem.PRONTA
    regiao = imagem.regioes[0]
    assert (regiao.origem, regiao.motor, regiao.versao_motor) == (OrigemRegiao.AUTOMATICA, 'classico', '2.1')
    assert job.duracao_s is not None


def test_tipo_sem_motor_fica_pronto_sem_regioes(app):
    imagem, job = enviar_e_segmentar('folhas', foto_jpeg())
    assert job is None
    assert imagem.status == StatusImagem.PRONTA and imagem.regioes == []


def test_falha_do_motor_vira_erro_visivel_e_nao_trava(app, monkeypatch):
    class MotorQuebrado:
        nome, versao = 'classico', '9'
        def segmentar(self, rgb):
            raise MemoryError('sem memória para esta foto')
    monkeypatch.setitem(pacote_segmentacao.MOTORES, 'classico', MotorQuebrado())

    imagem, job = enviar_e_segmentar('graos')
    db.session.refresh(job)
    assert job.status == StatusJob.ERRO and 'sem memória' in job.mensagem_erro
    assert imagem.status == StatusImagem.ERRO

    monkeypatch.undo()  # a próxima foto segue normalmente
    outra, _ = enviar_e_segmentar('graos', foto_jpeg(cor=(9, 9, 9)))
    assert outra.status == StatusImagem.PRONTA


def test_segmentar_de_novo_troca_so_as_regioes_automaticas(app):
    imagem, job = enviar_e_segmentar('graos')
    manual = Regiao.do_poligono([[1, 1], [30, 1], [30, 30]], origem=OrigemRegiao.MANUAL)
    imagem.regioes.append(manual)
    automaticas = len(imagem.regioes) - 1
    novo_job = JobSegmentacao(imagem=imagem, motor='classico', versao_motor='2.0')
    db.session.add(novo_job)
    db.session.commit()
    executar_job(novo_job.id)
    db.session.refresh(imagem)
    assert manual in imagem.regioes
    assert len([r for r in imagem.regioes if r.origem == OrigemRegiao.AUTOMATICA]) == automaticas


def test_fila_retoma_o_que_ficou_pela_metade(app):
    imagem = receber_foto(nova_coleta(), foto_de_graos(), 'b.png').imagem
    job = agendar_segmentacao(imagem)
    job.status = StatusJob.PROCESSANDO  # como se a plataforma tivesse fechado no meio
    db.session.commit()

    assert fila().retomar_pendentes() == 1
    db.session.refresh(job)
    assert job.status == StatusJob.CONCLUIDO
