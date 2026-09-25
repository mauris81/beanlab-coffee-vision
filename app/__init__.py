"""BeanLab Coffee Vision: criação da aplicação Flask.

Estrutura das pastas e responsabilidades: docs/ARQUITETURA.md
"""
from flask import Flask

from app.config import Config, carregar_chave_secreta
from app.extensions import db, migrate


def create_app(config: Config | None = None) -> Flask:
    config = config or Config()
    app = Flask(__name__)
    app.config.from_object(config)

    app.config['PASTA_IMAGENS'].mkdir(parents=True, exist_ok=True)
    app.config['SECRET_KEY'] = carregar_chave_secreta(app.config['PASTA_DADOS'])

    db.init_app(app)
    # render_as_batch: o SQLite não altera colunas diretamente; o Alembic recria a tabela.
    migrate.init_app(app, db, directory=str(app.config['PASTA_MIGRACOES']), render_as_batch=True)

    from app import dominio  # noqa: F401  (registra as tabelas no SQLAlchemy)
    from app.fila import FilaDeSegmentacao
    app.extensions['fila_segmentacao'] = FilaDeSegmentacao(app)
    from app.api.rotas import api_bp
    from app.cli import registrar_comandos
    from app.web import web_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)
    registrar_comandos(app)
    return app
