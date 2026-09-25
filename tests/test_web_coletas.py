"""Rotas de coletas e envio de fotos (sem navegador). Login: tests/test_web_login.py."""
import html
import io

from sqlalchemy import select

from app.dominio import Coleta, Imagem, StatusImagem
from app.extensions import db
from tests.conftest import TOKEN
from tests.fabrica_imagens import foto_de_graos, foto_jpeg


def criar_coleta(cliente, tipo='graos', nome='Talhão 3'):
    resposta = cliente.post('/coletas/nova', data={'_csrf': TOKEN, 'tipo': tipo, 'nome': nome})
    assert resposta.status_code == 302
    return db.session.scalars(select(Coleta).filter_by(nome=nome)).one()


def enviar(cliente, coleta, arquivos, modo='fotos', **cabecalhos):
    dados = {'_csrf': TOKEN, 'modo': modo,
             'arquivos': [(io.BytesIO(conteudo), nome) for nome, conteudo in arquivos]}
    return cliente.post(f'/coletas/{coleta.id}/enviar', data=dados,
                        content_type='multipart/form-data', headers=cabecalhos)


# ----------------------------------------------------------------- segurança

def test_formulario_sem_codigo_csrf_e_recusado(logado):
    resposta = logado.post('/coletas/nova', data={'tipo': 'graos', 'nome': 'X'})
    assert resposta.status_code == 400
    assert 'Formulário expirado' in resposta.get_data(as_text=True)


# ------------------------------------------------------------------- coletas

def test_nova_coleta_mostra_erros_nos_campos(logado):
    html = logado.post('/coletas/nova', data={'_csrf': TOKEN, 'nome': ''}).get_data(as_text=True)
    assert 'Escolha o que foi fotografado.' in html
    assert 'Dê um nome à coleta.' in html
    assert 'aria-invalid="true"' in html


def test_criar_coleta_registra_quem_coletou(logado):
    coleta = criar_coleta(logado)
    assert coleta.coletor.nome == 'Ana' and coleta.tipo_amostra.codigo == 'graos'
    pagina = logado.get(f'/coletas/{coleta.id}').get_data(as_text=True)
    assert 'Coleta criada. Agora envie as fotos.' in pagina
    assert 'Nenhuma foto ainda' in pagina


def test_lista_de_coletas_filtra_por_tipo(logado):
    criar_coleta(logado, 'graos', 'Coleta de grãos')
    criar_coleta(logado, 'folhas', 'Coleta de folhas')
    html = logado.get('/coletas?tipo=folhas').get_data(as_text=True)
    assert 'Coleta de folhas' in html and 'Coleta de grãos' not in html


# -------------------------------------------------------------------- envio

def test_enviar_fotos_segmenta_e_mostra_resumo(logado):
    coleta = criar_coleta(logado)
    resposta = enviar(logado, coleta, [('bandeja.png', foto_de_graos()), ('texto.jpg', b'nao e foto')])
    assert resposta.status_code == 302 and resposta.location.endswith('#fotos')
    html = logado.get(resposta.location).get_data(as_text=True)
    assert '1 foto recebida.' in html
    assert '1 arquivo não aceito: texto.jpg (O arquivo não é uma imagem' in html
    [imagem] = coleta.imagens
    assert imagem.status == StatusImagem.PRONTA and imagem.regioes  # nos testes a fila roda na hora


def test_envio_pelo_javascript_recebe_o_destino_em_json(logado):
    coleta = criar_coleta(logado)
    resposta = enviar(logado, coleta, [('a.jpg', foto_jpeg())], **{'X-Envio-Via': 'js'})
    assert resposta.status_code == 200
    assert resposta.get_json() == {'destino': f'/coletas/{coleta.id}#fotos'}


def test_envio_sem_arquivos(logado):
    coleta = criar_coleta(logado)
    resposta = enviar(logado, coleta, [])
    assert 'Nenhum arquivo foi escolhido.' in logado.get(resposta.location).get_data(as_text=True)


def test_situacao_json_para_acompanhar_a_segmentacao(logado):
    coleta = criar_coleta(logado)
    enviar(logado, coleta, [('bandeja.png', foto_de_graos())])
    situacao = logado.get(f'/coletas/{coleta.id}/situacao.json').get_json()
    assert situacao['pendentes'] == 0 and situacao['regioes'] > 0
    assert situacao['imagens'][0]['selo'] == {'texto': 'Pronta', 'variante': 'sucesso',
                                              'icone': 'sucesso', 'animado': False}


def test_foto_e_miniatura_sao_servidas_com_cache_longo(logado):
    coleta = criar_coleta(logado)
    enviar(logado, coleta, [('a.jpg', foto_jpeg(800, 600))])
    imagem = coleta.imagens[0]
    for caminho in (f'/imagens/{imagem.id}/arquivo', f'/imagens/{imagem.id}/miniatura'):
        resposta = logado.get(caminho)
        assert resposta.status_code == 200 and resposta.mimetype == 'image/jpeg'
        assert 'max-age=31536000' in resposta.headers['Cache-Control']


def test_excluir_foto(logado):
    coleta = criar_coleta(logado)
    enviar(logado, coleta, [('a.jpg', foto_jpeg())])
    imagem_id = coleta.imagens[0].id
    resposta = logado.post(f'/imagens/{imagem_id}/excluir', data={'_csrf': TOKEN})
    pagina = html.unescape(logado.get(resposta.location).get_data(as_text=True))
    assert 'Foto "a.jpg" excluída.' in pagina
    assert db.session.get(Imagem, imagem_id) is None


def test_folhas_sem_motor_explicam_o_que_fazer(logado):
    coleta = criar_coleta(logado, 'folhas', 'Folhas lote B')
    html = logado.get(f'/coletas/{coleta.id}').get_data(as_text=True)
    assert 'Folhas ainda não têm segmentação automática' in html
    assert 'value="recortes" checked' in html
