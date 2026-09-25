"""Segmentação das fotos: agendar, executar e retomar.

Fluxo: agendar_segmentacao() cria um JobSegmentacao "na fila" -> (commit) -> a fila
(app/fila.py) chama executar_job() em segundo plano -> as regiões são gravadas e a
foto fica "pronta" (ou "erro", com a mensagem guardada no job).
"""
import logging

from sqlalchemy import select

from app.armazenamento import armazenamento_de_imagens
from app.dominio import Imagem, JobSegmentacao, OrigemRegiao, Regiao, StatusImagem, StatusJob
from app.dominio.geometria import PoligonoInvalido
from app.dominio.tipos import agora_utc
from app.extensions import db
from app.segmentacao import obter_motor
from app.servicos.imagens import matriz_rgb

log = logging.getLogger(__name__)


def agendar_segmentacao(imagem: Imagem) -> JobSegmentacao | None:
    """Coloca a foto na fila do motor do seu tipo de amostra. Não confirma (commit).

    Tipo sem motor: a foto fica pronta sem regiões (precisa chegar já segmentada).
    """
    nome_motor = imagem.coleta.tipo_amostra.motor_padrao
    if not nome_motor or imagem.ja_segmentada:
        imagem.status = StatusImagem.PRONTA
        return None
    motor = obter_motor(nome_motor)
    job = JobSegmentacao(imagem=imagem, motor=motor.nome, versao_motor=motor.versao)
    imagem.status = StatusImagem.AGUARDANDO
    db.session.add(job)
    db.session.flush()
    return job


def executar_job(job_id: int) -> None:
    """Roda a segmentação de um job e grava o resultado (confirma no banco)."""
    job = db.session.get(JobSegmentacao, job_id)
    if job is None or job.status not in (StatusJob.NA_FILA, StatusJob.PROCESSANDO):
        return
    imagem = job.imagem
    job.status, job.iniciado_em = StatusJob.PROCESSANDO, agora_utc()
    imagem.status = StatusImagem.SEGMENTANDO
    db.session.commit()

    try:
        caminho = armazenamento_de_imagens().caminho(imagem.hash_sha256, imagem.extensao)
        encontradas = obter_motor(job.motor).segmentar(matriz_rgb(caminho))
        # Refazer a segmentação substitui as regiões automáticas anteriores deste motor.
        for antiga in [r for r in imagem.regioes if r.origem == OrigemRegiao.AUTOMATICA]:
            imagem.regioes.remove(antiga)
        gravadas = 0
        for encontrada in encontradas:
            try:
                imagem.regioes.append(Regiao.do_poligono(
                    encontrada.poligono, origem=OrigemRegiao.AUTOMATICA, area_px=encontrada.area_px,
                    pontuacao=encontrada.pontuacao, motor=job.motor, versao_motor=job.versao_motor))
                gravadas += 1
            except PoligonoInvalido:
                continue  # contorno degenerado (ex.: 3 pontos alinhados): ignora
        job.status, job.num_regioes = StatusJob.CONCLUIDO, gravadas
        imagem.status = StatusImagem.PRONTA
    except Exception as erro:  # qualquer falha vira "erro" visível, nunca trava a fila
        log.exception('Falha na segmentação do job %s', job_id)
        db.session.rollback()
        job = db.session.get(JobSegmentacao, job_id)
        job.status, job.mensagem_erro = StatusJob.ERRO, f'{type(erro).__name__}: {erro}'[:2000]
        job.imagem.status = StatusImagem.ERRO
    job.concluido_em = agora_utc()
    db.session.commit()


def jobs_para_retomar() -> list[int]:
    """Jobs que ficaram pela metade (plataforma fechada no meio). Confirma no banco."""
    jobs = db.session.scalars(select(JobSegmentacao).where(
        JobSegmentacao.status.in_([StatusJob.NA_FILA, StatusJob.PROCESSANDO]))
        .order_by(JobSegmentacao.id)).all()
    for job in jobs:
        job.status = StatusJob.NA_FILA
        job.imagem.status = StatusImagem.AGUARDANDO
    db.session.commit()
    return [job.id for job in jobs]


def ultimo_erro(imagem: Imagem) -> str | None:
    erros = [j for j in imagem.jobs if j.status == StatusJob.ERRO]
    return erros[-1].mensagem_erro if erros else None
