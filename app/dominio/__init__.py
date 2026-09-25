"""Entidades do sistema: o que existe e como se relaciona.

    TipoAmostra ──1:N── Classe
        │
       1:N
        │
      Coleta ──1:N── Imagem ──1:N── Regiao ──1:N── Anotacao ──N:1── Pessoa
                       │
                      1:N
                       │
                 JobSegmentacao

Detalhes e justificativas em docs/MODELO_DE_DADOS.md.
"""
from app.dominio.coleta import Coleta, Imagem
from app.dominio.job import JobSegmentacao
from app.dominio.pessoa import Papel, Pessoa
from app.dominio.regiao import Anotacao, Regiao
from app.dominio.taxonomia import Classe, TipoAmostra
from app.dominio.tipos import (
    OrigemAnotacao, OrigemImagem, OrigemRegiao, StatusImagem, StatusJob,
)

__all__ = [
    'Anotacao', 'Classe', 'Coleta', 'Imagem', 'JobSegmentacao', 'Papel', 'Pessoa', 'Regiao',
    'TipoAmostra', 'OrigemAnotacao', 'OrigemImagem', 'OrigemRegiao', 'StatusImagem',
    'StatusJob',
]
