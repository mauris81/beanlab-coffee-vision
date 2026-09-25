"""O caminho completo de quem coleta, no navegador, com a fila em segundo plano:
entrar -> criar coleta -> enviar foto -> acompanhar a segmentação -> excluir."""
import re

import pytest

from tests.fabrica_imagens import bandeja_de_graos
from tests.navegador.conftest import violacoes_wcag

pytestmark = pytest.mark.navegador


@pytest.mark.parametrize('tela', ['computador', 'celular'])
def test_coletar_enviar_e_acompanhar(abrir, tmp_path, tela):
    foto = tmp_path / 'bandeja.png'
    foto.write_bytes(bandeja_de_graos())
    pagina = abrir('/coletas', tela)

    # 1. Sem saber quem é a pessoa, "Nova coleta" leva para "Quem é você?"
    pagina.get_by_role('link', name='Nova coleta').click()
    pagina.wait_for_url(re.compile(r'/entrar'))
    assert 'Antes, diga quem é você' in pagina.inner_text('main')
    assert violacoes_wcag(pagina) == ''
    pagina.get_by_role('textbox', name='Seu nome').fill(f'Ana {tela}')
    pagina.get_by_role('button', name='Continuar').click()

    # 2. Volta sozinha para o formulário da coleta
    pagina.wait_for_url(re.compile(r'/coletas/nova'))
    pagina.get_by_role('button', name='Criar coleta').click()  # sem preencher: erros nos campos
    assert 'Escolha o que foi fotografado.' in pagina.inner_text('main')
    assert violacoes_wcag(pagina) == ''
    pagina.get_by_label('Grãos').check()
    pagina.get_by_label('Nome da coleta').fill('Talhão 3, março')
    pagina.get_by_label('Talhão').fill('3')
    pagina.get_by_role('button', name='Criar coleta').click()

    # 3. Página da coleta: envia a foto (com barra de progresso)
    pagina.wait_for_url(re.compile(r'/coletas/\d+'))
    assert 'Coleta criada. Agora envie as fotos.' in pagina.inner_text('main')
    pagina.locator('input[type=file]:not([capture])').set_input_files(foto)
    assert '1 arquivo escolhido' in pagina.inner_text('[data-resumo-arquivos]')
    pagina.get_by_role('button', name='Enviar', exact=True).click()
    pagina.wait_for_selector('text=1 foto recebida.')

    # 4. O status se atualiza sozinho até "Pronta" (fila em segundo plano); depois a
    #    página recarrega uma vez para atualizar os números
    #    (a foto de teste é rápida: pode já chegar pronta, sem acompanhamento)
    pagina.wait_for_selector('.foto .selo--sucesso', timeout=30_000)
    pagina.wait_for_timeout(2_000)
    pagina.wait_for_load_state('networkidle')
    regioes = int(pagina.inner_text('[data-regioes]').split()[0])
    assert regioes > 0
    assert violacoes_wcag(pagina) == ''
    assert pagina.erros_js == []

    # 5. Excluir pelo diálogo (foco começa em "Cancelar")
    pagina.get_by_role('button', name=re.compile('Excluir a foto bandeja.png')).click()
    assert pagina.evaluate('document.activeElement.textContent.trim()') == 'Cancelar'
    pagina.get_by_role('button', name='Excluir foto').click()
    pagina.wait_for_selector('text=Foto "bandeja.png" excluída.')
    assert pagina.is_visible('text=Nenhuma foto ainda')


def test_fim_da_segmentacao_nao_recarrega_com_dialogo_aberto(abrir, tmp_path):
    """Se a pessoa estiver no meio de algo, a página não recarrega sozinha."""
    foto = tmp_path / 'bandeja.png'
    foto.write_bytes(bandeja_de_graos(semente=21))
    pagina = abrir('/entrar')
    pagina.get_by_role('textbox', name='Seu nome').fill('Bia')
    pagina.get_by_role('button', name='Continuar').click()
    pagina.goto(pagina.url.rsplit('/', 1)[0] + '/coletas/nova')
    pagina.get_by_label('Grãos').check()
    pagina.get_by_label('Nome da coleta').fill('Teste de recarga')
    pagina.get_by_role('button', name='Criar coleta').click()
    pagina.locator('input[type=file]:not([capture])').set_input_files(foto)
    pagina.get_by_role('button', name='Enviar', exact=True).click()
    pagina.wait_for_selector('text=1 foto recebida.')

    # A foto de teste segmenta em ~0,3 s. Para o fim acontecer com o diálogo já aberto,
    # a página recarregada "acha" que ainda há 1 pendente; o servidor responde que não.
    pagina.add_init_script("""document.addEventListener('readystatechange', () => {
        if (document.readyState === 'interactive')
            document.getElementById('pagina-coleta')?.setAttribute('data-pendentes', '1');
    });""")
    pagina.reload(wait_until='networkidle')
    pagina.get_by_role('button', name=re.compile('Excluir a foto')).click()  # abre o diálogo
    pagina.evaluate('window.__marca = 1')  # some se a página recarregar
    pagina.wait_for_selector('text=Atualize a página quando quiser', timeout=15_000)
    assert pagina.evaluate('window.__marca') == 1
    assert pagina.is_visible('#dialogo-excluir')
