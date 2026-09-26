"""Exportação: planilha, COCO, YOLO, recortes, regras de treino, página e comando."""
import csv
import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pytest
import yaml
from PIL import Image

from app.dominio import Coleta, Imagem, Regiao, OrigemRegiao
from app.extensions import db
from app.servicos.anotacoes import CONFIANCA_DUVIDA, anotar_regiao
from app.servicos.exportacao import PedidoDeExportacao, exportar
from app.servicos.ingestao import importar_coco, receber_foto
from tests.conftest import TOKEN, classe, criar_pessoa, tipo
from tests.fabrica_imagens import foto_jpeg


def quadrado(x, y, lado=40):
    return Regiao.do_poligono([[x, y], [x + lado, y], [x + lado, y + lado], [x, y + lado]],
                              origem=OrigemRegiao.AUTOMATICA, motor='classico', versao_motor='2.1')


@pytest.fixture
def dados(app):
    """Foto A: completa (sem_defeito, preto em dúvida, ardido corrigido para sem_defeito).
    Foto B: preto + uma região pendente."""
    ana = criar_pessoa('Ana Souza')
    coleta = Coleta(nome='Talhão 3', tipo_amostra=tipo('graos'), fazenda='Boa Vista', data_coleta=date(2026, 3, 12))
    db.session.add(coleta)
    db.session.flush()
    a = receber_foto(coleta, foto_jpeg(cor=(10, 20, 30)), 'a.jpg', ja_segmentada=True).imagem
    b = receber_foto(coleta, foto_jpeg(cor=(40, 50, 60)), 'b.jpg', ja_segmentada=True).imagem
    a.regioes.extend([quadrado(10, 10), quadrado(100, 10), quadrado(200, 10)])
    b.regioes.extend([quadrado(10, 100), quadrado(100, 100)])
    db.session.flush()
    r1, r2, r3 = a.regioes
    r4, r5 = b.regioes
    anotar_regiao(r1, classe('graos', 'sem_defeito'), pessoa=ana)
    anotar_regiao(r2, classe('graos', 'preto'), pessoa=ana, confianca=CONFIANCA_DUVIDA, observacao='escuro; será?')
    anotar_regiao(r3, classe('graos', 'ardido'), pessoa=ana)
    anotar_regiao(r3, classe('graos', 'sem_defeito'), pessoa=ana)
    anotar_regiao(r4, classe('graos', 'preto'), pessoa=ana)
    db.session.commit()
    return {'coleta': coleta, 'a': a, 'b': b, 'regioes': [r1, r2, r3, r4, r5]}


def exportado(tmp_path, **opcoes) -> tuple[zipfile.ZipFile, str]:
    pedido = PedidoDeExportacao(tipo=tipo('graos'), formatos=frozenset({'coco', 'yolo', 'recortes'}), **opcoes)
    destino = tmp_path / 'saida.zip'
    exportar(pedido, destino)
    arquivo = zipfile.ZipFile(destino)
    return arquivo, arquivo.namelist()[0].split('/')[0]


def planilha(arquivo, raiz, nome):
    texto = arquivo.read(f'{raiz}/{nome}').decode('utf-8')
    assert texto.startswith('﻿')  # BOM: o Excel reconhece os acentos
    return list(csv.DictReader(io.StringIO(texto[1:]), delimiter=';'))


# ------------------------------------------------------------------ planilhas

def test_planilha_traz_todas_as_regioes(dados, tmp_path):
    arquivo, raiz = exportado(tmp_path)
    linhas = {int(l['regiao_id']): l for l in planilha(arquivo, raiz, 'regioes.csv')}
    r1, r2, r3, r4, r5 = dados['regioes']
    assert len(linhas) == 5
    assert linhas[r1.id]['classe_codigo'] == 'sem_defeito' and linhas[r1.id]['anotada_por'] == 'Ana Souza'
    assert linhas[r2.id]['duvida'] == 'sim' and linhas[r2.id]['observacao'] == 'escuro; será?'
    assert linhas[r3.id]['classe_codigo'] == 'sem_defeito' and linhas[r3.id]['vezes_anotada'] == '2'
    assert linhas[r5.id]['situacao'] == 'pendente' and linhas[r5.id]['classe_codigo'] == ''
    assert linhas[r1.id]['fazenda'] == 'Boa Vista' and linhas[r1.id]['data_coleta'] == '2026-03-12'


def test_historico_tem_as_anotacoes_substituidas(dados, tmp_path):
    arquivo, raiz = exportado(tmp_path)
    historico = planilha(arquivo, raiz, 'historico_anotacoes.csv')
    r3 = dados['regioes'][2]
    da_r3 = [(h['classe_codigo'], h['vigente']) for h in historico if int(h['regiao_id']) == r3.id]
    assert da_r3 == [('ardido', 'não'), ('sem_defeito', 'sim')]
    duvida = next(h for h in historico if h['classe_codigo'] == 'preto' and h['confianca'])
    assert duvida['confianca'] == '0,5'  # vírgula decimal, como o Excel em português espera


# ------------------------------------------------------------- formatos de treino

def test_treino_sem_duvidas_e_so_com_fotos_completas(dados, tmp_path):
    arquivo, raiz = exportado(tmp_path)
    coco = json.loads(arquivo.read(f'{raiz}/coco.json'))
    r1, r2, r3, r4, r5 = dados['regioes']
    assert [i['id'] for i in coco['images']] == [dados['a'].id]  # a foto B tem pendente
    assert sorted(a['id'] for a in coco['annotations']) == [r1.id, r3.id]  # r2 está em dúvida
    categorias = {c['id']: c['name'] for c in coco['categories']}
    assert {categorias[a['category_id']] for a in coco['annotations']} == {'sem_defeito'}
    anotacao = next(a for a in coco['annotations'] if a['id'] == r1.id)
    assert anotacao['bbox'] == [10, 10, 40, 40] and anotacao['segmentation'] == [[10, 10, 50, 10, 50, 50, 10, 50]]
    manifesto = json.loads(arquivo.read(f'{raiz}/manifesto.json'))
    assert manifesto['contagens'] == {'fotos': 2, 'regioes': 5, 'anotadas': 4, 'pendentes': 1, 'em_duvida': 1,
                                      'fotos_de_treino': 1, 'regioes_de_treino': 2, 'recortes': 3}


def test_opcoes_desligadas_levam_tudo_que_tem_classe(dados, tmp_path):
    arquivo, raiz = exportado(tmp_path, sem_duvidas=False, so_fotos_completas=False)
    coco = json.loads(arquivo.read(f'{raiz}/coco.json'))
    assert len(coco['images']) == 2 and len(coco['annotations']) == 4


def test_yolo_pronto_para_treinar(dados, tmp_path):
    arquivo, raiz = exportado(tmp_path, sem_duvidas=False, so_fotos_completas=False)
    nomes = set(arquivo.namelist())
    config = yaml.safe_load(arquivo.read(f'{raiz}/data.yaml'))
    indices = {v: k for k, v in config['names'].items()}
    assert config['train'] == 'images/train'
    imagens = [n.split(f'{raiz}/images/')[1] for n in nomes if '/images/' in n]  # 'train/000001.jpg'
    assert {Path(i).name for i in imagens} == {f'{dados["a"].id:06d}.jpg', f'{dados["b"].id:06d}.jpg'}
    for imagem in imagens:  # arranjo padrão: images/<parte>/x.jpg ao lado de labels/<parte>/x.txt
        assert f'{raiz}/labels/{Path(imagem).with_suffix(".txt").as_posix()}' in nomes
    da_foto_a = next(i for i in imagens if Path(i).name == f'{dados["a"].id:06d}.jpg')
    rotulos = arquivo.read(f'{raiz}/labels/{Path(da_foto_a).with_suffix(".txt").as_posix()}').decode().split('\n')
    linhas = [l.split() for l in rotulos if l]
    assert sorted(int(l[0]) for l in linhas) == sorted([indices['sem_defeito']] * 2 + [indices['preto']])
    coordenadas = [float(v) for l in linhas for v in l[1:]]
    assert all(0 <= v <= 1 for v in coordenadas)
    assert linhas[0][1:3] == [f'{10 / 400:.6f}', f'{10 / 300:.6f}']  # normalizado pela largura e altura


def test_recortes_por_classe(dados, tmp_path):
    arquivo, raiz = exportado(tmp_path)
    r1, r2, r3, r4, r5 = dados['regioes']
    recortes = sorted(n.split(f'{raiz}/recortes/')[1] for n in arquivo.namelist() if '/recortes/' in n)
    assert recortes == sorted([f'preto/{r4.id}.jpg', f'sem_defeito/{r1.id}.jpg', f'sem_defeito/{r3.id}.jpg'])


def test_foto_girada_sai_na_orientacao_dos_contornos(app, tmp_path):
    coleta = Coleta(nome='Deitada', tipo_amostra=tipo('graos'))
    db.session.add(coleta)
    db.session.flush()
    imagem = receber_foto(coleta, foto_jpeg(400, 300, orientacao=6), 'de_pe.jpg', ja_segmentada=True).imagem
    imagem.regioes.append(quadrado(10, 10))
    db.session.flush()
    anotar_regiao(imagem.regioes[0], classe('graos', 'preto'))
    db.session.commit()
    assert (imagem.largura, imagem.altura) == (300, 400)  # o celular gravou deitada, com a marca de rotação
    arquivo, raiz = exportado(tmp_path)
    nome = next(n for n in arquivo.namelist() if '/images/' in n and n.endswith(f'/{imagem.id:06d}.jpg'))
    foto = Image.open(io.BytesIO(arquivo.read(nome)))
    assert foto.size == (300, 400) and foto.getexif().get(0x0112, 1) == 1


def test_coco_exportado_volta_para_a_plataforma(dados, tmp_path):
    """Ida e volta: o que sai em COCO entra de novo, região por região, com as mesmas classes."""
    arquivo, raiz = exportado(tmp_path, sem_duvidas=False, so_fotos_completas=False)
    fotos = {Path(n).name: arquivo.read(n) for n in arquivo.namelist() if '/images/' in n}
    nova = Coleta(nome='Reimportada', tipo_amostra=tipo('graos'))
    db.session.add(nova)
    db.session.flush()
    resumo = importar_coco(nova, fotos, arquivo.read(f'{raiz}/coco.json'))
    db.session.commit()
    assert resumo.regioes == 4 and resumo.anotacoes == 4 and not resumo.categorias_sem_classe
    originais = sorted((r.bbox, r.anotacao_vigente.classe.codigo) for r in dados['regioes'] if r.anotacao_vigente)
    voltaram = sorted((r.bbox, r.anotacao_vigente.classe.codigo) for i in nova.imagens for r in i.regioes)
    assert voltaram == originais


def test_leiame_avisa_quando_nada_entra_no_treino(app, tmp_path):
    coleta = Coleta(nome='Sem anotação', tipo_amostra=tipo('graos'))
    db.session.add(coleta)
    db.session.flush()
    imagem = receber_foto(coleta, foto_jpeg(), 'x.jpg', ja_segmentada=True).imagem
    imagem.regioes.append(quadrado(5, 5))
    db.session.commit()
    arquivo, raiz = exportado(tmp_path)
    leiame = arquivo.read(f'{raiz}/LEIAME.txt').decode()
    assert 'ATENÇÃO: nenhuma foto entrou em COCO/YOLO' in leiame and '1 foto,' in leiame


# ---------------------------------------------------------------- página e comando

def test_so_a_administracao_exporta(logado):
    assert logado.get('/exportar').status_code == 403
    assert logado.post('/exportar', data={'_csrf': TOKEN, 'tipo': 'graos'}).status_code == 403


def test_pagina_mostra_coletas_e_baixa_o_zip(logado_admin, dados, app):
    pagina = ' '.join(logado_admin.get('/exportar?tipo=graos').get_data(as_text=True).split())
    assert 'Talhão 3' in pagina and '4 de 5 regiões anotadas' in pagina
    resposta = logado_admin.post('/exportar', data={
        '_csrf': TOKEN, 'tipo': 'graos', 'coletas': [dados['coleta'].id], 'formatos': ['coco'],
        'sem_duvidas': '1', 'so_fotos_completas': '1'})
    assert resposta.status_code == 200 and resposta.mimetype == 'application/zip'
    assert f'beanlab_graos_{date.today().isoformat()}.zip' in resposta.headers['Content-Disposition']
    arquivo = zipfile.ZipFile(io.BytesIO(resposta.get_data()))
    assert any(n.endswith('coco.json') for n in arquivo.namelist())
    assert not any(n.endswith('data.yaml') for n in arquivo.namelist())  # YOLO não foi pedido
    resposta.close()
    assert list((Path(app.config['PASTA_DADOS']) / 'exportacoes').glob('*.zip')) == []  # temporário apagado


def test_exportar_sem_coletas_pede_para_escolher(logado_admin, dados):
    resposta = logado_admin.post('/exportar', data={'_csrf': TOKEN, 'tipo': 'graos'}, follow_redirects=True)
    assert 'Escolha pelo menos uma coleta para exportar.' in resposta.get_data(as_text=True)


def test_comando_de_terminal(app, dados, tmp_path):
    destino = tmp_path / 'graos.zip'
    resultado = app.test_cli_runner().invoke(args=['exportar', 'graos', '--formatos', 'yolo', '--saida', str(destino)])
    assert resultado.exit_code == 0, resultado.output
    assert 'regiões 5' in resultado.output and zipfile.is_zipfile(destino)


@pytest.mark.ia
def test_o_ultralytics_le_o_yolo_exportado(dados, tmp_path, monkeypatch):
    """Prova com a própria biblioteca: o conjunto YOLO abre e os rótulos batem com as fotos."""
    pytest.importorskip('ultralytics')
    monkeypatch.setenv('YOLO_OFFLINE', '1')
    from ultralytics.data import YOLODataset
    from ultralytics.data.utils import check_det_dataset
    arquivo, raiz = exportado(tmp_path, sem_duvidas=False, so_fotos_completas=False)
    arquivo.extractall(tmp_path / 'x')
    conjunto = check_det_dataset(str(tmp_path / 'x' / raiz / 'data.yaml'))
    total = 0
    for parte in ('train', 'val'):
        rotulos = YOLODataset(img_path=conjunto[parte], data=conjunto, task='segment', augment=False).get_labels()
        assert all(len(r['segments']) == len(r['cls']) for r in rotulos)
        total += sum(len(r['cls']) for r in rotulos) if parte == 'train' or conjunto['val'] != conjunto['train'] else 0
    assert total == 4
