"""O que todo motor de segmentação recebe e devolve.

Um motor recebe a foto como matriz RGB (altura × largura × 3, já na orientação
correta, ver app/servicos/imagens.py) e devolve uma lista de RegiaoEncontrada.
As coordenadas são pixels dessa mesma matriz. Quem grava no banco é o serviço de
segmentação: o motor só sabe de imagem, não de banco.
"""
from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class RegiaoEncontrada:
    poligono: list[list[int]]       # contorno [[x, y], ...]
    area_px: int                    # pixels do objeto (contagem exata da máscara)
    pontuacao: float | None = None  # confiança do motor (0 a 1), se ele tiver


class Segmentador(Protocol):
    nome: str     # gravado em Regiao.motor, ex.: 'classico'
    versao: str   # gravado em Regiao.versao_motor; mude quando o resultado mudar

    def segmentar(self, rgb: np.ndarray) -> list[RegiaoEncontrada]: ...
