"""Regras das contas: senhas, login, bloqueio, administração e primeiro acesso."""
import re
from datetime import timedelta

import pytest

from app.dominio import Papel, Pessoa
from app.dominio.tipos import agora_utc
from app.extensions import db
from app.servicos.contas import (
    TENTATIVAS_ANTES_DO_BLOQUEIO, ContaInvalida, FalhaDeLogin, autenticar, codigo_de_primeiro_acesso,
    criar_conta, criar_primeiro_administrador, definir_papel, desativar, existe_administrador,
    gerar_senha_provisoria, redefinir_senha, trocar_senha, validar_senha,
)
from tests.conftest import SENHA, criar_pessoa


def test_usuario_e_normalizado():
    assert Pessoa.normalizar_usuario('  Maria da Conceição ') == 'maria.da.conceicao'
    assert Pessoa.normalizar_usuario('JOSÉ_2') == 'jose_2'


def test_senha_provisoria_e_facil_de_ditar_e_valida():
    senha = gerar_senha_provisoria()
    assert re.fullmatch(r'[a-z]+-[a-z]+-\d{4}', senha)
    validar_senha(senha)  # não pode ser recusada pelas próprias regras


@pytest.mark.parametrize('senha, trecho', [
    ('curta', 'pelo menos 8'), ('12345678', 'fácil demais'), ('aaaaaaaaaa', 'fácil demais'),
    ('senha-da-ana-123', 'nome de usuário'),
])
def test_senhas_fracas_sao_recusadas(senha, trecho):
    with pytest.raises(ContaInvalida, match=trecho):
        validar_senha(senha, usuario='ana')


def test_conta_criada_pelo_administrador_tem_senha_provisoria(app):
    pessoa, senha = criar_conta('Bia Souza', '', Papel.MEMBRO)
    assert pessoa.usuario == 'bia.souza' and pessoa.precisa_trocar_senha and senha
    assert pessoa.senha_hash != senha and senha not in pessoa.senha_hash  # nunca em texto
    assert autenticar('bia.souza', senha) is pessoa


def test_usuario_repetido_e_recusado(app):
    criar_pessoa('Ana')
    with pytest.raises(ContaInvalida, match='já existe'):
        criar_conta('Outra Ana', 'ANA')


def test_mesma_mensagem_para_usuario_inexistente_e_senha_errada(app):
    criar_pessoa('Ana')
    with pytest.raises(FalhaDeLogin) as inexistente:
        autenticar('ninguem', SENHA)
    with pytest.raises(FalhaDeLogin) as senha_errada:
        autenticar('ana', 'senha-errada-99')
    assert str(inexistente.value) == str(senha_errada.value) == 'Usuário ou senha incorretos.'


def test_bloqueio_depois_de_varias_tentativas_erradas(app):
    ana = criar_pessoa('Ana')
    for _ in range(TENTATIVAS_ANTES_DO_BLOQUEIO):
        with pytest.raises(FalhaDeLogin):
            autenticar('ana', 'errada-errada')
    with pytest.raises(FalhaDeLogin, match='Muitas tentativas'):
        autenticar('ana', SENHA)  # nem a senha certa entra durante o bloqueio
    ana.bloqueada_ate = agora_utc() - timedelta(seconds=1)  # o tempo passou
    assert autenticar('ana', SENHA) is ana


def test_conta_desativada_nao_entra(app, administracao):
    ana = criar_pessoa('Ana')
    desativar(ana, feito_por=administracao)
    with pytest.raises(FalhaDeLogin, match='desativada'):
        autenticar('ana', SENHA)


def test_trocar_senha_exige_a_atual_e_desconecta_outros_aparelhos(app):
    ana = criar_pessoa('Ana')
    versao = ana.versao_sessao
    with pytest.raises(ContaInvalida, match='atual está incorreta'):
        trocar_senha(ana, 'errada', 'nova-senha-da-fazenda')
    trocar_senha(ana, SENHA, 'nova-senha-da-fazenda')
    assert ana.versao_sessao == versao + 1 and not ana.precisa_trocar_senha
    assert autenticar('ana', 'nova-senha-da-fazenda') is ana


def test_redefinir_senha_gera_provisoria_e_desbloqueia(app):
    ana = criar_pessoa('Ana')
    ana.bloqueada_ate = agora_utc() + timedelta(minutes=5)
    senha = redefinir_senha(ana)
    assert ana.precisa_trocar_senha and ana.bloqueada_ate is None
    assert autenticar('ana', senha) is ana


def test_plataforma_nunca_fica_sem_administrador(app, administracao):
    with pytest.raises(ContaInvalida, match='única conta de administrador'):
        definir_papel(administracao, Papel.MEMBRO)
    with pytest.raises(ContaInvalida, match='própria conta'):
        desativar(administracao, feito_por=administracao)
    outra = criar_pessoa('Outra Admin', Papel.ADMINISTRADOR)
    definir_papel(administracao, Papel.MEMBRO)  # agora pode: existe outra administração
    assert existe_administrador() and outra.eh_administrador


def test_primeiro_administrador_exige_o_codigo(app):
    pasta = app.config['PASTA_DADOS']
    codigo = codigo_de_primeiro_acesso(pasta)
    assert re.fullmatch(r'\d{4}-\d{4}', codigo)
    assert codigo_de_primeiro_acesso(pasta) == codigo  # o mesmo até ser usado
    with pytest.raises(ContaInvalida, match='Código incorreto'):
        criar_primeiro_administrador(pasta, '0000-0000' if codigo != '0000-0000' else '1111-1111',
                                     'Chefe', 'chefe', SENHA)
    pessoa = criar_primeiro_administrador(pasta, codigo, 'Chefe', 'chefe', SENHA)
    db.session.commit()
    assert pessoa.eh_administrador and not pessoa.precisa_trocar_senha
    assert codigo_de_primeiro_acesso(pasta) is None  # não serve mais
    with pytest.raises(ContaInvalida, match='Já existe um administrador'):
        criar_primeiro_administrador(pasta, codigo, 'Intruso', 'intruso', SENHA)
