"""Excluir coleta (com fotos e anotações) e excluir conta (apagar ou tornar anônima)."""
import pytest

from app.armazenamento import armazenamento_de_imagens
from app.dominio import (
    Anotacao, Coleta, Imagem, JobSegmentacao, Papel, Pessoa, Regiao, StatusImagem,
)
from app.extensions import db
from app.servicos.anotacoes import anotar_regiao
from app.servicos.coletas import ExclusaoRecusada, excluir_coleta
from app.servicos.contas import ContaInvalida, autenticar, excluir_conta, FalhaDeLogin
from app.servicos.ingestao import receber_foto
from app.servicos.segmentacao import agendar_segmentacao, executar_job
from tests.conftest import SENHA, TOKEN, classe, criar_pessoa, entrar_como, tipo
from tests.fabrica_imagens import foto_de_graos, foto_jpeg


def coleta_com_foto(nome='Talhão 3', coletor=None, conteudo=None, segmentar=True) -> Coleta:
    coleta = Coleta(nome=nome, tipo_amostra=tipo('graos'), coletor=coletor)
    db.session.add(coleta)
    db.session.flush()
    imagem = receber_foto(coleta, conteudo or foto_de_graos(linhas=2, colunas=2), 'bandeja.png').imagem
    job = agendar_segmentacao(imagem) if segmentar else None
    db.session.commit()
    if job:
        executar_job(job.id)
    return coleta


def caminho_da_foto(coleta):
    imagem = coleta.imagens[0]
    return armazenamento_de_imagens().caminho(imagem.hash_sha256, imagem.extensao)


def anotar_uma(coleta, pessoa=None):
    anotar_regiao(coleta.imagens[0].regioes[0], classe('graos', 'sem_defeito'), pessoa=pessoa)
    db.session.commit()


def contar(modelo):
    return db.session.query(modelo).count()


# ------------------------------------------------------------ excluir coleta

def test_administracao_exclui_coleta_com_tudo_dentro(logado_admin, administracao):
    coleta = coleta_com_foto()
    anotar_uma(coleta, administracao)
    arquivo = caminho_da_foto(coleta)
    assert arquivo.exists() and contar(Regiao) > 0 and contar(JobSegmentacao) == 1

    # Com anotações, precisa digitar o nome (maiúsculas e espaços não importam).
    errado = logado_admin.post(f'/coletas/{coleta.id}/excluir', data={'_csrf': TOKEN, 'confirmacao': 'talhão'})
    assert errado.status_code == 302 and errado.location.endswith('#excluir')
    assert db.session.get(Coleta, coleta.id) is not None

    resposta = logado_admin.post(f'/coletas/{coleta.id}/excluir',
                                 data={'_csrf': TOKEN, 'confirmacao': '  TALHÃO   3 '}, follow_redirects=True)
    assert 'Coleta &#34;Talhão 3&#34; excluída, com 1 foto.' in resposta.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(Coleta, coleta.id) is None
    for modelo in (Imagem, Regiao, Anotacao, JobSegmentacao):
        assert contar(modelo) == 0, modelo.__name__
    assert not arquivo.exists()


def test_foto_usada_em_outra_coleta_fica_no_disco(app, administracao):
    conteudo = foto_jpeg()
    primeira = coleta_com_foto('A', conteudo=conteudo, segmentar=False)
    coleta_com_foto('B', conteudo=conteudo, segmentar=False)
    arquivo = caminho_da_foto(primeira)
    apagar_arquivos = excluir_coleta(primeira, administracao)
    db.session.commit()
    apagar_arquivos()
    assert arquivo.exists()  # a coleta B ainda usa a mesma foto


def test_quem_criou_exclui_enquanto_ninguem_anotou(cliente, administracao):
    ana = criar_pessoa('Ana')
    coleta = coleta_com_foto(coletor=ana)
    resposta = entrar_como(cliente, ana).post(f'/coletas/{coleta.id}/excluir', data={'_csrf': TOKEN})
    assert resposta.location == '/coletas'  # sem anotações: não precisa digitar o nome
    assert db.session.get(Coleta, coleta.id) is None


def test_membro_nao_exclui_coleta_anotada_nem_a_de_outra_pessoa(app, administracao):
    ana, bia = criar_pessoa('Ana'), criar_pessoa('Bia')
    anotada = coleta_com_foto('Anotada', coletor=ana)
    anotar_uma(anotada, bia)
    with pytest.raises(ExclusaoRecusada, match='Só a administração'):
        excluir_coleta(anotada, ana, confirmacao='Anotada')
    de_outra = coleta_com_foto('Da Bia', coletor=bia)
    with pytest.raises(ExclusaoRecusada, match='Só quem criou'):
        excluir_coleta(de_outra, ana)


def test_nao_exclui_durante_a_segmentacao(app, administracao):
    coleta = coleta_com_foto(segmentar=False)
    coleta.imagens[0].status = StatusImagem.SEGMENTANDO
    with pytest.raises(ExclusaoRecusada, match='sendo segmentada'):
        excluir_coleta(coleta, administracao)


def test_pagina_da_coleta_explica_quem_pode_excluir(cliente, administracao):
    ana = criar_pessoa('Ana')
    coleta = coleta_com_foto(coletor=administracao)
    html = entrar_como(cliente, ana).get(f'/coletas/{coleta.id}').get_data(as_text=True)
    assert 'Só quem criou esta coleta, ou a administração, pode excluí-la.' in html
    assert 'id="dialogo-excluir-coleta"' not in html
    html = entrar_como(cliente, administracao).get(f'/coletas/{coleta.id}').get_data(as_text=True)
    assert 'id="dialogo-excluir-coleta"' in html
    assert 'name="confirmacao"' not in html  # sem anotações, não pede o nome


def test_excluir_coleta_exige_csrf(logado_admin):
    coleta = coleta_com_foto(segmentar=False)
    assert logado_admin.post(f'/coletas/{coleta.id}/excluir').status_code == 400


# ------------------------------------------------------------- excluir conta

def test_conta_nunca_usada_some_por_completo(logado_admin):
    pessoa = criar_pessoa('Carlos')
    resposta = logado_admin.post(f'/pessoas/{pessoa.id}/excluir', data={'_csrf': TOKEN}, follow_redirects=True)
    assert 'Conta de Carlos excluída.' in resposta.get_data(as_text=True)
    assert db.session.get(Pessoa, pessoa.id) is None


def test_conta_com_trabalho_vira_anonima_e_o_trabalho_fica(logado_admin, cliente, app):
    dora = criar_pessoa('Dora Lima')
    coleta = coleta_com_foto(coletor=dora)
    anotar_uma(coleta, dora)
    outro = app.test_client()
    entrar_como(outro, dora)
    assert outro.get('/').status_code == 200

    logado_admin.post(f'/pessoas/{dora.id}/excluir', data={'_csrf': TOKEN})
    db.session.expire_all()
    removida = db.session.get(Pessoa, dora.id)
    assert removida.nome == f'Pessoa removida nº {dora.id}' and removida.usuario == f'removida.{dora.id}'
    assert removida.senha_hash is None and not removida.ativa and removida.removida_em
    assert db.session.query(Anotacao).filter_by(pessoa_id=dora.id).count() == 1  # a pesquisa não perde nada
    assert outro.get('/').status_code == 302  # saiu de todos os aparelhos
    with pytest.raises(FalhaDeLogin):
        autenticar('dora.lima', SENHA)
    criar_pessoa('Dora Lima')  # o usuário antigo fica livre para outra conta

    pagina = logado_admin.get('/pessoas').get_data(as_text=True)
    assert f'removida.{dora.id}' not in pagina and '1 conta excluída não aparece aqui' in pagina
    assert logado_admin.post(f'/pessoas/{dora.id}/excluir', data={'_csrf': TOKEN}).status_code == 404


def test_nao_exclui_a_propria_conta_nem_a_ultima_administracao(app, administracao):
    with pytest.raises(ContaInvalida, match='própria conta'):
        excluir_conta(administracao, feito_por=administracao)
    outra = criar_pessoa('Outra Admin', Papel.ADMINISTRADOR)
    excluir_conta(outra, feito_por=administracao)  # havia duas: pode


def test_so_a_administracao_exclui_contas(logado):
    pessoa = criar_pessoa('Carlos')
    assert logado.post(f'/pessoas/{pessoa.id}/excluir', data={'_csrf': TOKEN}).status_code == 403


def test_pessoas_mostra_o_dialogo_certo_para_cada_conta(logado_admin):
    nova, com_trabalho = criar_pessoa('Nova'), criar_pessoa('Com Trabalho')
    anotar_uma(coleta_com_foto(), com_trabalho)
    html = logado_admin.get('/pessoas').get_data(as_text=True)
    assert f'data-acao="/pessoas/{nova.id}/excluir"' in html
    trecho_nova = html[html.index(f'data-acao="/pessoas/{nova.id}/excluir"') - 200:]
    assert 'dialogo-apagar-conta' in trecho_nova[:260]
    trecho = html[html.index(f'data-acao="/pessoas/{com_trabalho.id}/excluir"') - 200:]
    assert 'dialogo-anonimizar-conta' in trecho[:260]
