"""A plataforma publicada na internet a partir deste PC (Tailscale Funnel).

Ligar e desligar: "Publicar na internet.bat" (usa o comando `tailscale funnel`).
Aqui a plataforma só LÊ a situação, para mostrar o endereço na janela preta e na
página inicial, e cuida para o PC não suspender enquanto ela estiver aberta.

Por que assim: docs/decisoes/0007-publicacao-e-aplicativo.md
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

LOCAL_PADRAO_DO_TAILSCALE = Path(os.environ.get('ProgramFiles', r'C:\Program Files'), 'Tailscale', 'tailscale.exe')


def programa_tailscale() -> str | None:
    if encontrado := shutil.which('tailscale'):
        return encontrado
    return str(LOCAL_PADRAO_DO_TAILSCALE) if LOCAL_PADRAO_DO_TAILSCALE.is_file() else None


def endereco_publico(porta: int) -> str | None:
    """https://<nome-do-pc>.<rede>.ts.net se o Funnel estiver ligado para esta porta; senão None."""
    programa = programa_tailscale()
    if programa is None:
        return None
    try:
        saida = subprocess.run(
            [programa, 'serve', 'status', '--json'], capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        configuracao = json.loads(saida.stdout or '{}')
    except (OSError, subprocess.SubprocessError, ValueError):
        return None  # Tailscale desligado, travado ou numa versão que responde diferente
    return extrair_endereco_publico(configuracao, porta)


def extrair_endereco_publico(configuracao: dict, porta: int) -> str | None:
    """Lê a resposta de `tailscale serve status --json`. Exemplo:
        {"Web": {"pc.rede.ts.net:443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:5000"}}}},
         "AllowFunnel": {"pc.rede.ts.net:443": true}}
    """
    for host_e_porta, ligado in (configuracao.get('AllowFunnel') or {}).items():
        if not ligado:
            continue
        destinos = ((configuracao.get('Web') or {}).get(host_e_porta) or {}).get('Handlers') or {}
        destino = (destinos.get('/') or {}).get('Proxy', '')
        if destino.rstrip('/').endswith(f':{porta}'):
            host, _, porta_https = host_e_porta.rpartition(':')
            return f'https://{host}' + ('' if porta_https == '443' else f':{porta_https}')
    return None


def manter_pc_acordado() -> bool:
    """Impede o Windows de suspender sozinho enquanto a plataforma estiver aberta (a tela
    ainda pode apagar). Vale só enquanto o programa roda: fechou a janela, volta ao normal.
    Precisa ser chamado pela linha de execução que fica viva (a principal)."""
    if os.name != 'nt':
        return False
    import ctypes
    continuo, sistema_necessario = 0x80000000, 0x00000001  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    return bool(ctypes.windll.kernel32.SetThreadExecutionState(continuo | sistema_necessario))
