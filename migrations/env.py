import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# disable_existing_loggers=False: sem isso, os logs do Flask/Werkzeug somem
# depois que as migrações rodam ao iniciar a plataforma.
fileConfig(config.config_file_name, disable_existing_loggers=False)
logger = logging.getLogger('alembic.env')


def get_engine():
    # Flask-SQLAlchemy >= 3 (o get_engine() antigo será removido na versão 3.2).
    return current_app.extensions['migrate'].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = current_app.extensions['migrate'].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        # SQLite: para alterar uma tabela, o Alembic a recria (copia, apaga a antiga,
        # renomeia). Com as chaves estrangeiras ligadas, apagar a tabela antiga falha
        # se outras tabelas apontam para ela. Por isso elas ficam desligadas SÓ durante
        # a migração, a integridade é conferida no fim e elas são religadas antes de a
        # conexão voltar ao uso normal. (O PRAGMA só vale fora de transação.)
        sqlite = connection.dialect.name == 'sqlite'
        if sqlite:
            connection.exec_driver_sql('PRAGMA foreign_keys = OFF')
            # Fecha a transação que o SQLAlchemy abre sozinho; senão o Alembic acha que
            # já existe uma em andamento e não confirma (commit) a migração.
            connection.commit()
        try:
            context.configure(
                connection=connection,
                target_metadata=get_metadata(),
                **conf_args
            )

            with context.begin_transaction():
                context.run_migrations()
                if sqlite:
                    problemas = connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall()
                    if problemas:
                        raise RuntimeError(
                            'A migração deixaria referências quebradas no banco '
                            f'(tabela, linha, tabela referida): {problemas[:10]}')
        finally:
            if sqlite:
                connection.rollback()  # garante que não há transação aberta (senão o PRAGMA é ignorado)
                connection.exec_driver_sql('PRAGMA foreign_keys = ON')
                connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
