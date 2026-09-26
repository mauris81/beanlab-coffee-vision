r"""Gera os ícones PNG do aplicativo (tela inicial do celular) a partir do logotipo.

Rode de novo sempre que app/static/logo.svg mudar:
    .\.venv\Scripts\python.exe ferramentas\gerar_icones_do_aplicativo.py

Usa o Playwright (requirements-dev.txt) com o Chrome ou Edge instalado neste PC,
porque o navegador desenha o SVG exatamente como na plataforma.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
LOGO = RAIZ / 'app' / 'static' / 'logo.svg'
PASTA = RAIZ / 'app' / 'static' / 'aplicativo'
COR_DO_FUNDO = '#6B4226'  # a mesma do quadrado do logotipo

# (arquivo, lado em px, sangrado). "Sangrado" = fundo até as bordas: o celular recorta no
# formato dele (círculo no Android, quadrado arredondado no iPhone). Por isso o desenho
# fica menor, dentro da "zona segura" (o círculo central de 80%).
ICONES = [
    ('icone-192.png', 192, False),
    ('icone-512.png', 512, False),
    ('icone-mascaravel-512.png', 512, True),
    ('icone-apple-180.png', 180, True),
]


def pagina(lado: int, sangrado: bool) -> str:
    desenho = round(lado * (0.84 if sangrado else 1))
    fundo = COR_DO_FUNDO if sangrado else 'transparent'
    return (f'<html><body style="margin:0;width:{lado}px;height:{lado}px;display:grid;'
            f'place-items:center;background:{fundo}"><div style="width:{desenho}px;height:{desenho}px">'
            f'<style>svg{{display:block;width:100%;height:100%}}</style>{LOGO.read_text(encoding="utf-8")}'
            '</div></body></html>')


def main():
    PASTA.mkdir(exist_ok=True)
    with sync_playwright() as p:
        navegador = None
        for canal in ('chrome', 'msedge'):
            try:
                navegador = p.chromium.launch(channel=canal)
                break
            except Exception:  # canal não instalado
                continue
        if navegador is None:
            raise SystemExit('Instale o Chrome ou o Edge para gerar os ícones.')
        for nome, lado, sangrado in ICONES:
            aba = navegador.new_page(viewport={'width': lado, 'height': lado})
            aba.set_content(pagina(lado, sangrado))
            aba.screenshot(path=PASTA / nome, omit_background=not sangrado)
            aba.close()
            print(f'  {nome} ({lado}x{lado})')
        navegador.close()


if __name__ == '__main__':
    main()
