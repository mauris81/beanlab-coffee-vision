"""Painel (página inicial): os números, as listas de pendências e a atividade."""
import re
from datetime import date, timedelta

import pytest
from sqlalchemy import event

from app.dominio import Coleta, Imagem, OrigemImagem, OrigemRegiao, Papel, Regiao, StatusImagem
from app.extensions import db
from app.dominio.tipos import agora_utc
from app.servicos.anotacoes import CONFIANCA_DUVIDA, anotar_regiao
from app.servicos.painel import (
    Numeros, anotacoes_por_pessoa, atividade_por_dia, contagem_por_classe, fatias_do_tipo,
    montar_painel, numeros_por_tipo, resumo_das_coletas,
)
from tests.conftest import classe, criar_pessoa, entrar_como, tipo

_hashes = iter(range(10_000))


def nova_coleta(tipo_codigo='graos', nome='Coleta', fotos=(StatusImagem.PRONTA,), regioes_por_foto=3) -> Coleta:
    coleta = Coleta(nome=nome, tipo_amostra=tipo(tipo_codigo))
    for status in fotos:
        imagem = Imagem(coleta=coleta, hash_sha256=f'{next(_hashes):064x}', extensao='jpg',
                        nome_original='foto.jpg', largura=1000, altura=800, tamanho_bytes=10,
                        origem=OrigemImagem.ARQUIVO, status=status)
        for i in range(regioes_por_foto if status == StatusImagem.PRONTA else 0):
            imagem.regioes.append(Regiao.do_poligono([[i * 60, 0], [i * 60 + 50, 0], [i * 60 + 50, 50], [i * 60, 50]],
                                                     origem=OrigemRegiao.AUTOMATICA))
    db.session.add(coleta)
    db.session.commit()
    return coleta


def regioes_de(coleta: Coleta) -> list[Regiao]:
    return [r for imagem in coleta.imagens for r in imagem.regioes]


def anotar(regiao, tipo_codigo, classe_codigo, pessoa=None, duvida=False, dias_atras=0):
    anotacao = anotar_regiao(regiao, classe(tipo_codigo, classe_codigo), pessoa=pessoa,
                             confianca=CONFIANCA_DUVIDA if duvida else None)
    anotacao.criada_em = agora_utc() - timedelta(days=dias_atras)
    db.session.commit()
    return anotacao


# ------------------------------------------------------------------ números

def test_numeros_por_tipo_seguem_as_regras_da_anotacao(app):
    graos = nova_coleta('graos', fotos=(StatusImagem.PRONTA, StatusImagem.ERRO, StatusImagem.AGUARDANDO))
    r1, r2, r3 = regioes_de(graos)
    anotar(r1, 'graos', 'ardido')
    anotar(r1, 'graos', 'sem_defeito')           # mudou de ideia: continua 1 região anotada
    anotar(r2, 'graos', 'preto', duvida=True)
    nova_coleta('folhas', fotos=())         # coleta sem fotos

    numeros = numeros_por_tipo()
    assert numeros[tipo('graos').id] == Numeros(coletas=1, fotos=3, fotos_na_fila=1, fotos_com_erro=1,
                                                 regioes=3, anotadas=2, duvidas=1)
    assert numeros[tipo('graos').id].pendentes == 1 and numeros[tipo('graos').id].percentual == 66.7
    assert numeros[tipo('folhas').id] == Numeros(coletas=1)
    assert tipo('flores').id not in numeros


def test_duvida_resolvida_deixa_de_contar(app):
    coleta = nova_coleta()
    regiao = regioes_de(coleta)[0]
    anotar(regiao, 'graos', 'ardido', duvida=True)
    anotar(regiao, 'graos', 'ardido')  # revisou e confirmou
    assert numeros_por_tipo()[tipo('graos').id].duvidas == 0


def test_soma_dos_numeros(app):
    assert Numeros(coletas=1, regioes=4, anotadas=1) + Numeros(coletas=2, regioes=6, anotadas=4) \
        == Numeros(coletas=3, regioes=10, anotadas=5)


# ------------------------------------------------------------------ classes

def test_distribuicao_usa_a_classe_vigente(app):
    r1, r2, r3 = regioes_de(nova_coleta())
    anotar(r1, 'graos', 'ardido')
    anotar(r1, 'graos', 'sem_defeito')
    anotar(r2, 'graos', 'sem_defeito')
    anotar(r3, 'graos', 'preto')
    contagem = contagem_por_classe()
    assert contagem[classe('graos', 'sem_defeito').id] == 2
    assert contagem[classe('graos', 'preto').id] == 1
    assert classe('graos', 'ardido').id not in contagem

    fatias = {f.classe.codigo: f for f in fatias_do_tipo(tipo('graos'), contagem)}
    assert fatias['sem_defeito'].percentual == 66.7 and fatias['preto'].percentual == 33.3
    assert fatias['ardido'].quantidade == 0  # classe ativa aparece mesmo zerada


def test_classe_desativada_so_aparece_se_tiver_regioes(app):
    r1, *_ = regioes_de(nova_coleta())
    anotar(r1, 'graos', 'preto')
    for codigo in ('preto', 'ardido'):
        classe('graos', codigo).ativa = False
    db.session.commit()
    codigos = [f.classe.codigo for f in fatias_do_tipo(tipo('graos'), contagem_por_classe())]
    assert 'preto' in codigos and 'ardido' not in codigos


# ------------------------------------------------------------------ coletas

def test_continuar_anotando_comeca_pela_coleta_mexida_por_ultimo(app, administracao):
    antiga = nova_coleta(nome='Antiga')
    recente = nova_coleta(nome='Recente')
    nova_coleta(nome='Nova, sem anotação')
    completa = nova_coleta(nome='Completa', regioes_por_foto=1)
    anotar(regioes_de(antiga)[0], 'graos', 'sem_defeito', dias_atras=0)
    anotar(regioes_de(recente)[0], 'graos', 'sem_defeito', dias_atras=3)
    anotar(regioes_de(completa)[0], 'graos', 'sem_defeito')
    antiga.criada_em = recente.criada_em = agora_utc() - timedelta(days=10)
    db.session.commit()

    painel = montar_painel([tipo('graos')], None, administracao)
    nomes = [c.coleta.nome for c in painel.para_continuar]
    # "Antiga" foi anotada hoje: vem primeiro. "Completa" não tem pendência.
    assert nomes == ['Antiga', 'Nova, sem anotação', 'Recente']
    assert painel.coletas_pendentes == 3


def test_o_que_precisa_de_atencao(app, administracao):
    com_erro = nova_coleta(nome='Com erro', fotos=(StatusImagem.PRONTA, StatusImagem.ERRO))
    anotar(regioes_de(com_erro)[0], 'graos', 'preto', duvida=True)
    nova_coleta(nome='Vazia', fotos=())
    painel = montar_painel([tipo('graos')], None, administracao)
    assert [c.coleta.nome for c in painel.com_erro] == ['Com erro']
    assert [(c.coleta.nome, c.duvidas) for c in painel.com_duvidas] == [('Com erro', 1)]
    assert [c.coleta.nome for c in painel.sem_fotos] == ['Vazia']
    assert painel.precisa_de_atencao


def test_filtro_por_tipo(app, administracao):
    nova_coleta('graos', nome='Grãos 1')
    nova_coleta('folhas', nome='Folhas 1')
    assert [c.coleta.nome for c in resumo_das_coletas(tipo('folhas').id)] == ['Folhas 1']
    painel = montar_painel([tipo('graos'), tipo('folhas')], tipo('folhas'), administracao)
    assert painel.numeros.coletas == 1 and [c.coleta.nome for c in painel.para_continuar] == ['Folhas 1']
    assert [f.classe.tipo_amostra.codigo for f in painel.fatias] == ['folhas'] * len(painel.fatias)


# ---------------------------------------------------------------- atividade

def test_atividade_por_dia(app):
    ana, bia = criar_pessoa('Ana'), criar_pessoa('Bia')
    r1, r2, r3 = regioes_de(nova_coleta())
    anotar(r1, 'graos', 'sem_defeito', pessoa=ana)
    anotar(r2, 'graos', 'sem_defeito', pessoa=bia)
    anotar(r3, 'graos', 'sem_defeito', pessoa=ana, dias_atras=2)
    anotar(r3, 'graos', 'preto', pessoa=ana, dias_atras=20)  # fora da janela de 14 dias

    dias = atividade_por_dia()
    assert len(dias) == 14 and dias[-1].data == date.today()
    assert dias[-1].anotacoes == 2 and dias[-3].anotacoes == 1
    assert sum(d.anotacoes for d in dias) == 3
    assert atividade_por_dia(7, pessoa_id=bia.id)[-1].anotacoes == 1
    assert sum(d.anotacoes for d in atividade_por_dia(tipo_id=tipo('folhas').id)) == 0
    assert anotacoes_por_pessoa() == [('Ana', 3), ('Bia', 1)]  # 30 dias


def test_painel_nao_faz_uma_consulta_por_coleta(app, administracao):
    """Com 3 ou 30 coletas, o painel faz o mesmo número de consultas ao banco."""
    def consultas_do_painel():
        contador = []
        ouvir = lambda *args: contador.append(1)  # noqa: E731
        event.listen(db.engine, 'before_cursor_execute', ouvir)
        try:
            db.session.expire_all()
            montar_painel([tipo('graos')], None, administracao, com_equipe=True)
        finally:
            event.remove(db.engine, 'before_cursor_execute', ouvir)
        return len(contador)

    for i in range(3):
        anotar(regioes_de(nova_coleta(nome=f'A{i}'))[0], 'graos', 'sem_defeito')
    poucas = consultas_do_painel()
    for i in range(27):
        anotar(regioes_de(nova_coleta(nome=f'B{i}'))[0], 'graos', 'sem_defeito')
    assert consultas_do_painel() == poucas


# -------------------------------------------------------------------- página

def test_pagina_resume_em_uma_frase(logado):
    r1, *_ = regioes_de(nova_coleta(nome='Talhão 3'))
    anotar(r1, 'graos', 'sem_defeito')
    html = logado.get('/').get_data(as_text=True)
    assert 'Faltam 2 regiões para anotar em 1 coleta.' in html
    assert re.search(r'href="/coletas/\d+/anotar"', html)  # "Continuar anotando"
    assert 'Olá, Ana' in html


def test_primeira_vez_explica_como_funciona(logado):
    html = logado.get('/').get_data(as_text=True)
    assert 'Nenhuma coleta ainda. Crie a primeira para começar.' in html
    assert 'Como funciona' in html


def test_tudo_anotado(logado):
    regiao, = regioes_de(nova_coleta(regioes_por_foto=1))
    anotar(regiao, 'graos', 'sem_defeito')
    assert 'Tudo anotado: 1 região. Bom trabalho!' in logado.get('/').get_data(as_text=True)


def test_quem_anotou_so_para_a_administracao(cliente, administracao):
    membro = criar_pessoa('Carla')
    regiao, *_ = regioes_de(nova_coleta())
    anotar(regiao, 'graos', 'sem_defeito', pessoa=membro)
    assert 'Quem anotou' not in entrar_como(cliente, membro).get('/').get_data(as_text=True)
    html = entrar_como(cliente, administracao).get('/').get_data(as_text=True)
    assert 'Quem anotou' in html and 'Carla' in html


def test_duvidas_levam_para_a_revisao_no_lote(logado):
    coleta = nova_coleta(nome='Dúvidas')
    r1, r2, _ = regioes_de(coleta)
    anotar(r1, 'graos', 'preto', duvida=True)
    anotar(r2, 'graos', 'sem_defeito')
    html = logado.get('/').get_data(as_text=True)
    endereco = f'/coletas/{coleta.id}/lote?mostrar=duvidas'
    assert endereco in html
    lote = logado.get(endereco).get_data(as_text=True)
    assert 'Em dúvida (1)' in lote
    assert lote.count('name="regioes"') == 1  # só a região em dúvida


@pytest.mark.parametrize('caminho', ['/?tipo=graos', '/?tipo=inexistente'])
def test_filtro_do_painel(logado, caminho):
    assert logado.get(caminho).status_code == 200


def test_guia_visual_saiu_do_menu_e_foi_para_o_rodape(logado):
    html = logado.get('/').get_data(as_text=True)
    menu = html[html.index('<nav class="navegacao"'):html.index('</nav>')]
    assert 'Guia visual' not in menu
    assert 'href="/guia-visual"' in html[html.index('<footer'):]
