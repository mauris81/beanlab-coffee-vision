"""Fila de segmentação em segundo plano.

Uma linha de execução (thread) processa um job por vez: a segmentação usa muito o
processador, e fazer várias ao mesmo tempo só deixaria tudo lento. A página
continua respondendo enquanto isso.

Nos testes (config SEGMENTACAO_SINCRONA), os jobs rodam na hora, sem thread.
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, current_app

from app.extensions import db
from app.servicos.segmentacao import executar_job, jobs_para_retomar

log = logging.getLogger(__name__)


class FilaDeSegmentacao:
    def __init__(self, app: Flask):
        self.app = app
        self._executor: ThreadPoolExecutor | None = None
        self._trava = threading.Lock()

    def enviar(self, ids_de_jobs: list[int]) -> None:
        """Chame DEPOIS do commit que criou os jobs."""
        if self.app.config.get('SEGMENTACAO_SINCRONA'):
            for job_id in ids_de_jobs:
                self._rodar(job_id)
            return
        with self._trava:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='segmentacao')
            for job_id in ids_de_jobs:
                self._executor.submit(self._rodar, job_id)

    def retomar_pendentes(self) -> int:
        """Recoloca na fila o que ficou pela metade. Chamado ao iniciar a plataforma."""
        with self.app.app_context():
            ids = jobs_para_retomar()
        self.enviar(ids)
        return len(ids)

    def _rodar(self, job_id: int) -> None:
        with self.app.app_context():
            try:
                executar_job(job_id)
            except Exception:
                log.exception('Erro inesperado ao processar o job %s', job_id)
            finally:
                db.session.remove()


def fila() -> FilaDeSegmentacao:
    return current_app.extensions['fila_segmentacao']
