"""Cálculos sobre polígonos (o contorno de uma região).

Um polígono é uma lista de pontos [x, y] em pixels da imagem original, com a
origem (0, 0) no canto superior esquerdo. Ex.: [[10, 10], [50, 10], [50, 40]].
"""


class PoligonoInvalido(ValueError):
    """O contorno recebido não descreve uma região válida."""


def validar_poligono(pontos) -> list[list[int]]:
    """Confere o formato e devolve os pontos como lista de [x, y] inteiros."""
    try:
        normalizado = [[int(round(x)), int(round(y))] for x, y in pontos]
    except (TypeError, ValueError) as erro:
        raise PoligonoInvalido('O contorno deve ser uma lista de pontos [x, y].') from erro
    if len(normalizado) < 3:
        raise PoligonoInvalido(f'O contorno precisa de pelo menos 3 pontos (recebeu {len(normalizado)}).')
    if any(x < 0 or y < 0 for x, y in normalizado):
        raise PoligonoInvalido('O contorno tem pontos com coordenada negativa.')
    if area_do_poligono(normalizado) == 0:
        raise PoligonoInvalido('O contorno não tem área (pontos alinhados ou repetidos).')
    return normalizado


def area_do_poligono(pontos) -> int:
    """Área em pixels pela fórmula do laço (shoelace), arredondada."""
    soma = 0
    for (x1, y1), (x2, y2) in zip(pontos, pontos[1:] + pontos[:1]):
        soma += x1 * y2 - x2 * y1
    return round(abs(soma) / 2)


def bbox_do_poligono(pontos) -> tuple[int, int, int, int]:
    """Menor retângulo que contém o polígono, no formato COCO: (x, y, largura, altura)."""
    xs = [x for x, _ in pontos]
    ys = [y for _, y in pontos]
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
