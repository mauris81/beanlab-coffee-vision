"""Identificação de quem usa a plataforma (por enquanto, só pelo nome)."""
from sqlalchemy import select

from app.dominio import Pessoa
from app.extensions import db


def obter_ou_criar_pessoa(nome: str) -> Pessoa:
    """Devolve a pessoa com esse nome, criando-a se for a primeira vez.

    Maiúsculas e espaços extras não importam: "maria  silva" é "Maria Silva".
    Não confirma (commit): quem chama decide.
    """
    nome_limpo = ' '.join((nome or '').split())
    if not nome_limpo:
        raise ValueError('Informe um nome.')
    if len(nome_limpo) > 120:
        raise ValueError('O nome passa de 120 caracteres.')

    normalizado = Pessoa.normalizar(nome_limpo)
    pessoa = db.session.scalar(select(Pessoa).filter_by(nome_normalizado=normalizado))
    if pessoa is None:
        pessoa = Pessoa(nome=nome_limpo, nome_normalizado=normalizado)
        db.session.add(pessoa)
        db.session.flush()
    return pessoa
