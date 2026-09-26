"""Motor de IA (Fase 6): o FastSAM encontra os objetos e o SAM 2.1 desenha o contorno de cada um.

Por que dois modelos (testado na foto real de grãos; números na decisão 0009):
- FastSAM-s acha quase todos os grãos, e rápido, mas o contorno sai "quadrado";
- SAM 2.1-tiny desenha contornos precisos, mas sozinho perde grãos e é muito lento;
- juntos: o FastSAM dá a caixa de cada objeto e o SAM contorna o que está dentro dela.

OPCIONAL: precisa do "Instalar IA.bat" (PyTorch, Ultralytics e SAM 2; ~1 GB) e dos pesos
dos modelos em <pasta de dados>/modelos (o mesmo atalho baixa e confere o hash).
Sem isso, disponivel() é False e o tipo de amostra usa o motor seguinte da lista do
YAML (ex.: grãos: `motor: [ia, classico]`).

Licenças: FastSAM/Ultralytics AGPL-3.0 (por isso o projeto é AGPL); SAM 2.1 Apache-2.0.
Nada vai para a internet durante o uso: as estatísticas do Ultralytics ficam desligadas.
"""
import hashlib
import importlib.util
import os
import tempfile
import threading
import urllib.request
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

from app.segmentacao.base import RegiaoEncontrada

BIBLIOTECAS = ('torch', 'ultralytics', 'sam2')


@dataclass(frozen=True)
class ArquivoDeModelo:
    nome: str
    url: str
    sha256: str      # conferido depois de baixar: arquivo corrompido ou trocado não é usado
    tamanho_mb: int


MODELOS = (
    ArquivoDeModelo('FastSAM-s.pt',
                    'https://github.com/ultralytics/assets/releases/download/v8.4.0/FastSAM-s.pt',
                    'c9f78716a81c7aff0d608ccc73e1b82ab3aaad86005049f6a92106a0be6d0844', 23),
    ArquivoDeModelo('sam2.1_hiera_tiny.pt',
                    'https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt',
                    '7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69', 156),
)


@dataclass(frozen=True)
class ParametrosIA:
    # Os modelos trabalham numa cópia com este lado maior (o SAM reduz para 1024 por dentro
    # de qualquer jeito). Uma foto de celular de 12 MP no tamanho original gastaria vários GB
    # de memória por lote. Os contornos voltam para a resolução original no fim.
    lado_de_trabalho: int = 1600
    tamanho_deteccao: int = 1600       # px: o FastSAM vê a foto neste tamanho (grão pequeno pede mais)
    confianca_minima: float = 0.25     # FastSAM: abaixo disso, não é objeto
    iou_repeticao: float = 0.7         # FastSAM: caixas mais sobrepostas que isso são a mesma
    maximo_objetos: int = 2000
    # Tamanho: numa mesma foto os objetos têm tamanhos parecidos, então vale o tamanho em
    # relação à mediana dos objetos encontrados (funciona de longe e de perto). Na foto real
    # de grãos, dá o mesmo resultado que limites fixos calibrados à mão (decisão 0009).
    faixa_relativa: tuple[float, float] = (0.25, 4.0)  # × a área mediana
    # Limites de segurança, em proporção da foto: pontinhos e o pote nunca entram.
    area_minima: float = 0.00002
    area_maxima: float = 0.25
    solidez_minima: float = 0.75       # objeto quase convexo; mancha do fundo não é
    sobreposicao_maxima: float = 0.25  # cobre um objeto já aceito? é repetição
    lote_contornos: int = 64           # caixas por rodada do SAM (mais = mais memória)
    tolerancia_contorno: float = 1.0   # px: simplificação do polígono
    nucleos: int = 3                   # de 4: deixa um livre para a plataforma responder


def pasta_dos_modelos() -> Path:
    from flask import current_app
    return Path(current_app.config['PASTA_MODELOS'])


class MotorIndisponivel(RuntimeError):
    """A IA não está instalada neste computador (bibliotecas ou pesos faltando)."""


class MotorIA:
    nome = 'ia'
    versao = '1.0'  # FastSAM-s + SAM 2.1-tiny com os ParametrosIA padrão; mude se mudar o resultado
    dica_foto = ('Fotografe de cima, com o pote ou a bandeja inteira no quadro e luz boa, sem sombras '
                 'fortes. Qualquer fundo serve e os grãos podem estar encostados; só evite grãos '
                 'empilhados uns sobre os outros. A segmentação leva cerca de 1 a 2 minutos por foto.')

    def __init__(self, parametros: ParametrosIA | None = None):
        self.p = parametros or ParametrosIA()
        self._modelos = None
        self._trava = threading.Lock()

    @property
    def parametros(self) -> dict:
        return {'detector': 'FastSAM-s', 'contorno': 'SAM 2.1 hiera-tiny', **asdict(self.p)}

    @staticmethod
    def bibliotecas_instaladas() -> bool:
        return all(importlib.util.find_spec(nome) is not None for nome in BIBLIOTECAS)

    def disponivel(self) -> bool:
        return self.bibliotecas_instaladas() and all((pasta_dos_modelos() / m.nome).is_file() for m in MODELOS)

    # ------------------------------------------------------------ segmentar

    def segmentar(self, rgb: np.ndarray) -> list[RegiaoEncontrada]:
        detector, contornador = self._carregar()
        import torch
        torch.set_num_threads(self.p.nucleos)
        escala = min(1.0, self.p.lado_de_trabalho / max(rgb.shape[:2]))
        trabalho = rgb if escala == 1 else cv2.resize(rgb, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
        bgr = np.ascontiguousarray(trabalho[..., ::-1])  # o Ultralytics espera a ordem do OpenCV
        deteccao = detector(bgr, device='cpu', imgsz=self.p.tamanho_deteccao, conf=self.p.confianca_minima,
                            iou=self.p.iou_repeticao, max_det=self.p.maximo_objetos, verbose=False)[0]
        if deteccao.boxes is None or not len(deteccao.boxes):
            return []
        caixas, confiancas = deteccao.boxes.xyxy.numpy(), deteccao.boxes.conf.numpy()

        forma = trabalho.shape[:2]
        candidatas = []  # já recortadas: a máscara da foto inteira é descartada logo (memória)
        with torch.inference_mode():
            contornador.set_image(trabalho)
            for inicio in range(0, len(caixas), self.p.lote_contornos):
                lote = slice(inicio, inicio + self.p.lote_contornos)
                mascaras, notas, _ = contornador.predict(box=caixas[lote], multimask_output=False)
                if mascaras.ndim == 4:
                    mascaras = mascaras[:, 0]
                for mascara, confianca, nota in zip(mascaras, confiancas[lote], np.ravel(notas)):
                    if (candidata := preparar_mascara(mascara > 0, float(confianca * nota), forma, self.p)):
                        candidatas.append(candidata)
        regioes = escolher_regioes(candidatas, forma, self.p)
        return regioes if escala == 1 else [_na_escala_original(r, escala, rgb.shape[:2]) for r in regioes]

    def _carregar(self):
        """Carrega os modelos uma vez por processo (~0,5 GB de memória) e reaproveita."""
        with self._trava:
            if self._modelos is None:
                if not self.disponivel():
                    raise MotorIndisponivel('A segmentação com IA não está instalada neste computador. '
                                            'Rode "Instalar IA.bat" (ou use o motor clássico).')
                os.environ.setdefault('YOLO_OFFLINE', '1')  # sem checagens na internet
                with warnings.catch_warnings():  # avisos técnicos das bibliotecas, não da plataforma
                    warnings.simplefilter('ignore', FutureWarning)
                    warnings.simplefilter('ignore', UserWarning)
                    from sam2.build_sam import build_sam2
                    from sam2.sam2_image_predictor import SAM2ImagePredictor
                    from ultralytics import FastSAM, settings
                    settings.update({'sync': False})  # sem estatísticas de uso
                    pasta = pasta_dos_modelos()
                    detector = FastSAM(str(pasta / 'FastSAM-s.pt'))
                    contornador = SAM2ImagePredictor(build_sam2(
                        'configs/sam2.1/sam2.1_hiera_t.yaml', str(pasta / 'sam2.1_hiera_tiny.pt'), device='cpu'))
                self._modelos = (detector, contornador)
        return self._modelos


# ------------------------------------------------------------------ filtro

def filtrar_mascaras(candidatas: list[tuple[np.ndarray, float]], forma: tuple[int, int],
                     p: ParametrosIA) -> list[RegiaoEncontrada]:
    """Das máscaras dos modelos, fica UMA por objeto.

    Descarta o que não tem forma de objeto (manchas do fundo), o que foge do tamanho típico
    dos objetos desta foto (o pote, pedacinhos, vários grãos juntos) e repetições (outra
    máscara já cobre o mesmo objeto; vence a de maior pontuação). De cada máscara fica só
    o maior pedaço contínuo.
    """
    preparadas = [preparar_mascara(mascara, pontuacao, forma, p) for mascara, pontuacao in candidatas]
    return escolher_regioes([c for c in preparadas if c], forma, p)


def preparar_mascara(mascara: np.ndarray, pontuacao: float, forma: tuple[int, int], p: ParametrosIA):
    """Recorta a máscara na caixa do objeto (maior pedaço contínuo) e descarta o que não tem
    tamanho nem forma de objeto. Devolve (pontuação, área, y0, x0, recorte, contorno) ou None."""
    if not mascara.any():
        return None
    ys, xs = np.nonzero(mascara)
    y0, x0 = ys.min(), xs.min()
    recorte = mascara[y0:ys.max() + 1, x0:xs.max() + 1].astype(np.uint8)
    quantos, rotulos, estatisticas, _ = cv2.connectedComponentsWithStats(recorte, connectivity=8)
    maior = 1 + int(np.argmax(estatisticas[1:quantos, cv2.CC_STAT_AREA]))
    recorte = rotulos == maior
    area = int(estatisticas[maior, cv2.CC_STAT_AREA])
    area_da_foto = forma[0] * forma[1]
    if not p.area_minima * area_da_foto <= area <= p.area_maxima * area_da_foto:
        return None
    contornos, _ = cv2.findContours(recorte.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contorno = max(contornos, key=cv2.contourArea)
    casca = cv2.contourArea(cv2.convexHull(contorno))
    if casca == 0 or cv2.contourArea(contorno) / casca < p.solidez_minima:
        return None
    return pontuacao, area, y0, x0, recorte, contorno + [x0, y0]


def _na_escala_original(regiao: RegiaoEncontrada, escala: float, forma: tuple[int, int]) -> RegiaoEncontrada:
    altura, largura = forma
    poligono = [[min(round(x / escala), largura - 1), min(round(y / escala), altura - 1)] for x, y in regiao.poligono]
    return RegiaoEncontrada(poligono=poligono, area_px=round(regiao.area_px / escala ** 2), pontuacao=regiao.pontuacao)


def escolher_regioes(boas: list, forma: tuple[int, int], p: ParametrosIA) -> list[RegiaoEncontrada]:
    """Das candidatas preparadas: tamanho típico desta foto e sem repetições."""
    if not boas:
        return []
    mediana = float(np.median([b[1] for b in boas]))
    menor, maior = (fator * mediana for fator in p.faixa_relativa)
    boas = [b for b in boas if menor <= b[1] <= maior]

    boas.sort(key=lambda b: b[0], reverse=True)
    ocupado = np.zeros(forma, bool)
    regioes = []
    for pontuacao, area, y0, x0, recorte, contorno in boas:
        janela = ocupado[y0:y0 + recorte.shape[0], x0:x0 + recorte.shape[1]]
        if (recorte & janela).sum() > p.sobreposicao_maxima * area:
            continue
        poligono = cv2.approxPolyDP(contorno, p.tolerancia_contorno, True).reshape(-1, 2).tolist()
        if len(poligono) < 3:
            continue
        janela |= recorte
        regioes.append(RegiaoEncontrada(poligono=poligono, area_px=area,
                                        pontuacao=round(min(max(pontuacao, 0.0), 1.0), 4)))
    return regioes


# ------------------------------------------------------------ baixar pesos

class DownloadInvalido(RuntimeError):
    """O arquivo baixado não confere com o esperado (corrompido ou trocado)."""


def _sha256(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with open(caminho, 'rb') as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b''):
            resumo.update(bloco)
    return resumo.hexdigest()


def baixar_modelos(pasta: Path, abrir=urllib.request.urlopen):
    """Baixa os pesos que faltam para `pasta`, conferindo o hash. Gera mensagens de progresso.

    Grava num arquivo temporário e só renomeia depois de conferir: se a internet cair ou o
    arquivo vier errado, nada pela metade fica no lugar do modelo.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    for modelo in MODELOS:
        destino = pasta / modelo.nome
        if destino.is_file() and _sha256(destino) == modelo.sha256:
            yield f'{modelo.nome}: já estava baixado.'
            continue
        yield f'{modelo.nome}: baixando {modelo.tamanho_mb} MB...'
        descritor, temporario = tempfile.mkstemp(dir=pasta, suffix='.parcial')
        try:
            with os.fdopen(descritor, 'wb') as arquivo, abrir(modelo.url, timeout=60) as resposta:
                for bloco in iter(lambda: resposta.read(1 << 20), b''):
                    arquivo.write(bloco)
            if _sha256(Path(temporario)) != modelo.sha256:
                raise DownloadInvalido(f'{modelo.nome} veio diferente do esperado (hash não confere). '
                                       'Tente de novo; se continuar, avise o responsável.')
            os.replace(temporario, destino)
        finally:
            Path(temporario).unlink(missing_ok=True)
        yield f'{modelo.nome}: pronto.'
