"""Registro de cada execução de segmentação (útil para mostrar progresso e erros)."""
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dominio.coleta import Imagem
from app.dominio.tipos import StatusJob, agora_utc, tipo_enum
from app.extensions import db


class JobSegmentacao(db.Model):
    __tablename__ = 'job_segmentacao'

    id: Mapped[int] = mapped_column(primary_key=True)
    imagem_id: Mapped[int] = mapped_column(ForeignKey('imagem.id', ondelete='CASCADE'), index=True)
    motor: Mapped[str] = mapped_column(String(40))
    versao_motor: Mapped[str | None] = mapped_column(String(40))
    parametros: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[StatusJob] = mapped_column(tipo_enum(StatusJob), default=StatusJob.NA_FILA,
                                              index=True)
    criado_em: Mapped[datetime] = mapped_column(default=agora_utc)
    iniciado_em: Mapped[datetime | None]
    concluido_em: Mapped[datetime | None]
    num_regioes: Mapped[int | None]
    mensagem_erro: Mapped[str | None] = mapped_column(Text)

    imagem: Mapped[Imagem] = relationship(back_populates='jobs')

    @property
    def duracao_s(self) -> float | None:
        if self.iniciado_em and self.concluido_em:
            return (self.concluido_em - self.iniciado_em).total_seconds()
        return None

    def __repr__(self):
        return f'<JobSegmentacao {self.id} {self.motor} {self.status}>'
