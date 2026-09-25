"""Login nas telas: porta de entrada, primeiro acesso, minha conta e administração."""
import html
import re

import pytest

from app.dominio import Papel, Pessoa
from app.extensions import db
from app.servicos.contas import codigo_de_primeiro_acesso
from tests.conftest import SENHA, TOKEN, criar_pessoa, entrar_como


def _com_csrf(cliente):
    with cliente.session_transaction() as sessao:
        sessao['_csrf'] = TOKEN
    return cliente


def _entrar(cliente, usuario, senha=SENHA, **extra):
    return _com_csrf(cliente).post('/entrar', data={'_csrf': TOKEN, 'usuario': usuario, 'senha': senha, **extra})


# --------------------------------------------------------------- porta de entrada

def test_sem_administrador_tudo_leva_ao_primeiro_acesso(cliente):
    for caminho in ('/', '/coletas', '/entrar'):
        assert cliente.get(caminho).location == '/primeiro-acesso'
    assert cliente.get('/api/saude').status_code == 200  # monitoramento continua funcionando


@pytest.mark.parametrize('caminho', ['/', '/coletas', '/coletas/nova', '/guia-visual', '/conta', '/pessoas'])
def test_paginas_exigem_login(cliente, administracao, caminho):
    resposta = cliente.get(caminho)
    assert resposta.status_code == 302 and resposta.location.startswith('/entrar')


def test_api_sem_login_responde_401_em_json(cliente, administracao):
    resposta = cliente.get('/api/coletas/1/regioes')
    assert resposta.status_code == 401 and 'Entre de novo' in resposta.get_json()['erro']


def test_tela_de_entrar_nao_lista_as_pessoas(cliente, administracao):
    criar_pessoa('Ana Secreta')
    assert 'Ana Secreta' not in cliente.get('/entrar').get_data(as_text=True)


# -------------------------------------------------------------------- entrar/sair

def test_entrar_e_voltar_para_onde_estava(cliente, administracao):
    criar_pessoa('Ana')
    resposta = _entrar(cliente, 'ANA', proximo='/coletas/nova')
    assert resposta.status_code == 302 and resposta.location == '/coletas/nova'
    assert cliente.get('/coletas/nova').status_code == 200


def test_senha_errada_mostra_mensagem(cliente, administracao):
    criar_pessoa('Ana')
    resposta = _entrar(cliente, 'ana', 'senha-errada-99')
    assert resposta.status_code == 401 and 'Usuário ou senha incorretos.' in resposta.get_data(as_text=True)


@pytest.mark.parametrize('destino', ['https://site-malicioso.com', '//site-malicioso.com', 'javascript:alert(1)'])
def test_entrar_nao_redireciona_para_outro_site(cliente, administracao, destino):
    criar_pessoa('Ana')
    assert _entrar(cliente, 'ana', proximo=destino).location == '/'


def test_sair_encerra_a_sessao(logado):
    resposta = logado.post('/sair', data={'_csrf': TOKEN})
    assert resposta.location == '/entrar'
    assert logado.get('/').location.startswith('/entrar')


def test_sessao_nova_a_cada_login(cliente, administracao):
    """Evita fixação de sessão: o que estava na sessão antes do login não sobrevive."""
    criar_pessoa('Ana')
    with cliente.session_transaction() as sessao:
        sessao['plantado'] = 'por-um-atacante'
    _entrar(cliente, 'ana')
    with cliente.session_transaction() as sessao:
        assert 'plantado' not in sessao and 'pessoa_id' in sessao


# ---------------------------------------------------------------- primeiro acesso

def test_primeiro_acesso_cria_administracao(cliente, app):
    codigo = codigo_de_primeiro_acesso(app.config['PASTA_DADOS'])
    _com_csrf(cliente)
    dados = {'_csrf': TOKEN, 'nome': 'Chefe', 'usuario': 'chefe', 'senha': SENHA, 'confirmacao': SENHA}
    errado = cliente.post('/primeiro-acesso', data={**dados, 'codigo': '9999-9999' if codigo != '9999-9999' else '0'})
    assert 'Código incorreto' in errado.get_data(as_text=True)
    certo = cliente.post('/primeiro-acesso', data={**dados, 'codigo': codigo})
    assert certo.location == '/pessoas'
    assert cliente.get('/pessoas').status_code == 200  # já entra logado
    assert cliente.get('/primeiro-acesso').location == '/entrar'  # não dá para repetir


# ------------------------------------------------------------ senha provisória

def test_senha_provisoria_obriga_a_trocar_antes_de_tudo(logado_admin, cliente):
    resposta = logado_admin.post('/pessoas', data={'_csrf': TOKEN, 'nome': 'Bia', 'usuario': '', 'papel': 'membro'})
    senha = re.search(r'class="senha-provisoria">([^<]+)<', resposta.get_data(as_text=True)).group(1)

    outro = cliente.application.test_client()
    resposta = _entrar(outro, 'bia', senha)
    assert resposta.location == '/conta'
    assert outro.get('/coletas').location == '/conta'  # antes de trocar, só "Minha conta"
    _com_csrf(outro)  # o login renovou a sessão; a página nova traria o código CSRF novo
    resposta = outro.post('/conta', data={'_csrf': TOKEN, 'senha_atual': senha,
                                          'senha_nova': 'minha-senha-do-cafe', 'confirmacao': 'minha-senha-do-cafe'})
    assert resposta.location == '/'
    assert outro.get('/coletas').status_code == 200


def test_trocar_senha_desconecta_os_outros_aparelhos(app, administracao):
    ana = criar_pessoa('Ana')
    celular, computador = app.test_client(), app.test_client()
    _entrar(celular, 'ana')
    _entrar(computador, 'ana')
    _com_csrf(computador)  # o login renovou a sessão (e o código CSRF)
    computador.post('/conta', data={'_csrf': TOKEN, 'senha_atual': SENHA,
                                    'senha_nova': 'outra-senha-boa-1', 'confirmacao': 'outra-senha-boa-1'})
    assert computador.get('/coletas').status_code == 200   # quem trocou continua
    assert celular.get('/coletas').location.startswith('/entrar')  # o outro aparelho saiu
    assert ana.versao_sessao > 1


# ------------------------------------------------------------------ administração

def test_membro_nao_acessa_a_administracao(logado):
    assert logado.get('/pessoas').status_code == 403
    assert logado.post('/pessoas', data={'_csrf': TOKEN, 'nome': 'X'}).status_code == 403


def test_menu_some_enquanto_a_senha_for_provisoria(app, administracao):
    from app.servicos.contas import redefinir_senha
    ana = criar_pessoa('Ana')
    redefinir_senha(ana)
    db.session.commit()
    pagina = entrar_como(app.test_client(), ana).get('/conta').get_data(as_text=True)
    assert 'class="navegacao"' not in pagina and 'navegacao-inferior' not in pagina


def test_ultimo_acesso_aparece_no_horario_local():
    from datetime import datetime, timezone
    from app.web.apresentacao import hora_local
    utc = datetime(2026, 3, 12, 12, 0)
    esperado = utc.replace(tzinfo=timezone.utc).astimezone().strftime('%d/%m/%Y %H:%M')
    assert hora_local(utc) == esperado and hora_local(None) == ''


def test_menu_mostra_pessoas_so_para_a_administracao(logado, app, administracao):
    assert 'href="/pessoas"' not in logado.get('/').get_data(as_text=True)
    admin = entrar_como(app.test_client(), administracao)
    assert 'href="/pessoas"' in admin.get('/').get_data(as_text=True)


def test_administracao_cria_conta_e_a_senha_aparece_uma_vez(logado_admin):
    resposta = logado_admin.post('/pessoas', data={'_csrf': TOKEN, 'nome': 'Carlos Lima', 'usuario': '', 'papel': 'membro'})
    pagina = resposta.get_data(as_text=True)
    # Regressão: o topo da página sobrescrevia "pessoa" e mostrava o usuário de quem criou.
    assert '<code>carlos.lima</code>' in pagina and 'admin.teste</code>' not in pagina
    assert 'senha-provisoria' in pagina
    assert 'senha-provisoria' not in logado_admin.get('/pessoas').get_data(as_text=True)
    pessoa = db.session.scalars(db.select(Pessoa).filter_by(usuario='carlos.lima')).one()
    assert pessoa.precisa_trocar_senha and pessoa.papel == Papel.MEMBRO


def test_desativar_conta_desconecta_na_hora(app, logado_admin):
    ana = criar_pessoa('Ana')
    celular = app.test_client()
    _entrar(celular, 'ana')
    logado_admin.post(f'/pessoas/{ana.id}/desativar', data={'_csrf': TOKEN})
    assert celular.get('/coletas').location.startswith('/entrar')
    pagina = html.unescape(logado_admin.get('/pessoas').get_data(as_text=True))
    assert 'Desativada' in pagina


def test_nao_da_para_tirar_a_ultima_administracao(logado_admin, administracao):
    resposta = logado_admin.post(f'/pessoas/{administracao.id}/papel', data={'_csrf': TOKEN, 'papel': 'membro'})
    pagina = html.unescape(logado_admin.get(resposta.location).get_data(as_text=True))
    assert 'única conta de administrador' in pagina
    assert administracao.eh_administrador
