"""Marcar na foto: janelas do SAM, escolha dos contornos, criar e excluir regiões, API e página."""
import io

import numpy as np
import pytest

from app.dominio import Anotacao, Coleta, OrigemRegiao, Regiao
from app.extensions import db
from app.segmentacao.toque import LADO_JANELA, Candidato, _escolher, janela_para
from app.servicos.anotacoes import anotar_regiao
from app.servicos.ingestao import receber_foto
from tests.conftest import TOKEN, classe, criar_pessoa, entrar_como, tipo
from tests.fabrica_imagens import centros_dos_graos, foto_de_graos, foto_jpeg


class MarcadorFalso:
    """Faz o papel do SAM nos testes: para qualquer toque, um quadrado pequeno e um grande."""

    def __init__(self):
        self.preparados = []

    def disponivel(self):
        return True

    def preparar(self, chave, obter_rgb, forma, x, y):
        self.preparados.append((round(x), round(y)))
        return janela_para(x, y, forma[1], forma[0])

    def candidatos(self, chave, obter_rgb, forma, x, y):
        x, y = round(x), round(y)
        return [Candidato([[x - 10, y - 10], [x + 10, y - 10], [x + 10, y + 10], [x - 10, y + 10]], 400, 0.7),
                Candidato([[x - 30, y - 30], [x + 30, y - 30], [x + 30, y + 30], [x - 30, y + 30]], 3600, 0.9)], 1


@pytest.fixture
def falso(app):
    app.extensions['marcador'] = MarcadorFalso()
    return app.extensions['marcador']


@pytest.fixture
def foto(app):
    coleta = Coleta(nome='Florada', tipo_amostra=tipo('flores'))
    db.session.add(coleta)
    db.session.flush()
    imagem = receber_foto(coleta, foto_jpeg(400, 300), 'planta.jpg', ja_segmentada=True).imagem
    db.session.commit()
    return imagem


def enviar(cliente, url, corpo):
    return cliente.post(url, json=corpo, headers={'X-CSRF': TOKEN})


# ----------------------------------------------------------------- janelas

def test_janela_em_foto_pequena_e_a_foto_inteira():
    assert janela_para(300, 200, 800, 600) == (0, 0, 800, 600)


@pytest.mark.parametrize('x, y', [(0, 0), (1500, 2000), (3023, 4031), (500, 3900)])
def test_janela_contem_o_toque_com_folga(x, y):
    x0, y0, x1, y1 = janela_para(x, y, 3024, 4032)
    assert x1 - x0 == LADO_JANELA and y1 - y0 == LADO_JANELA
    assert x0 <= x < x1 and y0 <= y < y1
    assert 0 <= x0 and x1 <= 3024 and y1 <= 4032
    if 256 < x < 3024 - 256:  # longe da borda da foto: longe da borda da janela
        assert min(x - x0, x1 - x) >= 128


def test_contornos_do_menor_para_o_maior_sem_repetidos_nem_gigantes():
    forma = (200, 200)
    def quadrado(lado):
        m = np.zeros(forma, bool)
        m[100 - lado:100 + lado, 100 - lado:100 + lado] = True
        return m
    mascaras = np.stack([quadrado(20), quadrado(8), quadrado(20), quadrado(99)])
    mascaras[1, 10:14, 10:14] = True  # pontinho solto: fica só o pedaço que contém o toque
    candidatos, melhor = _escolher(mascaras[:3], np.array([0.6, 0.8, 0.5]), (100, 100), (1000, 2000))
    assert [c.area_px for c in candidatos] == [256, 1600]  # o repetido (20) saiu
    assert candidatos[0].poligono[0][0] >= 1000  # na posição da foto, não da janela
    assert melhor == 0
    gigante, _ = _escolher(np.stack([quadrado(4), quadrado(60)]), np.array([0.5, 0.9]), (100, 100), (0, 0))
    assert [c.area_px for c in gigante] == [64]  # "tudo em volta" (mais de 50× o menor) sai


# --------------------------------------------------------------------- API

def test_sem_ia_a_pagina_avisa_e_o_toque_explica(logado, foto):
    dados = logado.get(f'/api/imagens/{foto.id}/marcacao').get_json()
    assert dados['toque_disponivel'] is False and 'Instalar IA.bat' in dados['aviso_sem_ia']
    resposta = enviar(logado, f'/api/imagens/{foto.id}/toque', {'x': 10, 'y': 10})
    assert resposta.status_code == 409 and 'Instalar IA.bat' in resposta.get_json()['erro']


def test_toque_propoe_contornos(logado, foto, falso):
    dados = enviar(logado, f'/api/imagens/{foto.id}/toque', {'x': 100, 'y': 80}).get_json()
    assert [c['area_px'] for c in dados['candidatos']] == [400, 3600] and dados['sugerido'] == 1
    assert enviar(logado, f'/api/imagens/{foto.id}/toque', {'x': 900, 'y': 80}).status_code == 422  # fora da foto
    assert enviar(logado, f'/api/imagens/{foto.id}/preparar', {'x': 200, 'y': 150}).get_json() == {'pronto': True}
    assert falso.preparados == [(200, 150)]


def test_criar_regiao_ja_anotada(logado, foto):
    poligono = [[10, 10], [60, 10], [60, 50], [10, 50]]
    resposta = enviar(logado, f'/api/imagens/{foto.id}/regioes',
                      {'poligono': poligono, 'classe': 'flor_aberta', 'duvida': True})
    assert resposta.status_code == 201
    dados = resposta.get_json()
    assert dados['regiao']['classe'] == 'flor_aberta' and dados['regiao']['duvida'] is True
    assert dados['progresso']['anotadas'] == 1
    regiao = db.session.get(Regiao, dados['regiao']['id'])
    assert regiao.origem == OrigemRegiao.MANUAL and regiao.motor == 'toque' and regiao.bbox == [10, 10, 50, 40]
    assert regiao.anotacao_vigente.pessoa.nome == 'Ana'


@pytest.mark.parametrize('corpo, mensagem', [
    ({'poligono': [[10, 10], [60, 10]]}, 'pelo menos 3 pontos'),
    ({'poligono': [[10, 10], [900, 10], [900, 50]]}, 'passa da borda'),
    ({'poligono': 'x'}, 'formato inválido'),
    ({'poligono': [[10, 10], [60, 10], [60, 50]], 'classe': 'sem_defeito'}, 'não existe'),  # classe de grãos
])
def test_regiao_invalida_nao_e_criada(logado, foto, corpo, mensagem):
    resposta = enviar(logado, f'/api/imagens/{foto.id}/regioes', corpo)
    assert resposta.status_code == 422 and mensagem in resposta.get_json()['erro']
    assert db.session.query(Regiao).count() == 0


def test_quem_pode_excluir_regiao(cliente, foto, administracao):
    ana, bia = criar_pessoa('Ana'), criar_pessoa('Bia')
    regiao = Regiao.do_poligono([[10, 10], [60, 10], [60, 50]], origem=OrigemRegiao.MANUAL)
    foto.regioes.append(regiao)
    db.session.flush()
    anotar_regiao(regiao, classe('flores', 'flor_aberta'), pessoa=bia)
    db.session.commit()

    entrar_como(cliente, ana)
    resposta = enviar(cliente, f'/api/regioes/{regiao.id}/excluir', {})
    assert resposta.status_code == 403 and 'Outra pessoa já anotou' in resposta.get_json()['erro']
    entrar_como(cliente, bia)  # quem anotou pode
    assert enviar(cliente, f'/api/regioes/{regiao.id}/excluir', {}).status_code == 200
    assert db.session.query(Anotacao).count() == 0  # as anotações vão junto


def test_administracao_exclui_qualquer_regiao(logado_admin, foto):
    regiao = Regiao.do_poligono([[10, 10], [60, 10], [60, 50]], origem=OrigemRegiao.AUTOMATICA)
    foto.regioes.append(regiao)
    db.session.flush()
    anotar_regiao(regiao, classe('flores', 'botao_floral'), pessoa=criar_pessoa('Outra'))
    db.session.commit()
    assert enviar(logado_admin, f'/api/regioes/{regiao.id}/excluir', {}).status_code == 200


def test_dados_da_marcacao_so_da_foto(logado, foto):
    outra = receber_foto(foto.coleta, foto_jpeg(cor=(9, 9, 9)), 'outra.jpg', ja_segmentada=True).imagem
    for imagem in (foto, outra):
        imagem.regioes.append(Regiao.do_poligono([[1, 1], [20, 1], [20, 20]], origem=OrigemRegiao.MANUAL))
    db.session.commit()
    dados = logado.get(f'/api/imagens/{foto.id}/marcacao').get_json()
    assert {r['imagem_id'] for r in dados['regioes']} == {foto.id}
    assert dados['fotos'] == {'posicao': 1, 'total': 2, 'anterior': None, 'proxima': outra.id}
    assert [c['codigo'] for c in dados['classes']][:2] == ['botao_floral', 'flor_aberta']


def test_api_de_marcacao_exige_login_e_csrf(cliente, logado, foto, administracao):
    assert logado.post(f'/api/imagens/{foto.id}/regioes', json={'poligono': []}).status_code == 400  # sem X-CSRF
    cliente.post('/sair', data={'_csrf': TOKEN})
    assert cliente.get(f'/api/imagens/{foto.id}/marcacao').status_code == 401


# ------------------------------------------------------------------ páginas

def test_pagina_marcar_e_caminhos_ate_ela(logado, foto):
    html = logado.get(f'/imagens/{foto.id}/marcar').get_data(as_text=True)
    assert 'Marcar na foto' in html and 'data-visor' in html
    coleta = logado.get(f'/coletas/{foto.coleta_id}').get_data(as_text=True)
    assert f'href="/imagens/{foto.id}/marcar"' in coleta
    anotar = logado.get(f'/coletas/{foto.coleta_id}/anotar').get_data(as_text=True)
    assert f'href="/imagens/{foto.id}/marcar"' in anotar  # coleta sem regiões: começa marcando


# -------------------------------------------------------- SAM de verdade (-m ia)

@pytest.mark.ia
def test_toque_de_verdade_contorna_o_grao(app):
    from pathlib import Path

    from app.config import PASTA_DADOS_PADRAO
    from app.segmentacao.toque import MarcadorPorToque
    marcador = MarcadorPorToque(lambda: Path(PASTA_DADOS_PADRAO) / 'modelos')
    if not marcador.disponivel():
        pytest.skip('IA não instalada neste computador ("Instalar IA.bat")')
    from PIL import Image
    rgb = np.array(Image.open(io.BytesIO(foto_de_graos(linhas=2, colunas=3))).convert('RGB'))
    x, y = centros_dos_graos(linhas=2, colunas=3)[0]
    candidatos, melhor = marcador.candidatos('teste', lambda: rgb, rgb.shape[:2], x, y)
    import cv2
    escolhido = candidatos[melhor]
    assert cv2.pointPolygonTest(np.array(escolhido.poligono, np.int32), (float(x), float(y)), False) >= 0
    assert 300 < escolhido.area_px < 20_000  # um grão, não o fundo
