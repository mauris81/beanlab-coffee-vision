"""Ponto de entrada para rodar a plataforma localmente.

Jeito mais fácil: dois cliques em "Iniciar BeanLab.bat".

Pelo terminal (celulares na mesma rede Wi-Fi conseguem acessar):
    python run.py

No modo normal usa o servidor waitress, feito para vários celulares ao mesmo tempo.

Modo desenvolvimento (servidor do Flask: recarrega ao salvar e mostra erros
detalhados, mas só aceita conexões deste computador):
    PowerShell:  $env:CAFE_DEBUG = "1"; python run.py

Outras variáveis opcionais:
    CAFE_PORT=5000             porta do servidor
    CAFE_ABRIR_NAVEGADOR=1     abre o navegador quando o servidor estiver pronto
"""
import os
import socket
import sys
import threading
import time
import webbrowser

from app import create_app
from app.cli import descrever_resumo
from app.servicos.banco import preparar_banco
from app.servicos.contas import codigo_de_primeiro_acesso
from app.servicos.taxonomias import TaxonomiaInvalida

app = create_app()


def endereco_na_rede():
    """Descobre o IP deste PC no Wi-Fi (ex.: 192.168.0.4), ou None se não houver rede."""
    try:
        # Conectar um socket UDP não envia nada; só pergunta ao sistema qual
        # interface de rede seria usada para sair para a internet.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
    except OSError:
        return None


def abrir_navegador_quando_pronto(porta):
    """Espera o servidor aceitar conexões e então abre o navegador."""
    def esperar_e_abrir():
        for _ in range(120):  # até 60 segundos
            try:
                with socket.create_connection(('127.0.0.1', porta), timeout=0.5):
                    webbrowser.open(f'http://127.0.0.1:{porta}')
                    return
            except OSError:
                time.sleep(0.5)

    threading.Thread(target=esperar_e_abrir, daemon=True).start()


if __name__ == '__main__':
    sys.stdout.reconfigure(line_buffering=True)  # mensagens aparecem na hora, mesmo em arquivo de log
    debug = os.environ.get('CAFE_DEBUG') == '1'
    # O depurador do Werkzeug permite executar código Python pelo navegador.
    # Por isso, com debug ligado, o servidor fica restrito a este computador.
    host = '127.0.0.1' if debug else '0.0.0.0'
    port = int(os.environ.get('CAFE_PORT', '5000'))

    # Com debug, o Flask reinicia o script num segundo processo; a mensagem e o
    # navegador só devem aparecer uma vez.
    primeira_execucao = os.environ.get('WERKZEUG_RUN_MAIN') != 'true'
    if primeira_execucao:
        # Aplica migrações pendentes e lê taxonomias/*.yaml antes de abrir as portas.
        try:
            with app.app_context():
                resumo = preparar_banco()
        except TaxonomiaInvalida as erro:
            print(f'\n  ERRO num arquivo de classes (pasta taxonomias/):\n  {erro}\n'
                  '  Corrija o arquivo e abra a plataforma de novo.\n')
            sys.exit(1)

        ip = endereco_na_rede()
        print()
        print(f'  Dados em: {app.config["PASTA_DADOS"]}')
        print(f'  {descrever_resumo(resumo)}')
        print()
        print('  BeanLab Coffee Vision está no ar')
        print(f'  {"Neste computador:":<28} http://127.0.0.1:{port}')
        if ip and not debug:
            print(f'  {"Nos celulares (mesmo Wi-Fi):":<28} http://{ip}:{port}')
        print('  Para desligar, feche esta janela (ou Ctrl+C).')
        print()
        with app.app_context():
            codigo = codigo_de_primeiro_acesso(app.config['PASTA_DADOS'])
        if codigo:
            print('  ============================================================')
            print(f'  PRIMEIRO ACESSO: abra a plataforma e use o código  {codigo}')
            print('  para criar a conta de administração.')
            print('  ============================================================')
            print()
        if os.environ.get('CAFE_ABRIR_NAVEGADOR') == '1':
            abrir_navegador_quando_pronto(port)

    # O processo que atende as páginas retoma as segmentações que ficaram pela metade.
    # (No modo desenvolvimento, é o processo filho criado pelo recarregador.)
    atende_paginas = not debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    if atende_paginas and (retomadas := app.extensions['fila_segmentacao'].retomar_pendentes()):
        print(f'  Retomando {retomadas} segmentação(ões) que ficaram pela metade.')

    if debug:
        app.run(debug=True, host=host, port=port)
    else:
        from waitress import serve
        serve(app, host=host, port=port, threads=8)
