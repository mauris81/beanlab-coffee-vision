"""Auditoria automática de acessibilidade com axe-core (WCAG 2.2 A e AA).

axe-core: https://github.com/dequelabs/axe-core (licença MPL-2.0; o arquivo
axe.min.js desta pasta é uma cópia sem alterações da versão 4.10.2).
Não substitui teste com pessoas nem com leitor de tela, mas pega a maior parte
dos erros comuns: contraste, rótulos, nomes de botões, estrutura, teclado.
"""
from pathlib import Path

import pytest

pytestmark = pytest.mark.navegador

AXE = (Path(__file__).parent / 'axe.min.js').read_text(encoding='utf-8')
REGRAS_WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']
PAGINAS = ['/', '/guia-visual', '/pagina-que-nao-existe']


def _descrever(violacoes) -> str:
    linhas = []
    for v in violacoes:
        linhas.append(f"[{v['impact']}] {v['id']}: {v['help']} ({v['helpUrl']})")
        linhas += [f"    em {no['target']}" for no in v['nodes'][:5]]
    return '\n'.join(linhas)


@pytest.mark.parametrize('tema', ['light', 'dark'])
@pytest.mark.parametrize('tela', ['celular', 'computador'])
@pytest.mark.parametrize('caminho', PAGINAS)
def test_pagina_sem_violacoes_wcag(abrir, caminho, tela, tema):
    pagina = abrir(caminho, tela, tema)
    pagina.add_script_tag(content=AXE)
    resultado = pagina.evaluate(
        '(regras) => axe.run(document, {runOnly: {type: "tag", values: regras}})', REGRAS_WCAG)
    assert resultado['violations'] == [], '\n' + _descrever(resultado['violations'])
    assert pagina.erros_js == []
