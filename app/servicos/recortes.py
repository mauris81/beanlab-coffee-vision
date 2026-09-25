"""Recortes das regiões e versão média das fotos, para a tela de anotação.

Os arquivos são derivados (podem ser apagados e refeitos a qualquer momento) e ficam
em cache no disco, ao lado da foto original. O nome do recorte vem da geometria da
região, então editar um contorno gera um recorte novo sem precisar limpar nada.
"""
from pathlib import Path

from PIL import Image

from app.armazenamento import armazenamento_de_imagens
from app.dominio import Imagem, Regiao
from app.servicos.imagens import abrir_orientada, gerar_miniatura, salvar_jpeg, trava

LADO_RECORTE = 320      # px do lado maior do recorte (objetos pequenos são ampliados)
LADO_MEDIA = 1600       # px do lado maior da foto na visão geral
MARGEM = 0.25           # contexto em volta do objeto: 25% do lado maior, de cada lado
MARGEM_MINIMA = 6       # px


def caixa_com_margem(bbox: list[int], largura: int, altura: int) -> tuple[int, int, int, int]:
    """(esquerda, topo, direita, base) da região com um pouco de contexto em volta."""
    x, y, w, h = bbox
    margem = max(MARGEM_MINIMA, round(MARGEM * max(w, h)))
    return (max(0, x - margem), max(0, y - margem),
            min(largura, x + w + margem), min(altura, y + h + margem))


def caminho_do_recorte(regiao: Regiao) -> Path:
    x, y, w, h = regiao.bbox
    pasta = armazenamento_de_imagens().pasta_recortes(regiao.imagem.hash_sha256)
    return pasta / f'{x}_{y}_{w}_{h}_{LADO_RECORTE}.jpg'


def garantir_recortes(imagem: Imagem) -> None:
    """Gera, de uma vez, os recortes que faltam desta foto (abre a foto uma vez só).

    A tela em lote pede dezenas de recortes ao mesmo tempo: a trava faz um pedido gerar
    todos e os outros só esperarem, em vez de cada um abrir a foto e gravar por cima.
    """
    with trava(f'recortes:{imagem.hash_sha256}'):
        faltando = [r for r in imagem.regioes if not caminho_do_recorte(r).is_file()]
        if not faltando:
            return
        armazenamento = armazenamento_de_imagens()
        foto = abrir_orientada(armazenamento.caminho(imagem.hash_sha256, imagem.extensao))
        for regiao in faltando:
            pedaco = foto.crop(caixa_com_margem(regiao.bbox, foto.width, foto.height))
            escala = LADO_RECORTE / max(pedaco.size)
            pedaco = pedaco.resize((max(1, round(pedaco.width * escala)), max(1, round(pedaco.height * escala))),
                                   Image.Resampling.LANCZOS)
            salvar_jpeg(pedaco, caminho_do_recorte(regiao), quality=88)


def recorte_da_regiao(regiao: Regiao) -> Path:
    caminho = caminho_do_recorte(regiao)
    if not caminho.is_file():
        garantir_recortes(regiao.imagem)
    return caminho


def media_da_imagem(imagem: Imagem) -> Path:
    armazenamento = armazenamento_de_imagens()
    return gerar_miniatura(armazenamento.caminho(imagem.hash_sha256, imagem.extensao),
                           armazenamento.caminho_media(imagem.hash_sha256), lado=LADO_MEDIA)
