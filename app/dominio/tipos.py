"""Valores fixos (listas de opções) e utilidades usadas por várias entidades."""
import enum
from datetime import datetime, timezone

from sqlalchemy import Enum as SAEnum


def agora_utc() -> datetime:
    """Data e hora atual em UTC. Todas as datas do banco estão em UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def tipo_enum(classe_enum: type[enum.Enum]) -> SAEnum:
    """Coluna que guarda o *valor* legível do enum (ex.: 'aguardando') como texto.

    O SQLAlchemy recusa valores fora da lista antes de gravar. Não criamos uma
    restrição CHECK no banco para que adicionar uma opção nova não exija migração.
    """
    return SAEnum(
        classe_enum,
        native_enum=False,
        create_constraint=False,
        length=20,
        validate_strings=True,
        values_callable=lambda membros: [m.value for m in membros],
    )


class OrigemImagem(enum.StrEnum):
    CAMERA = 'camera'          # foto tirada pela câmera, dentro da plataforma
    ARQUIVO = 'arquivo'        # arquivo escolhido do computador/celular
    IMPORTACAO = 'importacao'  # veio de um lote ou conjunto de dados externo


class StatusImagem(enum.StrEnum):
    AGUARDANDO = 'aguardando'    # recebida, esperando segmentação
    SEGMENTANDO = 'segmentando'  # segmentação em andamento
    PRONTA = 'pronta'            # regiões disponíveis para anotar
    ERRO = 'erro'                # segmentação falhou (ver JobSegmentacao)


class OrigemRegiao(enum.StrEnum):
    AUTOMATICA = 'automatica'  # criada por um motor de segmentação
    MANUAL = 'manual'          # desenhada por uma pessoa
    IMPORTADA = 'importada'    # veio pronta (imagem já segmentada, COCO, YOLO...)


class OrigemAnotacao(enum.StrEnum):
    MANUAL = 'manual'        # uma pessoa escolheu a classe
    IMPORTADA = 'importada'  # veio pronta junto com os dados importados
    MODELO = 'modelo'        # sugerida por um modelo de classificação


class StatusJob(enum.StrEnum):
    NA_FILA = 'na_fila'
    PROCESSANDO = 'processando'
    CONCLUIDO = 'concluido'
    ERRO = 'erro'
