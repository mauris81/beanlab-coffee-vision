"""O aplicativo num navegador de verdade: service worker, abrir sem sinal e a fila de
fotos guardadas no celular (IndexedDB) subindo sozinha quando a conexão volta.

"Sem sinal" é simulado pelo próprio Chrome (context.set_offline)."""
import re

import pytest

from app.dominio import Coleta, Imagem, TipoAmostra
from app.extensions import db
from tests.fabrica_imagens import foto_jpeg
from tests.navegador.conftest import violacoes_wcag

pytestmark = pytest.mark.navegador

_contador = iter(range(1000))


@pytest.fixture
def coleta(aplicacao):
    """Coleta de folhas (sem segmentação automática: o teste não espera a fila do servidor)."""
    n = next(_contador)
    with aplicacao.app_context():
        folhas = db.session.scalars(db.select(TipoAmostra).filter_by(codigo='folhas')).one()
        nova = Coleta(nome=f'Talhão {n} do campo', tipo_amostra=folhas)
        db.session.add(nova)
        db.session.commit()
        return {'id': nova.id, 'nome': nova.nome}


@pytest.fixture
def foto(tmp_path):
    caminho = tmp_path / 'campo.jpg'
    caminho.write_bytes(foto_jpeg(cor=(40, 120, 30)))
    return caminho


def fotos_na_coleta(aplicacao, coleta_id) -> int:
    with aplicacao.app_context():
        return db.session.query(Imagem).filter_by(coleta_id=coleta_id).count()


def esperar_service_worker(pagina):
    """Primeira visita: o service worker instala, guarda os arquivos e assume a página."""
    pagina.wait_for_function('() => navigator.serviceWorker.controller !== null', timeout=15_000)


def test_sem_sinal_o_aplicativo_abre_fotos_no_celular(abrir, endereco):
    pagina = abrir('/coletas', 'celular')
    esperar_service_worker(pagina)

    pagina.context.set_offline(True)
    pagina.goto(endereco + '/coletas/nova')
    assert pagina.get_by_role('heading', name='Fotos no celular', exact=True).is_visible()
    pagina.get_by_text('Sem conexão com a plataforma').wait_for()  # a página testa a conexão antes
    assert pagina.url.endswith('/coletas/nova')  # o endereço continua o que a pessoa pediu
    assert violacoes_wcag(pagina) == ''

    pagina.context.set_offline(False)  # o sinal volta: oferece abrir a página pedida
    pagina.get_by_role('button', name='Abrir a página que você pediu').click()
    pagina.wait_for_selector('h1:has-text("Nova coleta")')
    assert pagina.erros_js == []


def test_foto_sem_sinal_fica_guardada_e_sobe_quando_a_conexao_volta(abrir, aplicacao, coleta, foto):
    pagina = abrir(f'/coletas/{coleta["id"]}', 'celular')
    pagina.context.set_offline(True)
    pagina.locator('input[type=file]:not([capture])').set_input_files(foto)
    pagina.get_by_role('button', name='Enviar', exact=True).click()

    pagina.wait_for_selector('text=A foto ficou guardada no celular')
    faixa = pagina.locator('#fila-no-celular')
    faixa.wait_for(state='visible')
    assert '1 foto guardada no celular' in faixa.inner_text()
    assert fotos_na_coleta(aplicacao, coleta['id']) == 0

    # O sinal volta: a fila sobe sozinha, avisa e a página mostra a foto.
    pagina.context.set_offline(False)
    pagina.wait_for_selector('text=1 foto guardada foi enviada', timeout=20_000)
    pagina.wait_for_selector('.foto__nome:has-text("campo.jpg")', timeout=15_000)
    assert fotos_na_coleta(aplicacao, coleta['id']) == 1
    assert not pagina.locator('#fila-no-celular').is_visible()
    assert pagina.erros_js == []


def test_envio_lento_pode_ficar_para_depois(abrir, aplicacao, coleta, foto):
    """Sinal fraco: o envio não termina; a pessoa guarda no celular e segue trabalhando."""
    pagina = abrir(f'/coletas/{coleta["id"]}', 'celular')
    pedidos_presos = []
    pagina.route('**/enviar', lambda rota: pedidos_presos.append(rota))  # nunca responde
    pagina.locator('input[type=file]:not([capture])').set_input_files(foto)
    pagina.get_by_role('button', name='Enviar', exact=True).click()
    pagina.get_by_role('button', name='Guardar no celular e enviar depois').click()
    pagina.wait_for_selector('text=Envio interrompido. A foto ficou guardada no celular')

    # A foto sobe em segundo plano: pelo service worker (que o bloqueio deste teste não
    # alcança) ou pela página, quando o sinal "volta". Seja qual for, chega uma vez só.
    pagina.unroute('**/enviar')
    pagina.evaluate("window.dispatchEvent(new Event('online'))")
    pagina.wait_for_selector('.foto__nome:has-text("campo.jpg")', timeout=20_000)
    assert fotos_na_coleta(aplicacao, coleta['id']) == 1


def test_fotografar_sem_sinal_pela_pagina_do_celular(abrir, aplicacao, coleta, foto, endereco):
    pagina = abrir('/coletas', 'celular')  # com sinal: o celular guarda as coletas e quem é a pessoa
    esperar_service_worker(pagina)

    pagina.context.set_offline(True)
    pagina.goto(endereco + '/fotos-no-celular')  # vem do próprio celular
    pagina.get_by_text('Sem conexão agora').wait_for()  # a página testa a conexão antes
    escolha = pagina.get_by_label('Para qual coleta?')
    escolha.locator(f'option[value="{coleta["id"]}"]').wait_for(state='attached')
    escolha.select_option(str(coleta['id']))
    pagina.locator('input[type=file][capture]').set_input_files(foto)
    pagina.wait_for_selector('text=Foto guardada no celular.')
    item = pagina.locator('[data-lista] .foto')
    assert item.count() == 1 and 'Esperando sinal' in item.inner_text()
    assert coleta['nome'] in item.inner_text()
    assert violacoes_wcag(pagina) == ''

    pagina.context.set_offline(False)
    pagina.wait_for_selector('text=Nenhuma foto guardada', timeout=20_000)
    assert fotos_na_coleta(aplicacao, coleta['id']) == 1
    pagina.get_by_text('Conectado à plataforma').wait_for()
    assert pagina.erros_js == []


def test_politica_de_seguranca_bloqueia_script_injetado(abrir):
    """Se alguém conseguisse enfiar um <script> na página (XSS), o navegador não o roda."""
    pagina = abrir('/coletas')
    pagina.evaluate("""() => {
        const s = document.createElement('script');
        s.textContent = 'window.invadiu = true';
        document.body.append(s);
    }""")
    pagina.wait_for_timeout(300)
    assert pagina.evaluate('window.invadiu') is None
    assert any(re.search('Content Security Policy', erro) for erro in pagina.erros_js)


def test_sem_sinal_a_ajuda_abre_do_celular(abrir, endereco):
    pagina = abrir('/coletas', 'celular')
    esperar_service_worker(pagina)
    pagina.context.set_offline(True)
    pagina.goto(endereco + '/ajuda')
    assert pagina.get_by_role('heading', name='Ajuda', level=1).is_visible()
    assert pagina.get_by_role('heading', name='Sem sinal no campo').is_visible()
    assert pagina.erros_js == []
