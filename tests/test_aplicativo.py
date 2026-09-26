"""A plataforma como aplicativo no celular: manifesto, service worker, "Fotos no celular"
e o envio das fotos guardadas (fila). O comportamento no navegador de verdade (sem sinal,
fila no IndexedDB) está em tests/navegador/test_aplicativo_navegador.py."""
import json
import re
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.dominio import Imagem
from app.extensions import db
from tests.conftest import TOKEN, criar_coleta
from tests.fabrica_imagens import foto_jpeg

STATIC = Path(__file__).resolve().parent.parent / 'app' / 'static'
FILA = {'X-Envio-Via': 'fila', 'X-CSRF': TOKEN}


def _enviar_pela_fila(cliente, coleta_id, conteudo, nome='campo.jpg', modo='fotos'):
    return cliente.post(f'/coletas/{coleta_id}/enviar', headers=FILA,
                        data={'modo': modo, 'arquivos': (BytesIO(conteudo), nome)})


# ------------------------------------------------------------------ manifesto

def test_manifesto_permite_instalar(cliente):
    manifesto = json.loads((STATIC / 'manifest.json').read_text(encoding='utf-8'))
    assert manifesto['display'] == 'standalone' and manifesto['start_url'] == '/' and manifesto['scope'] == '/'
    tamanhos = {}
    for icone in manifesto['icons']:
        assert cliente.get(icone['src']).status_code == 200, icone['src']
        if icone['type'] == 'image/png':
            with Image.open(STATIC / icone['src'].removeprefix('/static/')) as imagem:
                assert f'{imagem.width}x{imagem.height}' == icone['sizes'], icone['src']
            tamanhos.setdefault(icone['purpose'], set()).add(icone['sizes'])
    # O Chrome exige 192 e 512; o ícone "mascarável" evita a borda branca no Android.
    assert {'192x192', '512x512'} <= tamanhos['any'] and '512x512' in tamanhos['maskable']


def test_atalhos_do_manifesto_existem(logado):
    manifesto = json.loads((STATIC / 'manifest.json').read_text(encoding='utf-8'))
    for atalho in manifesto['shortcuts']:
        assert logado.get(atalho['url']).status_code == 200, atalho['url']


def test_icone_do_iphone_esta_na_pagina(logado):
    html = logado.get('/').get_data(as_text=True)
    endereco = re.search(r'rel="apple-touch-icon" href="([^"]+)"', html).group(1)
    assert logado.get(endereco).status_code == 200


# ------------------------------------------------------------- service worker

def test_service_worker_funciona_sem_login_e_nunca_fica_velho(cliente):
    resposta = cliente.get('/sw.js')  # nem administração existe ainda: precisa responder mesmo assim
    assert resposta.status_code == 200 and resposta.mimetype == 'text/javascript'
    assert resposta.headers['Cache-Control'] == 'no-cache'
    assert re.search(r'const VERSAO = "[0-9a-f]{12}";', resposta.get_data(as_text=True))


def test_tudo_que_o_celular_guarda_existe(cliente, administracao):
    """Se um só endereço da lista falhar, o celular não instala o service worker."""
    codigo = cliente.get('/sw.js').get_data(as_text=True)
    arquivos = json.loads(re.search(r'const ARQUIVOS = (\[.*?\]);', codigo).group(1))
    pagina = json.loads(re.search(r'const PAGINA_SEM_SINAL = (".*?");', codigo).group(1))
    assert '/static/js/fila-fotos.js' in arquivos and '/static/css/base.css' in arquivos
    assert not any(a.endswith('.txt') for a in arquivos)
    for endereco in [*arquivos, pagina]:
        assert cliente.get(endereco).status_code == 200, endereco


def test_versao_muda_quando_um_arquivo_muda(app, monkeypatch):
    from app.web import aplicativo
    with app.test_request_context():
        antes = aplicativo._calcular_versao()
        original = Path.read_bytes
        monkeypatch.setattr(Path, 'read_bytes',
                            lambda caminho: original(caminho) + (b'/*mudou*/' if caminho.name == 'base.css' else b''))
        assert aplicativo._calcular_versao() != antes


# ---------------------------------------------------------- fotos no celular

def test_fotos_no_celular_abre_sem_login(cliente, administracao):
    resposta = cliente.get('/fotos-no-celular')
    assert resposta.status_code == 200 and 'Fotos no celular' in resposta.get_data(as_text=True)


def test_fotos_no_celular_nao_tem_dados_de_ninguem(logado):
    """Esta página fica guardada no celular: não pode levar nome, menu nem código da sessão."""
    html = logado.get('/fotos-no-celular').get_data(as_text=True)
    assert 'Ana' not in html
    assert 'name="csrf"' not in html and 'name="pessoa"' not in html
    assert 'navegacao' not in html
    assert 'id="fila-no-celular"' not in html


def test_paginas_dizem_quem_esta_logado_para_a_fila(logado, cliente):
    html = logado.get('/coletas').get_data(as_text=True)
    assert re.search(r'<meta name="pessoa" content="\d+">', html)
    assert 'id="fila-no-celular"' in html
    logado.post('/sair', data={'_csrf': TOKEN})
    assert '<meta name="pessoa" content="">' in cliente.get('/entrar').get_data(as_text=True)


def test_lista_de_coletas_para_fotografar_sem_sinal(logado, cliente):
    coleta = criar_coleta(nome='Talhão 3')
    dados = logado.get('/api/coletas').get_json()['coletas']
    assert dados == [{'id': coleta.id, 'nome': 'Talhão 3', 'tipo': 'Grãos', 'data': None,
                      'envio': f'/coletas/{coleta.id}/enviar'}]


def test_lista_de_coletas_exige_login(cliente, administracao):
    assert cliente.get('/api/coletas').status_code == 401


# ------------------------------------------------------------ envio pela fila

def test_envio_pela_fila_responde_json_sem_mensagens_na_sessao(logado):
    coleta = criar_coleta(num_regioes=0)
    resposta = _enviar_pela_fila(logado, coleta.id, foto_jpeg())
    assert resposta.status_code == 200
    assert resposta.get_json() == {'resultados': [{'nome': 'campo.jpg', 'situacao': 'nova', 'mensagem': 'Recebida.'}]}
    with logado.session_transaction() as sessao:
        assert '_flashes' not in sessao  # a fila mostra o resultado; nada acumula para depois
    assert db.session.query(Imagem).filter_by(coleta_id=coleta.id, nome_original='campo.jpg').count() == 1


def test_foto_enviada_duas_vezes_nao_duplica(logado):
    """Sinal que cai no meio do envio: a fila manda de novo, e a plataforma reconhece."""
    coleta = criar_coleta(num_regioes=0)
    conteudo = foto_jpeg()
    _enviar_pela_fila(logado, coleta.id, conteudo)
    segunda = _enviar_pela_fila(logado, coleta.id, conteudo)
    assert segunda.get_json()['resultados'][0]['situacao'] == 'repetida'


def test_fila_nao_aceita_coco(logado):
    coleta = criar_coleta(num_regioes=0)
    resposta = _enviar_pela_fila(logado, coleta.id, b'{}', nome='anotacoes.json', modo='coco')
    assert resposta.status_code == 400 and 'erro' in resposta.get_json()


def test_fila_para_coleta_excluida_responde_404(logado):
    assert _enviar_pela_fila(logado, 99999, foto_jpeg()).status_code == 404


# ------------------------------------------------------------------ instalar

def test_cartao_de_instalar_fica_escondido_ate_o_navegador_permitir(logado, app):
    html = logado.get('/').get_data(as_text=True)
    assert re.search(r'<section class="cartao pilha" data-instalar hidden', html)
    assert 'data-instalar-modo="sem-https"' not in html  # sem endereço público, nada a sugerir
    app.config['ENDERECO_PUBLICO'] = 'https://pc.rede.ts.net'
    assert 'https://pc.rede.ts.net' in logado.get('/').get_data(as_text=True)


def test_endereco_publico_lido_do_tailscale():
    from app.publicacao import extrair_endereco_publico
    configuracao = {
        'Web': {'pc.rede.ts.net:443': {'Handlers': {'/': {'Proxy': 'http://127.0.0.1:5000'}}}},
        'AllowFunnel': {'pc.rede.ts.net:443': True},
    }
    assert extrair_endereco_publico(configuracao, 5000) == 'https://pc.rede.ts.net'
    assert extrair_endereco_publico(configuracao, 5001) is None  # aponta para outra porta
    configuracao['AllowFunnel']['pc.rede.ts.net:443'] = False
    assert extrair_endereco_publico(configuracao, 5000) is None  # só na rede Tailscale, não na internet
    assert extrair_endereco_publico({}, 5000) is None
