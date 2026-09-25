"""Ponto de entrada para rodar a plataforma localmente.

Uso normal (celulares na mesma rede Wi-Fi conseguem acessar):
    python run.py

Modo desenvolvimento (recarrega ao salvar e mostra erros detalhados,
mas só aceita conexões deste computador):
    PowerShell:  $env:CAFE_DEBUG = "1"; python run.py
"""
import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    debug = os.environ.get('CAFE_DEBUG') == '1'
    # O depurador do Werkzeug permite executar código Python pelo navegador.
    # Por isso, com debug ligado, o servidor fica restrito a este computador.
    host = '127.0.0.1' if debug else '0.0.0.0'
    port = int(os.environ.get('CAFE_PORT', '5000'))
    app.run(debug=debug, host=host, port=port)
