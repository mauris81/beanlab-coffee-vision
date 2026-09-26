"""Exportar os dados anotados num .zip: planilha (CSV), COCO, YOLO e recortes por classe.

Para quem vai analisar (a planilha abre no Excel) ou treinar modelos (COCO, YOLO,
recortes). Quem recebe o arquivo encontra a explicação no LEIAME.txt, gerado aqui mesmo.
Por que cada escolha: docs/decisoes/0010-exportacao.md

Regras (as mesmas da plataforma):
- vale a classe da anotação VIGENTE (a mais recente) de cada região;
- região em DÚVIDA = anotação vigente com confiança menor que 1;
- nos formatos de TREINO (COCO, YOLO, recortes), por padrão:
    * ficam de fora as regiões em dúvida (rótulo incerto ensina errado);
    * COCO e YOLO usam só fotos sem regiões pendentes: um grão sem rótulo numa foto de
      treino ensinaria ao modelo que ele é "fundo".
  A planilha sempre traz tudo, com colunas para filtrar.
"""
import csv
import io
import json
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

import yaml
from PIL import Image, ImageOps
from sqlalchemy import func, select

from app.armazenamento import armazenamento_de_imagens
from app.dominio import (
    Anotacao, Classe, Coleta, Imagem, JobSegmentacao, Pessoa, Regiao, StatusJob, TipoAmostra,
)
from app.extensions import db
from app.servicos.recortes import recorte_da_regiao

FORMATOS = {  # a planilha (CSV) vai sempre
    'coco': 'COCO: fotos + contornos, para treinar segmentação (Detectron2, MMDetection...)',
    'yolo': 'YOLO: fotos + contornos no formato do Ultralytics (yolo segment train)',
    'recortes': 'Recortes por classe: uma pasta por classe, para treinar classificadores',
}
_TAG_ORIENTACAO = 0x0112


@dataclass(frozen=True)
class PedidoDeExportacao:
    tipo: TipoAmostra
    coleta_ids: tuple[int, ...] = ()        # vazio = todas as coletas do tipo
    formatos: frozenset[str] = frozenset()  # além da planilha: 'coco', 'yolo', 'recortes'
    sem_duvidas: bool = True                # formatos de treino sem regiões em dúvida
    so_fotos_completas: bool = True         # COCO/YOLO só com fotos sem regiões pendentes


@dataclass(frozen=True)
class RegiaoExportada:
    regiao: Regiao
    imagem: Imagem
    coleta: Coleta
    anotacao: Anotacao | None   # a vigente
    classe: Classe | None
    anotada_por: str | None
    vezes_anotada: int

    @property
    def duvida(self) -> bool:
        return bool(self.anotacao and self.anotacao.confianca is not None and self.anotacao.confianca < 1)


@dataclass
class Conteudo:
    """O que vai no .zip, já decidido (e as contagens para o manifesto e para a tela)."""
    linhas: list[RegiaoExportada]
    classes: list[Classe]                                   # ordem da taxonomia = índices do YOLO
    fotos_de_treino: list[Imagem] = field(default_factory=list)
    regioes_de_treino: list[RegiaoExportada] = field(default_factory=list)   # COCO/YOLO
    recortes: list[RegiaoExportada] = field(default_factory=list)            # classificação

    @property
    def fotos(self) -> int:
        return len({linha.imagem.id for linha in self.linhas})

    @property
    def anotadas(self) -> int:
        return sum(linha.classe is not None for linha in self.linhas)

    @property
    def duvidas(self) -> int:
        return sum(linha.duvida for linha in self.linhas)


# ------------------------------------------------------------ o que exportar

def coletas_do_pedido(pedido: PedidoDeExportacao) -> list[Coleta]:
    consulta = select(Coleta).where(Coleta.tipo_amostra_id == pedido.tipo.id).order_by(Coleta.criada_em)
    if pedido.coleta_ids:
        consulta = consulta.where(Coleta.id.in_(pedido.coleta_ids))
    return list(db.session.scalars(consulta))


def montar_conteudo(pedido: PedidoDeExportacao) -> Conteudo:
    ids = [c.id for c in coletas_do_pedido(pedido)]
    vigentes = (select(Anotacao.regiao_id, func.max(Anotacao.id).label('anotacao_id'),
                       func.count(Anotacao.id).label('vezes'))
                .group_by(Anotacao.regiao_id).subquery())
    consulta = (
        select(Regiao, Imagem, Coleta, Anotacao, Classe, Pessoa.nome, vigentes.c.vezes)
        .join(Regiao.imagem).join(Imagem.coleta)
        .outerjoin(vigentes, vigentes.c.regiao_id == Regiao.id)
        .outerjoin(Anotacao, Anotacao.id == vigentes.c.anotacao_id)
        .outerjoin(Classe, Classe.id == Anotacao.classe_id)
        .outerjoin(Pessoa, Pessoa.id == Anotacao.pessoa_id)
        .where(Imagem.coleta_id.in_(ids))
        .order_by(Coleta.criada_em, Imagem.id, Regiao.id))
    linhas = [RegiaoExportada(r, i, c, a, cl, nome, vezes or 0)
              for r, i, c, a, cl, nome, vezes in db.session.execute(consulta)]

    usadas = {linha.classe.id for linha in linhas if linha.classe}
    classes = [c for c in pedido.tipo.classes if c.ativa or c.id in usadas]
    conteudo = Conteudo(linhas=linhas, classes=classes)

    serve_para_treino = [l for l in linhas if l.classe and not (pedido.sem_duvidas and l.duvida)]
    conteudo.recortes = serve_para_treino
    pendentes_por_foto = Counter(l.imagem.id for l in linhas if l.classe is None)
    fotos = {l.imagem.id: l.imagem for l in serve_para_treino
             if not (pedido.so_fotos_completas and pendentes_por_foto[l.imagem.id])}
    conteudo.fotos_de_treino = list(fotos.values())
    conteudo.regioes_de_treino = [l for l in serve_para_treino if l.imagem.id in fotos]
    return conteudo


def tamanho_estimado(pedido: PedidoDeExportacao, conteudo: Conteudo) -> int:
    """Bytes aproximados do .zip (para avisar antes de baixar)."""
    total = 50_000 + 200 * len(conteudo.linhas)
    if pedido.formatos & {'coco', 'yolo'}:
        total += sum(f.tamanho_bytes for f in conteudo.fotos_de_treino)
    if 'recortes' in pedido.formatos:
        total += 25_000 * len(conteudo.recortes)
    return total


# -------------------------------------------------------------------- .zip

def nome_do_arquivo(pedido: PedidoDeExportacao, hoje: date | None = None) -> str:
    return f'beanlab_{pedido.tipo.codigo}_{(hoje or date.today()).isoformat()}'


def exportar(pedido: PedidoDeExportacao, destino: Path, exportado_por: Pessoa | None = None) -> Conteudo:
    """Grava o .zip em `destino` (arquivo). Devolve o que foi exportado (para contar)."""
    conteudo = montar_conteudo(pedido)
    raiz = nome_do_arquivo(pedido)
    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as arquivo_zip:
        def texto(nome, dados: str):
            arquivo_zip.writestr(f'{raiz}/{nome}', dados)

        texto('regioes.csv', _planilha_de_regioes(conteudo))
        texto('historico_anotacoes.csv', _planilha_de_historico(conteudo))
        nomes_das_fotos = {}  # id da foto -> 'train/000123.jpg' (caminho dentro de images/)
        if pedido.formatos & {'coco', 'yolo'}:
            for foto in conteudo.fotos_de_treino:
                nome, dados = _foto_orientada(foto)
                nomes_das_fotos[foto.id] = f'{_separacao(foto)}/{nome}'
                arquivo_zip.writestr(f'{raiz}/images/{nomes_das_fotos[foto.id]}', dados,
                                     compress_type=zipfile.ZIP_STORED)
        if 'coco' in pedido.formatos:
            texto('coco.json', json.dumps(_coco(pedido, conteudo, nomes_das_fotos), ensure_ascii=False, indent=1))
        if 'yolo' in pedido.formatos:
            for nome, dados in _yolo(conteudo, nomes_das_fotos).items():
                texto(nome, dados)
        if 'recortes' in pedido.formatos:
            for linha in conteudo.recortes:
                arquivo_zip.write(recorte_da_regiao(linha.regiao),
                                  f'{raiz}/recortes/{linha.classe.codigo}/{linha.regiao.id}.jpg',
                                  compress_type=zipfile.ZIP_STORED)
        manifesto = _manifesto(pedido, conteudo, exportado_por)
        texto('manifesto.json', json.dumps(manifesto, ensure_ascii=False, indent=1))
        texto('LEIAME.txt', _leiame(pedido, conteudo, manifesto))
    return conteudo


def _foto_orientada(foto: Imagem) -> tuple[str, bytes]:
    """A foto como os contornos a veem. Se o celular gravou "deitada" com a marca de rotação
    (EXIF), sai já girada, em JPEG de alta qualidade; senão, o arquivo original, intacto."""
    caminho = armazenamento_de_imagens().caminho(foto.hash_sha256, foto.extensao)
    with Image.open(caminho) as imagem:
        if imagem.getexif().get(_TAG_ORIENTACAO, 1) not in range(2, 9):  # 2 a 8 = girada ou espelhada
            return f'{foto.id:06d}.{foto.extensao}', caminho.read_bytes()
        girada = ImageOps.exif_transpose(imagem).convert('RGB')
    saida = io.BytesIO()
    girada.save(saida, 'JPEG', quality=95)
    return f'{foto.id:06d}.jpg', saida.getvalue()


# ----------------------------------------------------------------- planilhas

def _hora_local(valor: datetime | None) -> str:
    return valor.replace(tzinfo=timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M') if valor else ''


def _csv(cabecalho: list[str], linhas) -> str:
    """Planilha para o Excel em português: separador ";", vírgula decimal e UTF-8 com BOM
    (sem o BOM o Excel troca os acentos)."""
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=';', lineterminator='\r\n')
    escritor.writerow(cabecalho)
    for linha in linhas:
        escritor.writerow(['' if v is None else str(v).replace('.', ',') if isinstance(v, float) else v
                           for v in linha])
    return '﻿' + saida.getvalue()


def _planilha_de_regioes(conteudo: Conteudo) -> str:
    cabecalho = ['coleta_id', 'coleta', 'tipo_amostra', 'fazenda', 'talhao', 'variedade', 'data_coleta',
                 'foto_id', 'foto', 'foto_sha256', 'foto_largura', 'foto_altura', 'regiao_id', 'origem_regiao',
                 'motor', 'versao_motor', 'bbox_x', 'bbox_y', 'bbox_largura', 'bbox_altura', 'area_px',
                 'situacao', 'classe_codigo', 'classe', 'duvida', 'observacao', 'anotada_por', 'anotada_em',
                 'vezes_anotada']
    return _csv(cabecalho, (
        [l.coleta.id, l.coleta.nome, l.coleta.tipo_amostra.codigo, l.coleta.fazenda, l.coleta.talhao,
         l.coleta.variedade, l.coleta.data_coleta.isoformat() if l.coleta.data_coleta else None,
         l.imagem.id, l.imagem.nome_original, l.imagem.hash_sha256, l.imagem.largura, l.imagem.altura,
         l.regiao.id, l.regiao.origem.value, l.regiao.motor, l.regiao.versao_motor, *l.regiao.bbox,
         l.regiao.area_px, 'anotada' if l.classe else 'pendente',
         l.classe.codigo if l.classe else None, l.classe.nome if l.classe else None,
         ('sim' if l.duvida else 'não') if l.classe else None,
         l.anotacao.observacao if l.anotacao else None, l.anotada_por,
         _hora_local(l.anotacao.criada_em) if l.anotacao else None, l.vezes_anotada]
        for l in conteudo.linhas))


def _planilha_de_historico(conteudo: Conteudo) -> str:
    """Todas as anotações, inclusive as substituídas (para medir concordância e revisões)."""
    ids = [l.regiao.id for l in conteudo.linhas]
    vigentes = {l.anotacao.id for l in conteudo.linhas if l.anotacao}
    consulta = (select(Anotacao, Classe.codigo, Pessoa.nome).join(Anotacao.classe)
                .outerjoin(Pessoa, Pessoa.id == Anotacao.pessoa_id)
                .where(Anotacao.regiao_id.in_(ids)).order_by(Anotacao.regiao_id, Anotacao.id))
    return _csv(['regiao_id', 'anotacao_id', 'classe_codigo', 'confianca', 'observacao', 'anotada_por',
                 'origem', 'anotada_em', 'vigente'], (
        [a.regiao_id, a.id, codigo, a.confianca, a.observacao, nome, a.origem.value,
         _hora_local(a.criada_em), 'sim' if a.id in vigentes else 'não']
        for a, codigo, nome in db.session.execute(consulta)))


# ---------------------------------------------------------------- COCO/YOLO

def _coco(pedido: PedidoDeExportacao, conteudo: Conteudo, nomes: dict[int, str]) -> dict:
    categoria = {c.id: indice for indice, c in enumerate(conteudo.classes, start=1)}
    return {
        'info': {'description': f'BeanLab Coffee Vision: {pedido.tipo.nome}',
                 'date_created': datetime.now().astimezone().isoformat(timespec='seconds')},
        'licenses': [],
        'categories': [{'id': categoria[c.id], 'name': c.codigo, 'nome': c.nome,
                        'supercategory': pedido.tipo.codigo} for c in conteudo.classes],
        'images': [{'id': f.id, 'file_name': nomes[f.id], 'width': f.largura, 'height': f.altura,
                    'nome_original': f.nome_original, 'coleta_id': f.coleta_id}
                   for f in conteudo.fotos_de_treino],
        'annotations': [{'id': l.regiao.id, 'image_id': l.imagem.id, 'category_id': categoria[l.classe.id],
                         'segmentation': [[coordenada for ponto in l.regiao.poligono for coordenada in ponto]],
                         'area': l.regiao.area_px, 'bbox': l.regiao.bbox, 'iscrowd': 0,
                         'attributes': {'duvida': l.duvida, 'motor': l.regiao.motor}}
                        for l in conteudo.regioes_de_treino],
    }


def _separacao(foto: Imagem) -> str:
    """~1 foto em 5 vai para validação, sempre a mesma (decidido pelo conteúdo da foto)."""
    return 'val' if int(foto.hash_sha256[:8], 16) % 5 == 0 else 'train'


def _yolo(conteudo: Conteudo, nomes: dict[int, str]) -> dict[str, str]:
    """Arranjo padrão do Ultralytics: images/{train,val}/x.jpg ao lado de labels/{train,val}/x.txt."""
    indice = {c.id: i for i, c in enumerate(conteudo.classes)}
    rotulos: dict[int, list[str]] = {f.id: [] for f in conteudo.fotos_de_treino}
    for l in conteudo.regioes_de_treino:
        largura, altura = l.imagem.largura, l.imagem.altura
        pontos = ' '.join(f'{min(max(x / largura, 0), 1):.6f} {min(max(y / altura, 0), 1):.6f}'
                          for x, y in l.regiao.poligono)
        rotulos[l.imagem.id].append(f'{indice[l.classe.id]} {pontos}')

    arquivos = {f'labels/{Path(nomes[fid]).with_suffix(".txt").as_posix()}': '\n'.join(linhas) + '\n'
                for fid, linhas in rotulos.items()}
    tem_validacao = any(nome.startswith('val/') for nome in nomes.values())
    aviso = '' if tem_validacao else '# Poucas fotos: nenhuma caiu na validação, que usa as mesmas do treino.\n'
    arquivos['data.yaml'] = ('# Conjunto para o Ultralytics (YOLO). Treinar, por exemplo:\n'
                             '#   yolo segment train data=data.yaml model=yolo11n-seg.pt\n' + aviso
                             + yaml.safe_dump({'train': 'images/train',
                                               'val': 'images/val' if tem_validacao else 'images/train',
                                               'names': {i: c.codigo for i, c in enumerate(conteudo.classes)}},
                                              allow_unicode=True, sort_keys=False))
    return arquivos


# --------------------------------------------------------- manifesto/LEIAME

def _manifesto(pedido: PedidoDeExportacao, conteudo: Conteudo, exportado_por: Pessoa | None) -> dict:
    ids_fotos = {l.imagem.id for l in conteudo.linhas}
    motores = db.session.execute(
        select(JobSegmentacao.motor, JobSegmentacao.versao_motor, JobSegmentacao.parametros)
        .where(JobSegmentacao.imagem_id.in_(ids_fotos), JobSegmentacao.status == StatusJob.CONCLUIDO)).all()
    distintos = {json.dumps([m, v, p], sort_keys=True): {'motor': m, 'versao': v, 'parametros': p}
                 for m, v, p in motores}
    coletas = Counter((l.coleta.id, l.coleta.nome) for l in conteudo.linhas)
    return {
        'plataforma': 'BeanLab Coffee Vision',
        'exportado_em': datetime.now().astimezone().isoformat(timespec='seconds'),
        'exportado_por': exportado_por.nome if exportado_por else None,
        'tipo_amostra': {'codigo': pedido.tipo.codigo, 'nome': pedido.tipo.nome},
        'coletas': [{'id': cid, 'nome': nome, 'regioes': n} for (cid, nome), n in coletas.items()],
        'formatos': ['planilha', *sorted(pedido.formatos)],
        'opcoes': {'sem_duvidas': pedido.sem_duvidas, 'so_fotos_completas': pedido.so_fotos_completas},
        'contagens': {'fotos': conteudo.fotos, 'regioes': len(conteudo.linhas), 'anotadas': conteudo.anotadas,
                      'pendentes': len(conteudo.linhas) - conteudo.anotadas, 'em_duvida': conteudo.duvidas,
                      'fotos_de_treino': len(conteudo.fotos_de_treino),
                      'regioes_de_treino': len(conteudo.regioes_de_treino),
                      'recortes': len(conteudo.recortes) if 'recortes' in pedido.formatos else 0},
        'classes': [{'indice_yolo': i, 'id_coco': i + 1, 'codigo': c.codigo, 'nome': c.nome, 'ativa': c.ativa}
                    for i, c in enumerate(conteudo.classes)],
        'motores_de_segmentacao': list(distintos.values()),
    }


def _plural(quantidade: int, singular: str, plural: str | None = None) -> str:
    return f'{quantidade} {singular if quantidade == 1 else plural or singular + "s"}'


def _leiame(pedido: PedidoDeExportacao, conteudo: Conteudo, manifesto: dict) -> str:
    n = manifesto['contagens']
    partes = [f'''BeanLab Coffee Vision: exportação de {pedido.tipo.nome}
Gerada em {manifesto['exportado_em']} por {manifesto['exportado_por'] or '(terminal)'}.

{_plural(n['fotos'], 'foto')}, {_plural(n['regioes'], 'região', 'regiões')} ({n['anotadas']} anotadas, {n['pendentes']} pendentes,
{n['em_duvida']} em dúvida), de {_plural(len(manifesto['coletas']), 'coleta')}. Detalhes: manifesto.json.

REGRAS
- Cada região é um objeto encontrado na foto (um grão, uma folha...).
- Vale a classe da anotação mais recente da região. As anteriores estão em
  historico_anotacoes.csv (útil para medir concordância entre pessoas).
- "Em dúvida": quem anotou marcou "Tenho dúvida".
- Contornos (polígonos) em pixels da foto já na orientação certa.

ARQUIVOS
regioes.csv
    Uma linha por região, com a coleta, a foto, a caixa (bbox), a área e a classe.
    Feita para o Excel em português: separador ";" e vírgula decimal.
    No Python: pandas.read_csv("regioes.csv", sep=";", decimal=",")
historico_anotacoes.csv
    Todas as anotações, inclusive as substituídas (coluna "vigente").
manifesto.json
    Filtros, contagens, classes (com os índices do COCO e do YOLO) e os motores de
    segmentação usados, com os parâmetros de cada um.''']
    treino = []
    if pedido.formatos & {'coco', 'yolo'}:
        treino.append(f'''images/train/, images/val/
    {_plural(n['fotos_de_treino'], 'foto')} para treino, com nomes neutros (000123.jpg = foto 123).
    Cerca de 1 foto em cada 5 vai para validação (sempre as mesmas).''')
    if 'coco' in pedido.formatos:
        treino.append('''coco.json
    Formato COCO (segmentação por polígonos). O "file_name" é relativo a images/
    (ex.: train/000123.jpg). Categorias: o "name" é o código da classe. Pode ser
    importado de volta na plataforma ("Conjunto COCO", junto com as fotos).''')
    if 'yolo' in pedido.formatos:
        treino.append('''data.yaml, labels/train/, labels/val/
    Formato YOLO de segmentação (Ultralytics), no arranjo padrão.
    Para treinar:  yolo segment train data=data.yaml model=yolo11n-seg.pt''')
    if 'recortes' in pedido.formatos:
        treino.append(f'''recortes/<classe>/
    {n['recortes']} recortes (um por região anotada), uma pasta por classe, para treinar
    classificadores. O nome do arquivo é o número da região (regiao_id na planilha).''')
    if treino:
        partes.append('\n'.join(treino))
        filtros = []
        if pedido.sem_duvidas:
            filtros.append('- sem as regiões em dúvida (rótulo incerto ensina errado);')
        if pedido.so_fotos_completas:
            filtros.append('- COCO e YOLO só com fotos sem regiões pendentes: um objeto sem rótulo numa\n'
                           '  foto de treino ensinaria ao modelo que ele é "fundo".')
        if filtros:
            partes.append('NOS FORMATOS DE TREINO\n' + '\n'.join(filtros)
                          + f'\nFicaram {_plural(n["fotos_de_treino"], "foto")} e '
                            f'{_plural(n["regioes_de_treino"], "região", "regiões")}.')
        if pedido.formatos & {'coco', 'yolo'} and not n['fotos_de_treino']:
            partes.append('ATENÇÃO: nenhuma foto entrou em COCO/YOLO. '
                          + ('Anote todas as regiões de pelo menos uma foto, ou exporte de novo sem\n'
                             '"Só fotos com todas as regiões anotadas".'
                             if pedido.so_fotos_completas and n['anotadas']
                             else 'Ainda não há regiões anotadas nestas coletas.'))
    partes.append('''LICENÇA
Os dados (fotos e anotações) são da equipe que os coletou. A plataforma BeanLab é
software livre (AGPL-3.0): https://github.com/mauris81/beanlab-coffee-vision''')
    return '\r\n\r\n'.join(p.replace('\n', '\r\n') for p in partes) + '\r\n'
