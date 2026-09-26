"""Comandos de terminal. Uso: `flask --app app <comando>` (com o .venv ativo)."""
import click

from app.servicos.banco import preparar_banco


def registrar_comandos(app):
    registrar_comandos_da_ia(app)
    registrar_comando_de_exportacao(app)

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


def registrar_comandos_da_ia(app):
    @app.cli.command('baixar-modelos')
    def comando_baixar_modelos():
        """Baixa os pesos da IA (~180 MB) para <pasta de dados>/modelos, conferindo o hash."""
        from app.segmentacao.ia import DownloadInvalido, baixar_modelos
        try:
            for mensagem in baixar_modelos(app.config['PASTA_MODELOS']):
                click.echo(f'  {mensagem}')
        except (DownloadInvalido, OSError) as erro:
            raise click.ClickException(f'Não foi possível baixar: {erro}') from erro

    @app.cli.command('verificar-ia')
    def comando_verificar_ia():
        """Confere se a IA roda neste computador (segmenta uma imagem de teste)."""
        import time

        import numpy as np

        from app.segmentacao import obter_motor
        motor = obter_motor('ia')
        if not motor.disponivel():
            raise click.ClickException('A IA não está completa: faltam bibliotecas ou modelos. '
                                       'Rode "Instalar IA.bat" de novo.')
        # Imagem de teste: 12 "grãos" (elipses) sobre fundo claro.
        imagem = np.full((600, 800, 3), 225, np.uint8)
        import cv2
        for i in range(12):
            centro = (90 + (i % 4) * 190, 110 + (i // 4) * 190)
            cv2.ellipse(imagem, centro, (55, 38), 25 * i, 0, 360, (95, 120, 80), -1)
        inicio = time.perf_counter()
        regioes = motor.segmentar(imagem)
        click.echo(f'  IA funcionando: {len(regioes)} de 12 objetos de teste em '
                   f'{time.perf_counter() - inicio:.0f} s.')


def registrar_comando_de_exportacao(app):
    @app.cli.command('exportar')
    @click.argument('tipo')
    @click.option('--coleta', 'coletas', multiple=True, type=int, help='id da coleta (pode repetir); padrão: todas')
    @click.option('--formatos', default='coco,yolo,recortes', show_default=True,
                  help='além da planilha, que vai sempre (vazio = só a planilha)')
    @click.option('--incluir-duvidas', is_flag=True, help='formatos de treino com as regiões em dúvida')
    @click.option('--incluir-incompletas', is_flag=True, help='COCO/YOLO também com fotos com pendentes')
    @click.option('--saida', type=click.Path(), help='arquivo .zip (padrão: pasta atual)')
    def comando_exportar(tipo, coletas, formatos, incluir_duvidas, incluir_incompletas, saida):
        """Exporta os dados de um TIPO de amostra (ex.: graos) num .zip. Útil para exportações grandes."""
        from pathlib import Path

        from sqlalchemy import select

        from app.dominio import TipoAmostra
        from app.extensions import db
        from app.servicos.exportacao import FORMATOS, PedidoDeExportacao, exportar, nome_do_arquivo
        tipo_amostra = db.session.scalar(select(TipoAmostra).filter_by(codigo=tipo))
        if tipo_amostra is None:
            raise click.ClickException(f'Tipo de amostra "{tipo}" não existe.')
        escolhidos = {f.strip() for f in formatos.split(',') if f.strip()}
        if desconhecidos := escolhidos - set(FORMATOS):
            raise click.ClickException(f'Formato desconhecido: {", ".join(desconhecidos)}. Use: {", ".join(FORMATOS)}.')
        pedido = PedidoDeExportacao(tipo=tipo_amostra, coleta_ids=tuple(coletas), formatos=frozenset(escolhidos),
                                    sem_duvidas=not incluir_duvidas, so_fotos_completas=not incluir_incompletas)
        destino = Path(saida or f'{nome_do_arquivo(pedido)}.zip')
        conteudo = exportar(pedido, destino)
        click.echo(f'{destino}: fotos {conteudo.fotos}, regiões {len(conteudo.linhas)} '
                   f'(anotadas {conteudo.anotadas}); fotos de treino {len(conteudo.fotos_de_treino)}.')


def descrever_motores() -> str:
    """Uma linha: qual motor cada tipo de amostra está usando (mostrada ao iniciar)."""
    from sqlalchemy import select

    from app.dominio import TipoAmostra
    from app.extensions import db
    nomes = {'ia': 'IA', 'classico': 'clássico'}
    tipos = db.session.scalars(select(TipoAmostra).order_by(TipoAmostra.ordem)).all()
    com_motor = [f'{t.nome} ({nomes.get(t.motor_padrao, t.motor_padrao)})' for t in tipos if t.motor_padrao]
    return 'Segmentação automática: ' + (', '.join(com_motor) if com_motor else 'nenhuma') + '.'


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
