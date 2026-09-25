"""Fase 5: recortes, situação das regiões, lote, desfazer, API e páginas de anotação."""
import html

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.dominio import Anotacao, Pessoa
from app.extensions import db
from app.servicos.anotacoes import (
    anotar_em_lote, anotar_regiao, desfazer_anotacoes, situacao_das_regioes,
)
from app.servicos.recortes import LADO_RECORTE, caixa_com_margem, caminho_do_recorte, recorte_da_regiao
from tests.conftest import classe, criar_coleta
from tests.conftest import TOKEN, criar_pessoa
from tests.test_web_coletas import criar_coleta as criar_coleta_web, enviar
from tests.fabrica_imagens import foto_de_graos


def pessoa(nome='Ana') -> Pessoa:
    return criar_pessoa(nome)


# ------------------------------------------------------------------ recortes

def test_caixa_com_margem_nao_sai_da_foto():
    assert caixa_com_margem([0, 0, 40, 20], 100, 100) == (0, 0, 50, 30)
    assert caixa_com_margem([90, 90, 10, 10], 100, 100) == (84, 84, 100, 100)


def test_recorte_e_gerado_ampliado_e_guardado_em_cache(logado):
    coleta = criar_coleta_web(logado)
    enviar(logado, coleta, [('bandeja.png', foto_de_graos())])
    regiao = coleta.imagens[0].regioes[0]
    caminho = recorte_da_regiao(regiao)
    with Image.open(caminho) as recorte:
        assert max(recorte.size) == LADO_RECORTE  # grãos pequenos são ampliados
    # todas as regiões da foto foram geradas de uma vez
    assert all(caminho_do_recorte(r).is_file() for r in coleta.imagens[0].regioes)
    antes = caminho.stat().st_mtime_ns
    recorte_da_regiao(regiao)
    assert caminho.stat().st_mtime_ns == antes  # não refaz


def test_muitos_pedidos_simultaneos_de_recorte_da_mesma_foto(app, logado):
    """Regressão: a tela em lote pede dezenas de recortes ao mesmo tempo. Antes, todos
    gravavam no mesmo arquivo temporário e o Windows recusava ('arquivo em uso')."""
    import threading
    coleta = criar_coleta_web(logado)
    enviar(logado, coleta, [('bandeja.png', foto_de_graos(semente=5))])
    regioes = list(coleta.imagens[0].regioes)
    [r.bbox for r in regioes], regioes[0].imagem.regioes  # carrega tudo antes das threads
    erros = []

    def pedir(regiao):
        with app.app_context():
            try:
                recorte_da_regiao(regiao)
            except Exception as erro:  # noqa: BLE001
                erros.append(repr(erro))

    threads = [threading.Thread(target=pedir, args=(regioes[i % len(regioes)],)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert erros == []
    pasta = caminho_do_recorte(regioes[0]).parent
    assert not list(pasta.glob('*.parcial')), 'não pode sobrar temporário'
    for regiao in regioes:
        with Image.open(caminho_do_recorte(regiao)) as recorte:
            recorte.verify()  # arquivo completo, não pela metade


# -------------------------------------------------------------- serviços

def test_situacao_das_regioes_mostra_a_anotacao_vigente(app):
    coleta = criar_coleta(num_regioes=3)
    r1, r2, _ = coleta.imagens[0].regioes
    anotar_regiao(r1, classe('graos', 'verde'))
    anotar_regiao(r1, classe('graos', 'ardido'), confianca=0.5, observacao='manchado')
    anotar_regiao(r2, classe('graos', 'preto'))
    db.session.commit()

    situacao = {s.id: s for s in situacao_das_regioes(coleta.id)}
    assert (situacao[r1.id].classe, situacao[r1.id].duvida, situacao[r1.id].observacao) == ('ardido', True, 'manchado')
    assert situacao[r2.id].classe == 'preto' and not situacao[r2.id].duvida
    assert [s.classe for s in situacao.values()].count(None) == 1


def test_lote_anota_varias_de_uma_vez(app):
    coleta = criar_coleta(num_regioes=4)
    anotacoes = anotar_em_lote(coleta.imagens[0].regioes[:3], classe('graos', 'sem_defeito'))
    db.session.commit()
    assert len(anotacoes) == 3
    assert [s.classe for s in situacao_das_regioes(coleta.id)] == ['sem_defeito'] * 3 + [None]


def test_desfazer_so_apaga_a_propria_anotacao_vigente(app):
    ana, bia = pessoa('Ana'), pessoa('Bia')
    coleta = criar_coleta(num_regioes=2)
    r1, r2 = coleta.imagens[0].regioes
    da_ana = anotar_regiao(r1, classe('graos', 'verde'), pessoa=ana)
    da_bia = anotar_regiao(r2, classe('graos', 'verde'), pessoa=bia)
    substituida = anotar_regiao(r2, classe('graos', 'preto'), pessoa=ana)
    anotar_regiao(r2, classe('graos', 'ardido'), pessoa=bia)  # Bia mudou depois
    db.session.commit()

    assert desfazer_anotacoes([da_bia.id], ana) == 0        # não é da Ana
    assert desfazer_anotacoes([substituida.id], ana) == 0   # já foi substituída
    assert desfazer_anotacoes([da_ana.id], ana) == 1
    db.session.commit()
    assert [s.classe for s in situacao_das_regioes(coleta.id)] == [None, 'ardido']


# ---------------------------------------------------------------------- API

@pytest.fixture
def coleta_com_regioes(logado):
    coleta = criar_coleta_web(logado)
    enviar(logado, coleta, [('bandeja.png', foto_de_graos())])
    return coleta


def _post(cliente, url, dados, token=TOKEN):
    return cliente.post(url, json=dados, headers={'X-CSRF': token} if token else {})


def test_api_lista_regioes_classes_e_progresso(logado, coleta_com_regioes):
    dados = logado.get(f'/api/coletas/{coleta_com_regioes.id}/regioes').get_json()
    assert len(dados['regioes']) == dados['progresso']['total'] > 0
    assert dados['classes'][0] == {'codigo': 'sem_defeito', 'nome': 'Sem defeito', 'cor': '#009E73', 'tecla': '1'}
    regiao = dados['regioes'][0]
    assert regiao['classe'] is None and regiao['recorte'].endswith('v=' + '_'.join(map(str, regiao['bbox'])))
    assert logado.get(regiao['recorte']).status_code == 200


def test_api_anotar_e_desfazer(logado, coleta_com_regioes):
    regiao_id = coleta_com_regioes.imagens[0].regioes[0].id
    resposta = _post(logado, f'/api/regioes/{regiao_id}/anotar', {'classe': 'ardido', 'duvida': True})
    assert resposta.status_code == 200
    dados = resposta.get_json()
    assert dados['classe'] == 'ardido' and dados['duvida'] and dados['progresso']['anotadas'] == 1
    anotacao = db.session.get(Anotacao, dados['anotacao_id'])
    assert anotacao.confianca == 0.5 and anotacao.pessoa.nome == 'Ana'

    desfeito = _post(logado, '/api/anotacoes/desfazer', {'ids': [dados['anotacao_id']]}).get_json()
    assert desfeito['desfeitas'] == 1 and desfeito['regioes'][0]['classe'] is None
    assert desfeito['progresso']['anotadas'] == 0


def test_api_recusa_classe_de_outro_tipo(logado, coleta_com_regioes):
    regiao_id = coleta_com_regioes.imagens[0].regioes[0].id
    resposta = _post(logado, f'/api/regioes/{regiao_id}/anotar', {'classe': 'ferrugem'})
    assert resposta.status_code == 422 and 'não existe para Grãos' in resposta.get_json()['erro']


def test_api_exige_csrf_e_pessoa(cliente, logado, coleta_com_regioes):
    regiao_id = coleta_com_regioes.imagens[0].regioes[0].id
    assert _post(logado, f'/api/regioes/{regiao_id}/anotar', {'classe': 'ardido'}, token=None).status_code == 400
    with logado.session_transaction() as sessao:
        sessao.pop('pessoa_id')
    resposta = _post(logado, f'/api/regioes/{regiao_id}/anotar', {'classe': 'ardido'})
    assert resposta.status_code == 401 and 'Entre de novo' in resposta.get_json()['erro']


# ------------------------------------------------------------------ páginas

def test_pagina_anotar_mostra_classes_com_atalhos(logado, coleta_com_regioes):
    html_ = logado.get(f'/coletas/{coleta_com_regioes.id}/anotar').get_data(as_text=True)
    assert 'data-classe="ardido"' in html_ and 'aria-keyshortcuts="3"' in html_
    assert '<meta name="csrf"' in html_


def test_coleta_oferece_comecar_a_anotar(logado, coleta_com_regioes):
    html_ = logado.get(f'/coletas/{coleta_com_regioes.id}').get_data(as_text=True)
    assert 'Começar a anotar' in html_ and 'Anotar em lote' in html_


def test_lote_aplica_classe_e_permite_desfazer(logado, coleta_com_regioes):
    ids = [r.id for r in coleta_com_regioes.imagens[0].regioes[:5]]
    url = f'/coletas/{coleta_com_regioes.id}/lote'
    resposta = logado.post(url, data={'_csrf': TOKEN, 'regioes': ids, 'classe': 'sem_defeito'})
    pagina = html.unescape(logado.get(resposta.location).get_data(as_text=True))
    assert '5 regiões anotadas como Sem defeito.' in pagina
    assert db.session.scalar(select(func.count(Anotacao.id))) == 5

    anotacoes = [str(a.id) for a in db.session.scalars(select(Anotacao))]
    resposta = logado.post(url + '/desfazer', data={'_csrf': TOKEN, 'anotacoes': anotacoes})
    pagina = html.unescape(logado.get(resposta.location).get_data(as_text=True))
    assert 'Desfeito: 5 regiões voltaram a ficar pendente.' in pagina
    assert db.session.scalar(select(func.count(Anotacao.id))) == 0


def test_lote_sem_regioes_marcadas_explica(logado, coleta_com_regioes):
    resposta = logado.post(f'/coletas/{coleta_com_regioes.id}/lote', data={'_csrf': TOKEN, 'classe': 'preto'})
    assert 'Marque pelo menos uma região' in logado.get(resposta.location).get_data(as_text=True)


def test_lote_filtra_por_classe(logado, coleta_com_regioes):
    [primeira] = coleta_com_regioes.imagens[0].regioes[:1]
    anotar_regiao(primeira, classe('graos', 'brocado'))
    db.session.commit()
    html_ = logado.get(f'/coletas/{coleta_com_regioes.id}/lote?mostrar=brocado').get_data(as_text=True)
    assert html_.count('name="regioes"') == 1
