"""Motor de IA (FastSAM + SAM 2.1): filtro das máscaras, escolha do motor, download dos
modelos e "segmentar de novo". Não precisa do PyTorch, exceto os testes marcados `ia`,
que rodam os modelos de verdade:  pytest -m ia  (precisa do "Instalar IA.bat")."""
import hashlib
import io
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.config import PASTA_DADOS_PADRAO
from app.dominio import JobSegmentacao, StatusJob
from app.extensions import db
from app.segmentacao import MOTORES, ia, primeiro_disponivel
from app.segmentacao.ia import (
    DownloadInvalido, MotorIA, MotorIndisponivel, ParametrosIA, baixar_modelos, filtrar_mascaras,
)
from app.servicos.ingestao import receber_foto
from app.servicos.segmentacao import agendar_segmentacao, executar_job, motor_antigo
from app.servicos.taxonomias import TaxonomiaInvalida, ler_taxonomias, sincronizar_taxonomias
from tests.conftest import TOKEN, criar_coleta, tipo
from tests.fabrica_imagens import centros_dos_graos, foto_de_graos

FORMA = (600, 800)


def elipse(cx, cy, eixos=(30, 20), angulo=0):
    mascara = np.zeros(FORMA, np.uint8)
    cv2.ellipse(mascara, (cx, cy), eixos, angulo, 0, 360, 1, -1)
    return mascara.astype(bool)


# ------------------------------------------------------------------ filtro

def test_filtro_deixa_uma_regiao_por_objeto():
    graos = [(elipse(80 + 110 * (i % 6), 100 + 150 * (i // 6)), 0.9) for i in range(12)]
    repetida = (elipse(82, 102), 0.5)                     # o mesmo grão, pontuação menor
    pote = (np.pad(np.ones((500, 700), bool), ((50, 50), (50, 50))), 0.95)  # engloba tudo
    pontinho = (elipse(700, 550, (3, 3)), 0.99)
    lua = elipse(400, 520, (40, 40)) & ~elipse(420, 520, (40, 40))  # forma de lua: não é grão
    regioes = filtrar_mascaras([*graos, repetida, pote, pontinho, (lua, 0.9)], FORMA, ParametrosIA())
    assert len(regioes) == 12
    # Ficaram as 12 originais (0,9): nem a repetida (0,5), nem o pote (0,95), nem o pontinho (0,99).
    assert {r.pontuacao for r in regioes} == {0.9}


def test_filtro_se_adapta_a_foto_de_perto():
    """Poucos grãos grandes (foto de perto) valem tanto quanto muitos pequenos."""
    grandes = [(elipse(150 + 250 * i, 300, (100, 70)), 0.9) for i in range(3)]
    assert len(filtrar_mascaras(grandes, FORMA, ParametrosIA())) == 3


def test_filtro_fica_com_o_maior_pedaco_da_mascara():
    mascara = elipse(200, 200) | elipse(500, 500, (4, 4))  # grão + pontinho solto
    regiao, = filtrar_mascaras([(mascara, 1.7)], FORMA, ParametrosIA())
    assert regiao.area_px == int(elipse(200, 200).sum())
    assert regiao.pontuacao == 1.0  # a nota dos modelos pode passar de 1; o banco aceita até 1


def test_filtro_sem_mascaras():
    assert filtrar_mascaras([], FORMA, ParametrosIA()) == []
    assert filtrar_mascaras([(np.zeros(FORMA, bool), 0.5)], FORMA, ParametrosIA()) == []


# ------------------------------------------------------- escolha do motor

def test_ia_indisponivel_sem_os_modelos(app):
    assert not MOTORES['ia'].disponivel()  # pasta de dados dos testes: sem modelos
    assert primeiro_disponivel(['ia', 'classico']) == 'classico'
    with pytest.raises(MotorIndisponivel, match='Instalar IA.bat'):
        MotorIA().segmentar(np.zeros((10, 10, 3), np.uint8))


def test_ia_disponivel_com_bibliotecas_e_modelos(app, monkeypatch):
    pasta = Path(app.config['PASTA_MODELOS'])
    pasta.mkdir(parents=True)
    for modelo in ia.MODELOS:
        (pasta / modelo.nome).write_bytes(b'')
    monkeypatch.setattr(MotorIA, 'bibliotecas_instaladas', staticmethod(lambda: True))
    assert MOTORES['ia'].disponivel() and primeiro_disponivel(['ia', 'classico']) == 'ia'
    monkeypatch.setattr(MotorIA, 'bibliotecas_instaladas', staticmethod(lambda: False))
    assert not MOTORES['ia'].disponivel()


def _yaml_graos(tmp_path, linha_motor):
    original = (Path(__file__).parent.parent / 'taxonomias' / 'graos.yaml').read_text(encoding='utf-8')
    linhas = [linha_motor if l.startswith('motor:') else l for l in original.splitlines()]
    (tmp_path / 'graos.yaml').write_text('\n'.join(linhas), encoding='utf-8')
    return tmp_path


def test_taxonomia_usa_o_primeiro_motor_instalado(app, tmp_path, monkeypatch):
    pasta = _yaml_graos(tmp_path, 'motor: [ia, classico]')
    sincronizar_taxonomias(ler_taxonomias(pasta))
    assert tipo('graos').motor_padrao == 'classico'  # IA não instalada nos testes
    monkeypatch.setattr(MotorIA, 'disponivel', lambda self: True)
    sincronizar_taxonomias(ler_taxonomias(pasta))
    assert tipo('graos').motor_padrao == 'ia'  # instalou a IA: na próxima abertura, passa a usar


def test_taxonomia_recusa_motor_inexistente_na_lista(tmp_path):
    with pytest.raises(TaxonomiaInvalida, match='motor "magico" não existe'):
        ler_taxonomias(_yaml_graos(tmp_path, 'motor: [magico, classico]'))


def test_cada_segmentacao_guarda_os_parametros_usados(app):
    coleta = criar_coleta(num_regioes=0)
    imagem = receber_foto(coleta, foto_de_graos(linhas=2, colunas=2), 'a.png').imagem
    job = agendar_segmentacao(imagem)
    db.session.commit()
    assert job.parametros['distancia_minima_picos'] == 20  # parâmetro do motor clássico
    assert MotorIA().parametros['detector'] == 'FastSAM-s'


# ------------------------------------------------------- segmentar de novo

def test_foto_de_motor_antigo_oferece_segmentar_de_novo(logado):
    coleta = criar_coleta(num_regioes=0)
    imagem = receber_foto(coleta, foto_de_graos(linhas=2, colunas=2), 'bandeja.png').imagem
    job = agendar_segmentacao(imagem)
    db.session.commit()
    executar_job(job.id)
    assert motor_antigo(imagem) is None  # segmentada pelo motor atual
    job.versao_motor = '2.0'              # como a foto real, feita pela versão antiga
    db.session.commit()
    assert motor_antigo(imagem) == 'classico'
    html = logado.get(f'/coletas/{coleta.id}').get_data(as_text=True)
    assert 'Segmentada com o motor clássico.' in html
    assert 'regiões atuais desta foto serão substituídas.' in html
    resposta = logado.post(f'/imagens/{imagem.id}/segmentar', data={'_csrf': TOKEN})
    assert resposta.status_code == 302
    db.session.expire_all()
    assert motor_antigo(imagem) is None


# ------------------------------------------------------------ download

def _modelos_falsos(monkeypatch, conteudos):
    falsos = tuple(ia.ArquivoDeModelo(nome, f'https://exemplo/{nome}', hashlib.sha256(dados).hexdigest(), 1)
                   for nome, dados in conteudos.items())
    monkeypatch.setattr(ia, 'MODELOS', falsos)


def test_baixa_confere_e_nao_baixa_de_novo(tmp_path, monkeypatch):
    conteudos = {'a.pt': b'pesos A' * 1000, 'b.pt': b'pesos B'}
    _modelos_falsos(monkeypatch, conteudos)
    abrir = lambda url, timeout: io.BytesIO(conteudos[url.rsplit('/', 1)[1]])  # noqa: E731
    mensagens = list(baixar_modelos(tmp_path, abrir))
    assert mensagens[-1] == 'b.pt: pronto.' and (tmp_path / 'a.pt').read_bytes() == conteudos['a.pt']
    assert list(baixar_modelos(tmp_path, abrir)) == ['a.pt: já estava baixado.', 'b.pt: já estava baixado.']


def test_download_corrompido_nao_fica_no_lugar(tmp_path, monkeypatch):
    _modelos_falsos(monkeypatch, {'a.pt': b'certo'})
    with pytest.raises(DownloadInvalido, match='hash não confere'):
        list(baixar_modelos(tmp_path, lambda url, timeout: io.BytesIO(b'errado')))
    assert list(tmp_path.iterdir()) == []  # nem o arquivo, nem o temporário


# -------------------------------------------------- modelos de verdade (-m ia)

@pytest.fixture
def ia_de_verdade(app):
    app.config['PASTA_MODELOS'] = PASTA_DADOS_PADRAO / 'modelos'
    if not MOTORES['ia'].disponivel():
        pytest.skip('IA não instalada neste computador ("Instalar IA.bat")')
    return MOTORES['ia']


@pytest.mark.ia
def test_ia_acha_os_graos_de_uma_foto(ia_de_verdade):
    from PIL import Image
    rgb = np.array(Image.open(io.BytesIO(foto_de_graos(linhas=4, colunas=6))).convert('RGB'))
    regioes = ia_de_verdade.segmentar(rgb)
    centros = centros_dos_graos(linhas=4, colunas=6)
    achados = sum(any(cv2.pointPolygonTest(np.array(r.poligono, np.int32), (float(x), float(y)), False) >= 0
                      for r in regioes) for x, y in centros)
    assert achados >= 22 and len(regioes) <= 26  # 24 grãos: quase todos, sem inventar


@pytest.mark.ia
def test_foto_enviada_e_segmentada_pela_ia(ia_de_verdade):
    tipo('graos').motor_padrao = 'ia'
    coleta = criar_coleta(num_regioes=0)
    imagem = receber_foto(coleta, foto_de_graos(linhas=2, colunas=3), 'bandeja.png').imagem
    job = agendar_segmentacao(imagem)
    db.session.commit()
    executar_job(job.id)
    db.session.refresh(job)
    assert job.status == StatusJob.CONCLUIDO and job.motor == 'ia' and job.parametros['nucleos'] == 3
    assert {r.motor for r in imagem.regioes} == {'ia'} and len(imagem.regioes) >= 5
