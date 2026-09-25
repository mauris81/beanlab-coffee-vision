"""Entrada de fotos numa coleta: fotos para segmentar, recortes prontos e COCO.

Os serviços não confirmam (commit): quem chama decide. A segmentação é agendada
depois do commit (ver app/servicos/segmentacao.py).
"""
import io
import json
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import PurePath

import cv2
import numpy as np
from PIL import Image, ImageOps
from sqlalchemy import func, select

from app.armazenamento import armazenamento_de_imagens
from app.dominio import (
    Classe, Coleta, Imagem, OrigemAnotacao, OrigemImagem, OrigemRegiao, Pessoa, Regiao,
    StatusImagem,
)
from app.dominio.geometria import PoligonoInvalido
from app.extensions import db
from app.servicos.anotacoes import anotar_regiao
from app.servicos.imagens import FotoInvalida, gerar_miniatura, ler_metadados


@dataclass
class ResultadoEnvio:
    """O que aconteceu com UM arquivo enviado. `mensagem` é para mostrar à pessoa."""
    nome_arquivo: str
    situacao: str            # 'nova' | 'repetida' | 'recusada'
    mensagem: str
    imagem: Imagem | None = None


def receber_foto(coleta: Coleta, conteudo: bytes, nome_original: str, *,
                 origem: OrigemImagem = OrigemImagem.ARQUIVO, pessoa: Pessoa | None = None,
                 ja_segmentada: bool = False) -> ResultadoEnvio:
    """Valida, guarda o arquivo e cria a Imagem. Foto repetida na coleta não é duplicada."""
    nome = PurePath(nome_original or 'foto').name[:255]
    try:
        meta = ler_metadados(conteudo)
    except FotoInvalida as erro:
        return ResultadoEnvio(nome, 'recusada', str(erro))

    armazenamento = armazenamento_de_imagens()
    salvo = armazenamento.salvar(conteudo, meta.extensao)
    existente = db.session.scalar(select(Imagem).filter_by(coleta_id=coleta.id,
                                                           hash_sha256=salvo.hash_sha256))
    if existente:
        return ResultadoEnvio(nome, 'repetida',
                              f'Já estava nesta coleta (como "{existente.nome_original}").', existente)

    gerar_miniatura(salvo.caminho, armazenamento.caminho_miniatura(salvo.hash_sha256))
    imagem = Imagem(
        coleta=coleta, hash_sha256=salvo.hash_sha256, extensao=salvo.extensao,
        nome_original=nome, largura=meta.largura, altura=meta.altura,
        tamanho_bytes=salvo.tamanho_bytes, capturada_em=meta.capturada_em,
        latitude=meta.latitude, longitude=meta.longitude, origem=origem,
        status=StatusImagem.PRONTA if ja_segmentada else StatusImagem.AGUARDANDO,
        ja_segmentada=ja_segmentada, enviada_por=pessoa,
    )
    db.session.add(imagem)
    db.session.flush()
    return ResultadoEnvio(nome, 'nova', 'Recebida.', imagem)


# ------------------------------------------------------------------ recortes

def receber_recorte(coleta: Coleta, conteudo: bytes, nome_original: str, *,
                    pessoa: Pessoa | None = None) -> ResultadoEnvio:
    """Um arquivo = um objeto já recortado. Vira uma Imagem com uma única Região.

    O contorno vem da transparência (PNG com fundo transparente); sem transparência,
    a região é a imagem inteira.
    """
    resultado = receber_foto(coleta, conteudo, nome_original, origem=OrigemImagem.IMPORTACAO,
                             pessoa=pessoa, ja_segmentada=True)
    if resultado.situacao == 'nova':
        pontos, area = _contorno_do_recorte(conteudo)
        resultado.imagem.regioes.append(
            Regiao.do_poligono(pontos, origem=OrigemRegiao.IMPORTADA, area_px=area))
        db.session.flush()
    return resultado


def _contorno_do_recorte(conteudo: bytes) -> tuple[list[list[int]], int]:
    imagem = ImageOps.exif_transpose(Image.open(io.BytesIO(conteudo)))  # mesma orientação do resto
    largura, altura = imagem.size
    retangulo = [[0, 0], [largura, 0], [largura, altura], [0, altura]]
    if 'A' not in imagem.getbands() and 'transparency' not in imagem.info:
        return retangulo, largura * altura
    alfa = np.asarray(imagem.convert('RGBA'))[:, :, 3]
    mascara = (alfa > 0).astype(np.uint8)
    if mascara.all() or not mascara.any():
        return retangulo, largura * altura
    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    maior = max(contornos, key=cv2.contourArea)
    pontos = cv2.approxPolyDP(maior, 1.0, True).reshape(-1, 2).tolist()
    return (pontos, int(mascara.sum())) if len(pontos) >= 3 else (retangulo, largura * altura)


# ---------------------------------------------------------------------- COCO

@dataclass
class ResumoImportacao:
    resultados: list[ResultadoEnvio] = field(default_factory=list)
    regioes: int = 0
    anotacoes: int = 0
    categorias_sem_classe: set[str] = field(default_factory=set)
    imagens_sem_arquivo: list[str] = field(default_factory=list)
    arquivos_sem_anotacao: list[str] = field(default_factory=list)
    regioes_ignoradas: int = 0  # formato RLE ou contorno inválido


class ImportacaoInvalida(ValueError):
    """O arquivo de anotações não pôde ser lido. A mensagem é para a pessoa."""


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode()
    return ''.join(c if c.isalnum() else '_' for c in sem_acento.casefold()).strip('_')


def importar_coco(coleta: Coleta, arquivos: dict[str, bytes], conteudo_json: bytes, *,
                  pessoa: Pessoa | None = None) -> ResumoImportacao:
    """Importa fotos + anotações no formato COCO (segmentação por polígonos).

    - Fotos são casadas com o JSON pelo nome do arquivo (sem pasta).
    - Cada anotação vira uma Região. Polígonos com várias partes: usa a maior.
    - Categoria com o mesmo nome ou código de uma classe (sem acento, maiúsculas
      tanto faz) vira uma Anotação importada; as demais ficam pendentes.
    - Coordenadas: pixels da foto como ela aparece (já girada).
    """
    try:
        dados = json.loads(conteudo_json.decode('utf-8-sig'))
        imagens_coco = {img['id']: PurePath(img['file_name']).name for img in dados['images']}
        anotacoes_coco = dados.get('annotations', [])
        categorias = {c['id']: str(c['name']) for c in dados.get('categories', [])}
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as erro:
        raise ImportacaoInvalida('O arquivo .json não está no formato COCO '
                                 '(precisa das listas "images" e "annotations").') from erro

    classes_por_nome = {}
    for classe in coleta.tipo_amostra.classes_ativas:
        classes_por_nome[_normalizar(classe.codigo)] = classe
        classes_por_nome[_normalizar(classe.nome)] = classe

    resumo = ResumoImportacao()
    arquivos = {PurePath(nome).name: conteudo for nome, conteudo in arquivos.items()}
    imagem_por_id = {}
    for id_coco, nome in imagens_coco.items():
        if nome not in arquivos:
            resumo.imagens_sem_arquivo.append(nome)
            continue
        resultado = receber_foto(coleta, arquivos[nome], nome, origem=OrigemImagem.IMPORTACAO,
                                 pessoa=pessoa, ja_segmentada=True)
        resumo.resultados.append(resultado)
        if resultado.situacao == 'nova':
            imagem_por_id[id_coco] = resultado.imagem
    resumo.arquivos_sem_anotacao = sorted(set(arquivos) - set(imagens_coco.values()))

    for anotacao in anotacoes_coco:
        imagem = imagem_por_id.get(anotacao.get('image_id'))
        if imagem is None:
            continue
        pontos = _maior_poligono(anotacao.get('segmentation'))
        try:
            regiao = Regiao.do_poligono(pontos, origem=OrigemRegiao.IMPORTADA,
                                        area_px=_area_coco(anotacao))
        except PoligonoInvalido:
            resumo.regioes_ignoradas += 1
            continue
        imagem.regioes.append(regiao)
        resumo.regioes += 1
        nome_categoria = categorias.get(anotacao.get('category_id'))
        classe = classes_por_nome.get(_normalizar(nome_categoria)) if nome_categoria else None
        if classe:
            db.session.flush()
            anotar_regiao(regiao, classe, pessoa=pessoa, origem=OrigemAnotacao.IMPORTADA)
            resumo.anotacoes += 1
        elif nome_categoria:
            resumo.categorias_sem_classe.add(nome_categoria)
    db.session.flush()
    return resumo


def _maior_poligono(segmentacao) -> list:
    """COCO guarda polígonos como [x1, y1, x2, y2, ...]. RLE (dicionário) não é suportado."""
    if not isinstance(segmentacao, list) or not segmentacao:
        return []
    poligonos = [list(zip(p[0::2], p[1::2])) for p in segmentacao if isinstance(p, list) and len(p) >= 6]
    return max(poligonos, key=len) if poligonos else []


def _area_coco(anotacao) -> int | None:
    area = anotacao.get('area')
    return int(round(area)) if isinstance(area, (int, float)) and area > 0 else None


# ---------------------------------------------------------------- exclusão

def excluir_imagem(imagem: Imagem) -> Callable[[], None]:
    """Tira a foto do banco (com suas regiões e anotações).

    Devolve uma função que apaga o arquivo do disco: chame-a só DEPOIS do commit.
    Assim, se o commit falhar, a foto continua inteira. O arquivo só é apagado se
    nenhuma outra coleta usar a mesma foto.

        apagar_arquivo = excluir_imagem(imagem)
        db.session.commit()
        apagar_arquivo()
    """
    hash_sha256, extensao = imagem.hash_sha256, imagem.extensao
    armazenamento = armazenamento_de_imagens()
    db.session.delete(imagem)
    db.session.flush()

    def apagar_arquivo():
        ainda_usada = db.session.scalar(
            select(func.count(Imagem.id)).filter_by(hash_sha256=hash_sha256))
        if not ainda_usada:
            armazenamento.remover(hash_sha256, extensao)
    return apagar_arquivo
