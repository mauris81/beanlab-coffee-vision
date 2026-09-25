"""Gravação e leitura de arquivos (fotos) no disco."""
from flask import current_app

from app.armazenamento.imagens import ArmazenamentoImagens, ArquivoSalvo


def armazenamento_de_imagens() -> ArmazenamentoImagens:
    """Armazenamento configurado para a aplicação atual."""
    return ArmazenamentoImagens(current_app.config['PASTA_IMAGENS'])


__all__ = ['ArmazenamentoImagens', 'ArquivoSalvo', 'armazenamento_de_imagens']
