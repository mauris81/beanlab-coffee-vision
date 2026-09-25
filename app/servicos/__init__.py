"""Casos de uso: as regras do sistema, independentes de tela.

Convenção: os serviços PREPARAM as mudanças no banco (add/flush), e quem os chama
(uma rota, um comando ou um teste) CONFIRMA com `db.session.commit()`. Assim, uma
operação que usa vários serviços é gravada inteira ou não é gravada.
"""
