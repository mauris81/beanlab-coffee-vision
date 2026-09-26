"""Marcar com um toque: a pessoa toca num objeto e o SAM 2.1 desenha o contorno dele.

Para objetos pequenos numa foto grande (uma flor numa foto da planta inteira), o SAM
olha só uma JANELA da foto em resolução cheia ao redor do toque (1024 px, o tamanho que
ele usa por dentro), não a foto inteira reduzida: assim cada flor fica grande o bastante
para o contorno sair certo.

A análise de cada janela (a parte lenta, ~7 s neste PC) fica guardada na memória; os
toques seguintes na mesma parte da foto levam menos de meio segundo. A página pede para
preparar a parte que a pessoa está vendo antes mesmo do toque.

Precisa da IA instalada (os mesmos pesos do motor `ia`). Usa uma cópia própria do modelo,
separada da fila de segmentação: um toque não espera uma foto de 2 minutos terminar.
"""
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

import cv2
import numpy as np

LADO_JANELA = 1024     # px da foto original que o SAM vê de cada vez
PASSO_JANELA = 768     # janelas vizinhas se sobrepõem 256 px: o toque nunca cai colado na borda
JANELAS_GUARDADAS = 12  # ~16 MB cada
NUCLEOS = 3


@dataclass(frozen=True)
class Candidato:
    """Um contorno possível para o objeto tocado (o SAM dá até três: menor, médio, maior)."""
    poligono: list[list[int]]   # na foto original
    area_px: int
    pontuacao: float


def janela_para(x: float, y: float, largura: int, altura: int) -> tuple[int, int, int, int]:
    """A janela (x0, y0, x1, y1) cujo centro fica mais perto do ponto tocado."""
    def eixo(p, total):
        if total <= LADO_JANELA:
            return 0, total
        indice = round((p - LADO_JANELA / 2) / PASSO_JANELA)
        inicio = min(max(indice * PASSO_JANELA, 0), total - LADO_JANELA)
        return inicio, inicio + LADO_JANELA
    (x0, x1), (y0, y1) = eixo(x, largura), eixo(y, altura)
    return x0, y0, x1, y1


class MarcadorPorToque:
    def __init__(self, pasta_dos_modelos: Callable):
        self._pasta = pasta_dos_modelos
        self._modelo = None
        self._janelas: OrderedDict = OrderedDict()   # (chave, x0, y0) -> preditor com a janela analisada
        self._foto: tuple | None = None              # (chave, rgb) da última foto aberta
        self._trava = threading.Lock()

    def disponivel(self) -> bool:
        from app.segmentacao.ia import MotorIA
        return MotorIA.bibliotecas_instaladas() and (self._pasta() / 'sam2.1_hiera_tiny.pt').is_file()

    def preparar(self, chave: str, obter_rgb: Callable[[], np.ndarray], forma: tuple[int, int],
                 x: float, y: float) -> tuple[int, int, int, int]:
        """Analisa (e guarda) a janela ao redor de (x, y). Devolve a janela."""
        with self._trava:
            return self._janela(chave, obter_rgb, forma, x, y)[0]

    def candidatos(self, chave: str, obter_rgb: Callable[[], np.ndarray], forma: tuple[int, int],
                   x: float, y: float) -> tuple[list[Candidato], int]:
        """Contornos possíveis para o objeto em (x, y), do menor para o maior, e qual deles
        o modelo acha melhor (índice). Lista vazia: nada reconhecível ali."""
        import torch
        with self._trava:
            (x0, y0, x1, y1), preditor = self._janela(chave, obter_rgb, forma, x, y)
            with torch.inference_mode():
                mascaras, notas, _ = preditor.predict(point_coords=np.array([[x - x0, y - y0]], np.float32),
                                                      point_labels=np.array([1]), multimask_output=True)
        return _escolher(mascaras > 0, notas, (x - x0, y - y0), (x0, y0))

    # ----------------------------------------------------------- por dentro

    def _janela(self, chave, obter_rgb, forma, x, y):
        altura, largura = forma
        janela = janela_para(x, y, largura, altura)
        indice = (chave, janela[0], janela[1])
        if indice in self._janelas:
            self._janelas.move_to_end(indice)
            return janela, self._janelas[indice]
        import torch
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        torch.set_num_threads(NUCLEOS)
        if self._foto is None or self._foto[0] != chave:
            self._foto = (chave, obter_rgb())
        x0, y0, x1, y1 = janela
        preditor = SAM2ImagePredictor(self._carregar_modelo())
        with torch.inference_mode():
            preditor.set_image(np.ascontiguousarray(self._foto[1][y0:y1, x0:x1]))
        self._janelas[indice] = preditor
        while len(self._janelas) > JANELAS_GUARDADAS:
            self._janelas.popitem(last=False)
        return janela, preditor

    def _carregar_modelo(self):
        if self._modelo is None:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', FutureWarning)
                warnings.simplefilter('ignore', UserWarning)
                from sam2.build_sam import build_sam2
                self._modelo = build_sam2('configs/sam2.1/sam2.1_hiera_t.yaml',
                                          str(self._pasta() / 'sam2.1_hiera_tiny.pt'), device='cpu')
        return self._modelo


def _escolher(mascaras: np.ndarray, notas, ponto, origem) -> tuple[list[Candidato], int]:
    """De cada máscara, o pedaço que contém o toque; sem repetidas; do menor para o maior."""
    px, py = min(int(ponto[0]), mascaras.shape[2] - 1), min(int(ponto[1]), mascaras.shape[1] - 1)
    achados = []
    for mascara, nota in zip(mascaras, np.ravel(notas)):
        quantos, rotulos, estatisticas, _ = cv2.connectedComponentsWithStats(mascara.astype(np.uint8), connectivity=8)
        if quantos < 2:
            continue
        rotulo = rotulos[py, px] or 1 + int(np.argmax(estatisticas[1:, cv2.CC_STAT_AREA]))
        pedaco = rotulos == rotulo
        area = int(estatisticas[rotulo, cv2.CC_STAT_AREA])
        if area < 30 or area > 0.6 * mascara.size:  # pontinho, ou "a foto inteira"
            continue
        if any((pedaco & outro).sum() > 0.9 * max(area, a) for _, a, outro in achados):
            continue  # praticamente igual a um contorno já achado
        achados.append((float(nota), area, pedaco))
    achados.sort(key=lambda a: a[1])
    if achados:  # "o pote inteiro" em volta de um grão não é opção útil
        achados = [a for a in achados if a[1] <= 50 * achados[0][1]]
    candidatos = []
    for nota, area, pedaco in achados:
        contornos, _ = cv2.findContours(pedaco.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contorno = max(contornos, key=cv2.contourArea)
        poligono = (cv2.approxPolyDP(contorno, 1.0, True).reshape(-1, 2) + origem).astype(int).tolist()
        if len(poligono) >= 3:
            candidatos.append(Candidato(poligono, area, round(min(max(nota, 0.0), 1.0), 4)))
    melhor = max(range(len(candidatos)), key=lambda i: candidatos[i].pontuacao) if candidatos else -1
    return candidatos, melhor
