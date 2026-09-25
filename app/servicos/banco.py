"""Deixa o banco pronto para uso. Chamado ao iniciar a plataforma (run.py)."""
from flask import current_app
from flask_migrate import upgrade

from app.extensions import db
from app.servicos.taxonomias import ResumoSincronizacao, ler_taxonomias, sincronizar_taxonomias


def preparar_banco() -> ResumoSincronizacao:
    """Aplica as migrações pendentes e sincroniza as taxonomias.

    Seguro rodar quantas vezes quiser: o que já está em dia não é alterado.
    Precisa de um contexto de aplicação ativo (`with app.app_context():`).
    """
    upgrade()
    definicoes = ler_taxonomias(current_app.config['PASTA_TAXONOMIAS'])
    resumo = sincronizar_taxonomias(definicoes)
    db.session.commit()
    return resumo
