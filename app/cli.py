"""Comandos de terminal. Uso: `flask --app app <comando>` (com o .venv ativo)."""
import click

from app.servicos.banco import preparar_banco


def registrar_comandos(app):
    @app.cli.command('preparar-banco')
    def comando_preparar_banco():
        """Aplica migrações pendentes e sincroniza as taxonomias."""
        resumo = preparar_banco()
        click.echo(descrever_resumo(resumo))

    @app.cli.command('redefinir-senha')
    @click.argument('usuario')
    def comando_redefinir_senha(usuario):
        """Emergência: nova senha provisória para USUARIO (ex.: o único administrador
        esqueceu a senha). Precisa de acesso ao computador onde a plataforma roda."""
        from app.extensions import db
        from app.servicos.contas import buscar_por_usuario, redefinir_senha, reativar
        pessoa = buscar_por_usuario(usuario)
        if pessoa is None:
            raise click.ClickException(f'Usuário "{usuario}" não existe.')
        reativar(pessoa)
        senha = redefinir_senha(pessoa)
        db.session.commit()
        click.echo(f'Nova senha provisória de {pessoa.nome} ({pessoa.usuario}): {senha}')
        click.echo('No primeiro acesso a pessoa vai criar a própria senha.')


def descrever_resumo(resumo) -> str:
    """Frase curta sobre o que a sincronização de taxonomias mudou."""
    if not resumo.houve_mudanca:
        return 'Banco em dia. Nenhuma mudança nas classes.'
    partes = []
    if resumo.tipos_criados:
        partes.append(f'{len(resumo.tipos_criados)} tipo(s) de amostra criado(s)')
    if resumo.classes_criadas:
        partes.append(f'{len(resumo.classes_criadas)} classe(s) criada(s)')
    if resumo.classes_reativadas:
        partes.append('reativada(s): ' + ', '.join(resumo.classes_reativadas))
    if resumo.classes_desativadas:
        partes.append('desativada(s): ' + ', '.join(resumo.classes_desativadas))
    return 'Classes atualizadas: ' + '; '.join(partes) + '.'
