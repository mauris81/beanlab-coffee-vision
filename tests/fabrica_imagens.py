"""Imagens geradas na hora para os testes (nada de arquivos binários no repositório)."""
import io
import json

import cv2
import numpy as np
from PIL import ExifTags, Image


def foto_jpeg(largura=400, altura=300, cor=(120, 90, 60), orientacao=None, data=None,
              gps=None) -> bytes:
    """JPEG com EXIF opcional. gps = (lat, lon) em graus decimais."""
    imagem = Image.new('RGB', (largura, altura), cor)
    exif = Image.Exif()
    if orientacao:
        exif[ExifTags.Base.Orientation] = orientacao
    if data:
        exif.get_ifd(ExifTags.IFD.Exif)[ExifTags.Base.DateTimeOriginal] = data
    if gps:
        def dms(valor):
            valor = abs(valor)
            graus = int(valor)
            minutos = int((valor - graus) * 60)
            segundos = round(((valor - graus) * 60 - minutos) * 60, 4)
            return (float(graus), float(minutos), float(segundos))
        lat, lon = gps
        exif.get_ifd(ExifTags.IFD.GPSInfo).update({
            ExifTags.GPS.GPSLatitudeRef: 'S' if lat < 0 else 'N', ExifTags.GPS.GPSLatitude: dms(lat),
            ExifTags.GPS.GPSLongitudeRef: 'W' if lon < 0 else 'E', ExifTags.GPS.GPSLongitude: dms(lon),
        })
    saida = io.BytesIO()
    imagem.save(saida, 'JPEG', exif=exif, quality=90)
    return saida.getvalue()


def png(largura=200, altura=150, cor=(10, 200, 30), transparente=False) -> bytes:
    """PNG liso. Com transparente=True: círculo opaco no centro, resto transparente."""
    if transparente:
        imagem = Image.new('RGBA', (largura, altura), (0, 0, 0, 0))
        matriz = np.array(imagem)
        cv2.circle(matriz, (largura // 2, altura // 2), min(largura, altura) // 3, (*cor, 255), -1)
        imagem = Image.fromarray(matriz, 'RGBA')
    else:
        imagem = Image.new('RGB', (largura, altura), cor)
    saida = io.BytesIO()
    imagem.save(saida, 'PNG')
    return saida.getvalue()


def foto_de_graos(semente=7, linhas=6, colunas=8, espacamento='separados', formato='png') -> bytes:
    """Foto sintética no cenário do motor clássico: grãos marrons sobre FUNDO AZUL.

    espacamento: 'separados' (há fundo entre os grãos) ou 'encostados' (camada contínua).
    Os centros dos grãos ficam em centros_dos_graos(...) para os testes conferirem.
    """
    return _codificar(_desenhar_graos(semente, linhas, colunas, espacamento)[0], formato)


def centros_dos_graos(semente=7, linhas=6, colunas=8, espacamento='separados') -> list[tuple[int, int]]:
    return _desenhar_graos(semente, linhas, colunas, espacamento)[1]


def _desenhar_graos(semente, linhas, colunas, espacamento):
    rng = np.random.default_rng(semente)
    passo = (80, 60) if espacamento == 'separados' else (56, 40)
    eixos = (30, 21)
    bgr = np.full((linhas * passo[1] + 120, colunas * passo[0] + 120, 3), (190, 110, 30), np.uint8)
    centros = []
    for i in range(linhas):
        for j in range(colunas):
            centro = (60 + j * passo[0] + passo[0] // 2 + int(rng.integers(-4, 5)),
                      60 + i * passo[1] + passo[1] // 2 + int(rng.integers(-4, 5)))
            cor = (int(rng.integers(50, 80)), int(rng.integers(95, 125)), int(rng.integers(140, 170)))
            angulo = float(rng.integers(-15, 15))
            cv2.ellipse(bgr, centro, eixos, angulo, 0, 360, cor, -1)
            cv2.ellipse(bgr, centro, eixos, angulo, 0, 360, (30, 45, 60), 2)
            centros.append(centro)
    bgr = np.clip(bgr + rng.normal(0, 4, bgr.shape), 0, 255).astype(np.uint8)
    return bgr, centros


def _codificar(bgr, formato):
    return cv2.imencode('.png' if formato == 'png' else '.jpg', bgr)[1].tobytes()


def coco(imagens: list[tuple[int, str]], anotacoes: list[dict], categorias: dict[int, str]) -> bytes:
    return json.dumps({
        'images': [{'id': i, 'file_name': nome, 'width': 400, 'height': 300} for i, nome in imagens],
        'annotations': anotacoes,
        'categories': [{'id': i, 'name': nome} for i, nome in categorias.items()],
    }).encode()
