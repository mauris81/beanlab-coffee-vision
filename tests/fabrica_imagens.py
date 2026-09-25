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


def bandeja_de_graos(semente=7, quantidade=60) -> bytes:
    """Foto sintética de grãos escuros numa bandeja bege sobre fundo azul (PNG)."""
    rng = np.random.default_rng(semente)
    bgr = np.full((700, 900, 3), (200, 120, 40), np.uint8)
    cv2.rectangle(bgr, (60, 60), (840, 640), (150, 195, 225), -1)
    for _ in range(quantidade):
        centro = (int(rng.integers(100, 800)), int(rng.integers(100, 600)))
        eixos = (int(rng.integers(16, 24)), int(rng.integers(10, 15)))
        cor = tuple(int(v) for v in rng.integers(25, 80, 3))
        cv2.ellipse(bgr, centro, eixos, float(rng.integers(0, 180)), 0, 360, cor, -1)
    bgr = np.clip(bgr + rng.normal(0, 5, bgr.shape), 0, 255).astype(np.uint8)
    return cv2.imencode('.png', bgr)[1].tobytes()


def coco(imagens: list[tuple[int, str]], anotacoes: list[dict], categorias: dict[int, str]) -> bytes:
    return json.dumps({
        'images': [{'id': i, 'file_name': nome, 'width': 400, 'height': 300} for i, nome in imagens],
        'annotations': anotacoes,
        'categories': [{'id': i, 'name': nome} for i, nome in categorias.items()],
    }).encode()
