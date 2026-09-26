"""Configurações da aplicação.

Tudo que muda de um computador para outro vem de variáveis de ambiente, com um
valor padrão razoável. Nada de caminhos absolutos espalhados pelo código.

Variáveis reconhecidas:
    CAFE_DATA_DIR      pasta onde ficam banco e fotos (padrão: C:\\CafeData no Windows)
    CAFE_SECRET_KEY    chave para assinar cookies (padrão: gerada e guardada na pasta de dados)
"""
import os
import secrets
from datetime import timedelta
from pathlib import Path

RAIZ_DO_PROJETO = Path(__file__).resolve().parent.parent

# Fora do OneDrive de propósito: ver docs/decisoes/0003-dados-fora-do-onedrive.md
PASTA_DADOS_PADRAO = Path('C:/CafeData') if os.name == 'nt' else Path.home() / 'CafeData'


class Config:
    """Configuração normal (uso diário)."""

    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB por envio
    # Cookie da sessão (guarda quem é a pessoa): não vai em pedidos vindos de outros
    # sites (proteção extra contra CSRF) e dura 90 dias.
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=90)
    # Além do bloqueio por conta (5 erros), um limite por endereço de internet:
    # impede alguém de testar senhas em várias contas. Ver app/seguranca.py.
    LOGIN_MAXIMO_POR_IP = 20
    LOGIN_JANELA_POR_IP = timedelta(minutes=15)

    # Endereço na internet (Tailscale Funnel), descoberto por run.py ao iniciar. Só para
    # mostrar às pessoas (ex.: "para instalar, abra ..."); nada depende dele.
    ENDERECO_PUBLICO = None

    PASTA_TAXONOMIAS = RAIZ_DO_PROJETO / 'taxonomias'
    PASTA_MIGRACOES = RAIZ_DO_PROJETO / 'migrations'

    def __init__(self, pasta_dados=None):
        self.PASTA_DADOS = Path(
            pasta_dados or os.environ.get('CAFE_DATA_DIR') or PASTA_DADOS_PADRAO
        )
        self.PASTA_IMAGENS = self.PASTA_DADOS / 'imagens'
        self.SQLALCHEMY_DATABASE_URI = f"sqlite:///{(self.PASTA_DADOS / 'beanlab.db').as_posix()}"


class ConfigTeste(Config):
    """Configuração dos testes automáticos: cada teste usa uma pasta temporária."""

    TESTING = True
    SEGMENTACAO_SINCRONA = True  # segmenta na hora, sem thread: testes previsíveis


def carregar_chave_secreta(pasta_dados: Path) -> str:
    """Devolve a chave usada para assinar cookies.

    Fica num arquivo na pasta de dados (fora do git), criado na primeira execução.
    Assim a chave não vaza no GitHub e continua a mesma entre reinícios.
    """
    if chave := os.environ.get('CAFE_SECRET_KEY'):
        return chave
    arquivo = pasta_dados / '.chave_secreta'
    if not arquivo.exists():
        arquivo.write_text(secrets.token_hex(32), encoding='utf-8')
    return arquivo.read_text(encoding='utf-8').strip()
