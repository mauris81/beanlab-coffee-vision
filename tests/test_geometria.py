"""Cálculos sobre o contorno das regiões."""
import pytest

from app.dominio import OrigemRegiao, Regiao
from app.dominio.geometria import (
    PoligonoInvalido, area_do_poligono, bbox_do_poligono, validar_poligono,
)

QUADRADO = [[10, 20], [110, 20], [110, 120], [10, 120]]


def test_area_e_bbox_de_um_quadrado():
    assert area_do_poligono(QUADRADO) == 10_000
    assert bbox_do_poligono(QUADRADO) == (10, 20, 100, 100)


def test_area_de_um_triangulo_nao_e_a_da_caixa():
    """Regressão: antes a 'área' era largura × altura da caixa."""
    triangulo = [[0, 0], [100, 0], [0, 100]]
    assert area_do_poligono(triangulo) == 5_000
    x, y, largura, altura = bbox_do_poligono(triangulo)
    assert largura * altura == 10_000


def test_regiao_calcula_bbox_e_area_sozinha():
    regiao = Regiao.do_poligono(QUADRADO, origem=OrigemRegiao.MANUAL)
    assert regiao.bbox == [10, 20, 100, 100]
    assert regiao.area_px == 10_000


def test_regiao_aceita_area_exata_informada_pelo_motor():
    regiao = Regiao.do_poligono(QUADRADO, origem=OrigemRegiao.AUTOMATICA, area_px=9_876)
    assert regiao.area_px == 9_876


def test_coordenadas_decimais_sao_arredondadas():
    assert validar_poligono([[0.4, 0.6], [10.5, 0], [10, 9.6]]) == [[0, 1], [10, 0], [10, 10]]


@pytest.mark.parametrize('pontos, mensagem', [
    ([[0, 0], [1, 1]], 'pelo menos 3 pontos'),
    ([[0, 0], [5, 5], [10, 10]], 'não tem área'),
    ([[0, 0], [-5, 0], [0, 5]], 'negativa'),
    (['abc'], 'lista de pontos'),
    (None, 'lista de pontos'),
])
def test_contornos_invalidos(pontos, mensagem):
    with pytest.raises(PoligonoInvalido, match=mensagem):
        validar_poligono(pontos)
