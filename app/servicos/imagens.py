"""Leitura de fotos: validação, orientação, EXIF (data e GPS), miniaturas e recortes.

Orientação: fotos de celular costumam ser gravadas "deitadas", com uma marcação
EXIF dizendo como girar. O arquivo ORIGINAL é guardado sem alteração, mas todas
as coordenadas da plataforma (regiões, polígonos) valem para a foto JÁ GIRADA,
que é como o navegador e as pessoas a veem. Por isso tudo que lê pixels passa por
abrir_orientada().
"""
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError

# Formato detectado pelo conteúdo -> extensão gravada. (MPO = JPEG de alguns celulares.)
FORMATOS_ACEITOS = {'JPEG': 'jpg', 'MPO': 'jpg', 'PNG': 'png', 'WEBP': 'webp',
                    'BMP': 'bmp', 'TIFF': 'tiff'}
_ORIENTACOES_GIRADAS = {5, 6, 7, 8}  # EXIF: foto de pé gravada deitada
LADO_MINIATURA = 480


class FotoInvalida(ValueError):
    """O arquivo não pode ser usado. A mensagem é para a pessoa que enviou."""


@dataclass(frozen=True)
class MetadadosFoto:
    extensao: str
    largura: int     # já considerando a rotação
    altura: int
    capturada_em: datetime | None  # hora local da câmera (EXIF não diz o fuso)
    latitude: float | None
    longitude: float | None


def ler_metadados(conteudo: bytes) -> MetadadosFoto:
    try:
        Image.open(io.BytesIO(conteudo)).verify()  # confere se o arquivo não está corrompido
        imagem = Image.open(io.BytesIO(conteudo))
    except Image.DecompressionBombError as erro:
        raise FotoInvalida('A imagem é grande demais (mais de 170 milhões de pixels).') from erro
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as erro:
        raise FotoInvalida('O arquivo não é uma imagem ou está corrompido.') from erro

    if imagem.format not in FORMATOS_ACEITOS:
        raise FotoInvalida(f'Formato {imagem.format} não aceito. Envie JPG, PNG, WEBP, BMP ou TIFF.')

    exif = imagem.getexif()
    largura, altura = imagem.size
    if exif.get(ExifTags.Base.Orientation) in _ORIENTACOES_GIRADAS:
        largura, altura = altura, largura

    latitude, longitude = _gps(exif)
    return MetadadosFoto(
        extensao=FORMATOS_ACEITOS[imagem.format], largura=largura, altura=altura,
        capturada_em=_data_da_foto(exif), latitude=latitude, longitude=longitude,
    )


def _data_da_foto(exif) -> datetime | None:
    texto = (exif.get_ifd(ExifTags.IFD.Exif).get(ExifTags.Base.DateTimeOriginal)
             or exif.get(ExifTags.Base.DateTime))
    try:
        return datetime.strptime(str(texto).strip('\x00 '), '%Y:%m:%d %H:%M:%S') if texto else None
    except ValueError:
        return None  # data malformada: melhor sem data do que recusar a foto


def _gps(exif) -> tuple[float | None, float | None]:
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)

    def graus(valor, referencia) -> float | None:
        try:
            g, m, s = (float(parte) for parte in valor)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
        decimal = g + m / 60 + s / 3600
        return -decimal if str(referencia).upper() in ('S', 'W') else decimal

    latitude = graus(gps.get(ExifTags.GPS.GPSLatitude), gps.get(ExifTags.GPS.GPSLatitudeRef))
    longitude = graus(gps.get(ExifTags.GPS.GPSLongitude), gps.get(ExifTags.GPS.GPSLongitudeRef))
    if latitude is None or longitude is None or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None, None
    return round(latitude, 7), round(longitude, 7)


def abrir_orientada(origem: Path | bytes) -> Image.Image:
    """A foto girada como deve ser vista, em RGB (transparência sobre fundo branco)."""
    imagem = Image.open(io.BytesIO(origem) if isinstance(origem, bytes) else origem)
    imagem = ImageOps.exif_transpose(imagem)
    return _sem_transparencia(imagem)


def matriz_rgb(origem: Path | bytes) -> np.ndarray:
    """A foto orientada como matriz (altura × largura × 3), para os motores de segmentação."""
    return np.asarray(abrir_orientada(origem))


def gerar_miniatura(origem: Path | bytes, destino: Path, lado: int = LADO_MINIATURA) -> Path:
    """JPEG leve (lado maior = `lado` px) para listas e para o celular."""
    if destino.exists():
        return destino
    imagem = Image.open(io.BytesIO(origem) if isinstance(origem, bytes) else origem)
    imagem.draft('RGB', (lado * 2, lado * 2))  # JPEG: decodifica já reduzido (bem mais rápido)
    imagem = _sem_transparencia(ImageOps.exif_transpose(imagem))
    imagem.thumbnail((lado, lado))
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix('.parcial')
    imagem.save(temporario, 'JPEG', quality=82, optimize=True)
    temporario.replace(destino)
    return destino


def recortar(imagem_orientada: Image.Image, bbox: list[int], margem: int = 0) -> Image.Image:
    """Recorte retangular de uma região (bbox COCO: x, y, largura, altura), sem mexer nas cores."""
    x, y, largura, altura = bbox
    return imagem_orientada.crop((max(0, x - margem), max(0, y - margem),
                                  min(imagem_orientada.width, x + largura + margem),
                                  min(imagem_orientada.height, y + altura + margem)))


def _sem_transparencia(imagem: Image.Image) -> Image.Image:
    if imagem.mode in ('RGBA', 'LA') or (imagem.mode == 'P' and 'transparency' in imagem.info):
        imagem = imagem.convert('RGBA')
        fundo = Image.new('RGBA', imagem.size, (255, 255, 255, 255))
        return Image.alpha_composite(fundo, imagem).convert('RGB')
    return imagem.convert('RGB')
