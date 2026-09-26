r"""Compara os motores de segmentação da plataforma em fotos reais (como foi feito na Fase 6).

Uso (com a plataforma fechada ou aberta, tanto faz):
    .\.venv\Scripts\python.exe ferramentas\avaliar_segmentacao.py FOTO [FOTO ...]
        [--motores classico ia] [--recorte X Y LADO --contagem N] [--saida PASTA]

Para cada foto e motor, mostra quantos objetos achou e quanto tempo levou, e grava a
foto com os contornos desenhados (e o recorte ampliado) na pasta de saída.

Validar com um gabarito simples: escolha um recorte da foto, conte os objetos à mão
(amplie a imagem) e passe --recorte e --contagem. A ferramenta conta quantos objetos
cada motor achou com o centro dentro do recorte. Para uma validação séria, use várias
fotos de cada tipo de amostra e, se possível, contornos desenhados à mão (IoU).

As fotos de avaliação da equipe são dados da pesquisa: guarde a saída fora do git
(o padrão é <pasta de dados>/avaliacao).
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.segmentacao import obter_motor  # noqa: E402


def abrir_foto(caminho: Path) -> np.ndarray:
    return np.array(ImageOps.exif_transpose(Image.open(caminho)).convert('RGB'))


def main():
    argumentos = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    argumentos.add_argument('fotos', nargs='+', type=Path)
    argumentos.add_argument('--motores', nargs='+', default=['classico', 'ia'])
    argumentos.add_argument('--recorte', nargs=3, type=int, metavar=('X', 'Y', 'LADO'))
    argumentos.add_argument('--contagem', type=int, help='objetos contados à mão dentro do recorte')
    argumentos.add_argument('--saida', type=Path)
    opcoes = argumentos.parse_args()

    app = create_app()
    saida = opcoes.saida or Path(app.config['PASTA_DADOS']) / 'avaliacao'
    saida.mkdir(parents=True, exist_ok=True)
    print(f'{"foto":24} {"motor":10} {"objetos":>8} {"no recorte":>12} {"tempo":>8}')
    with app.app_context():
        for caminho in opcoes.fotos:
            rgb = abrir_foto(caminho)
            for nome in opcoes.motores:
                motor = obter_motor(nome)
                if not motor.disponivel():
                    print(f'{caminho.name[:24]:24} {nome:10} (não instalado neste computador)')
                    continue
                inicio = time.perf_counter()
                regioes = motor.segmentar(rgb)
                segundos = time.perf_counter() - inicio

                desenho = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                no_recorte = 0
                for regiao in regioes:
                    pontos = np.array(regiao.poligono, np.int32)
                    cv2.polylines(desenho, [pontos], True, (0, 0, 255), 2)
                    if opcoes.recorte:
                        x, y, lado = opcoes.recorte
                        cx, cy = pontos.mean(axis=0)
                        no_recorte += x <= cx < x + lado and y <= cy < y + lado
                base = f'{caminho.stem}_{nome}'
                cv2.imwrite(str(saida / f'{base}.jpg'), desenho)
                recorte_txt = ''
                if opcoes.recorte:
                    x, y, lado = opcoes.recorte
                    ampliado = cv2.resize(desenho[y:y + lado, x:x + lado], None, fx=2.5, fy=2.5,
                                          interpolation=cv2.INTER_NEAREST)
                    cv2.imwrite(str(saida / f'{base}_recorte.jpg'), ampliado)
                    recorte_txt = f'{no_recorte}' + (f' de ~{opcoes.contagem}' if opcoes.contagem else '')
                print(f'{caminho.name[:24]:24} {nome:10} {len(regioes):>8} {recorte_txt:>12} {segundos:>6.1f} s')
    print(f'\nImagens com os contornos em: {saida}')


if __name__ == '__main__':
    main()
