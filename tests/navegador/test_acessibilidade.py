"""Auditoria automática de acessibilidade com axe-core (WCAG 2.2 A e AA).

axe-core: https://github.com/dequelabs/axe-core (licença MPL-2.0; o arquivo
axe.min.js desta pasta é uma cópia sem alterações da versão 4.10.2).
Não substitui teste com pessoas nem com leitor de tela, mas pega a maior parte
dos erros comuns: contraste, rótulos, nomes de botões, estrutura, teclado.
Páginas que precisam de dados (coleta com fotos) são auditadas em test_fluxo_coleta.py.
"""
import pytest

from tests.navegador.conftest import violacoes_wcag

pytestmark = pytest.mark.navegador

PAGINAS = ['/', '/guia-visual', '/pagina-que-nao-existe', '/coletas', '/entrar']


@pytest.mark.parametrize('tema', ['light', 'dark'])
@pytest.mark.parametrize('tela', ['celular', 'computador'])
@pytest.mark.parametrize('caminho', PAGINAS)
def test_pagina_sem_violacoes_wcag(abrir, caminho, tela, tema):
    pagina = abrir(caminho, tela, tema)
    assert violacoes_wcag(pagina) == ''
    assert pagina.erros_js == []
