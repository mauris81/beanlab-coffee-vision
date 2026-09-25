"""Motor clássico (watershed) para grãos sobre fundo uniforme.

Mesmo algoritmo do sistema antigo, reorganizado e corrigido:
- (2.1) considera TODOS os grupos com cor de grão, não só o maior: o antigo achava
  1 de 48 grãos quando eles estavam espalhados (só funcionava com grãos encostados);
- devolve CONTORNOS (polígonos), não recortes retangulares;
- a área é a contagem real de pixels do grão, não largura × altura da caixa;
- trabalha só em RGB, sem conversões que trocavam vermelho e azul;
- procura cada grão só dentro da sua caixa (muito mais rápido em fotos grandes).

Requisito da foto: FUNDO AZUL (ou de outra cor fria). Branco, cinza e bege contam
como "cor de grão" (matiz baixa) e confundem o motor.

Etapas: (1) acha as áreas com cor de grão (matiz baixa); (2) separa grãos do fundo
com limiar adaptativo; (3) separa grãos encostados com watershed sobre a
transformada de distância; (4) descarta regiões de tamanho muito fora do padrão.
"""
from dataclasses import dataclass

import cv2
import numpy as np
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.segmentation import watershed

from app.segmentacao.base import RegiaoEncontrada


@dataclass(frozen=True)
class ParametrosClassico:
    matiz_maxima_roi: int = 60        # matiz (0-179) até onde a cor conta como área de interesse
    area_minima_grupo: int = 150      # px: grupos com cor de grão menores que isso são ruído
    somente_maior_grupo: bool = False # True = comportamento antigo (só o maior grupo de grãos encostados)
    distancia_minima_picos: int = 20  # px entre centros de grãos vizinhos
    area_minima_ruido: int = 100      # px: manchas menores são ruído
    limiar_buracos: int = 1000        # px: buracos menores dentro do grão são preenchidos
    tolerancia_contorno: float = 1.0  # px: simplificação do polígono
    filtrar_por_iqr: bool = True      # descarta tamanhos muito fora do padrão (quartis)


class MotorClassico:
    nome = 'classico'
    versao = '2.1'
    dica_foto = ('Fotografe os grãos sobre um fundo AZUL (pano, papel ou EVA), com luz uniforme e '
                 'sem sombras fortes. Podem estar encostados ou separados; evite grãos empilhados.')

    def __init__(self, parametros: ParametrosClassico | None = None):
        self.p = parametros or ParametrosClassico()

    # ------------------------------------------------------------ interface

    def segmentar(self, rgb: np.ndarray) -> list[RegiaoEncontrada]:
        rotulos = self.rotular(rgb)
        regioes = []
        for indice, caixa in enumerate(ndi.find_objects(rotulos), start=1):
            if caixa is None:
                continue
            mascara = (rotulos[caixa] == indice).astype(np.uint8)
            contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contornos:
                continue
            contorno = cv2.approxPolyDP(max(contornos, key=cv2.contourArea),
                                        self.p.tolerancia_contorno, True)
            deslocamento = np.array([caixa[1].start, caixa[0].start])  # (x, y) da caixa
            pontos = (contorno.reshape(-1, 2) + deslocamento).tolist()
            if len(pontos) >= 3:
                regioes.append(RegiaoEncontrada(pontos, int(mascara.sum())))
        return self._filtrar_por_tamanho(regioes) if self.p.filtrar_por_iqr else regioes

    # --------------------------------------------------------------- etapas

    def rotular(self, rgb: np.ndarray) -> np.ndarray:
        """Matriz do tamanho da foto: 0 = fundo, 1..N = cada grão."""
        area_interesse = self._area_de_interesse(rgb)

        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        brilho = hsv[:, :, 2].astype(np.float32)
        cinza = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
        realce = cv2.normalize(brilho + cinza, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        realce = cv2.GaussianBlur(realce, (5, 9), sigmaX=2)

        limiar = cv2.adaptiveThreshold(realce, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
        graos = self._limpar_e_preencher(limiar, area_interesse)

        distancia = ndi.distance_transform_edt(graos)
        picos = peak_local_max(distancia, min_distance=self.p.distancia_minima_picos, labels=graos)
        marcadores = np.zeros_like(distancia, dtype=bool)
        marcadores[tuple(picos.T)] = True
        marcadores = ndi.label(marcadores, structure=np.ones((3, 3)))[0]
        return watershed(-distancia, marcadores, mask=graos)

    def _area_de_interesse(self, rgb: np.ndarray) -> np.ndarray:
        """Pixels com cor de grão (matiz até `matiz_maxima_roi`), sem manchas pequenas."""
        matiz = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[:, :, 0]
        mascara = np.uint8(matiz <= self.p.matiz_maxima_roi) * 255
        n, rotulos, stats, _ = cv2.connectedComponentsWithStats(mascara, connectivity=8)
        if n <= 1:
            return mascara
        areas = stats[1:, cv2.CC_STAT_AREA]
        if self.p.somente_maior_grupo:
            manter = [1 + int(np.argmax(areas))]
        else:
            manter = [1 + i for i, area in enumerate(areas) if area >= self.p.area_minima_grupo]
        return np.where(np.isin(rotulos, manter), 255, 0).astype(np.uint8)

    def _limpar_e_preencher(self, limiar: np.ndarray, area_interesse: np.ndarray) -> np.ndarray:
        """Remove ruído (manchas pequenas e alongadas) e fecha buracos dentro dos grãos."""
        invertido = cv2.bitwise_not(limiar)
        nucleo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        invertido = cv2.morphologyEx(invertido, cv2.MORPH_OPEN, nucleo)

        n, rotulos, stats, _ = cv2.connectedComponentsWithStats(invertido, connectivity=8)
        bordas = np.zeros_like(invertido)
        for i in range(1, n):
            largura, altura = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
            proporcao = max(largura, altura) / (min(largura, altura) + 1e-5)
            if stats[i, cv2.CC_STAT_AREA] > self.p.area_minima_ruido and proporcao < 2:
                bordas[rotulos == i] = 255

        bordas = cv2.dilate(bordas, nucleo, iterations=1)
        graos = cv2.bitwise_and(area_interesse, area_interesse, mask=cv2.bitwise_not(bordas))

        contornos, _ = cv2.findContours(graos, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        for contorno in contornos:
            if cv2.contourArea(contorno) < self.p.limiar_buracos:
                cv2.drawContours(graos, [contorno], -1, 255, -1)
        return graos

    @staticmethod
    def _filtrar_por_tamanho(regioes: list[RegiaoEncontrada]) -> list[RegiaoEncontrada]:
        """Descarta áreas fora de [Q1 - 1,5·IQR, Q3 + 1,5·IQR] (fundo, grãos colados demais)."""
        if len(regioes) < 4:
            return regioes
        areas = np.array([r.area_px for r in regioes])
        q1, q3 = np.percentile(areas, [25, 75])
        minimo, maximo = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        return [r for r in regioes if minimo <= r.area_px <= maximo]
