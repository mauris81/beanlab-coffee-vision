"""Motores de segmentação: recebem uma foto e devolvem as regiões encontradas.

Todos seguem a interface de app/segmentacao/base.py. Para adicionar um motor:
crie o arquivo, registre-o em MOTORES abaixo e indique-o no YAML do tipo de
amostra (campo `motor`). Ver docs/decisoes/0002-segmentacao-plugavel.md.

    classico  watershed para grãos sobre fundo azul (sempre disponível)
    ia        FastSAM + SAM 2.1 (opcional: "Instalar IA.bat"; decisão 0009)
"""
from app.segmentacao.base import RegiaoEncontrada, Segmentador
from app.segmentacao.classico import MotorClassico
from app.segmentacao.ia import MotorIA

MOTORES: dict[str, Segmentador] = {
    MotorClassico.nome: MotorClassico(),
    MotorIA.nome: MotorIA(),
}


def primeiro_disponivel(nomes) -> str | None:
    """Da lista de preferência do YAML (ex.: ['ia', 'classico']), o primeiro que roda aqui."""
    return next((nome for nome in nomes if MOTORES[nome].disponivel()), None)


def obter_motor(nome: str) -> Segmentador:
    try:
        return MOTORES[nome]
    except KeyError:
        raise ValueError(f'Motor de segmentação desconhecido: "{nome}". '
                         f'Disponíveis: {", ".join(MOTORES)}') from None


__all__ = ['MOTORES', 'RegiaoEncontrada', 'Segmentador', 'obter_motor', 'primeiro_disponivel']
