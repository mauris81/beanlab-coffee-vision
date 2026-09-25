"""Administração de pessoas (só para administradores): criar contas, redefinir senha,
mudar perfil, desativar e reativar.

Senhas provisórias aparecem UMA vez, na resposta da própria ação (não vão para
mensagens da sessão, que ficam gravadas num cookie).
"""
from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import select

from app.dominio import Papel, Pessoa
from app.extensions import db
from app.servicos.contas import (
    ContaInvalida, criar_conta, definir_papel, desativar, reativar, redefinir_senha,
)
from app.web import web_bp
from app.web.identidade import exige_administrador, pessoa_atual


def _pessoa_ou_404(pessoa_id: int) -> Pessoa:
    return db.session.get(Pessoa, pessoa_id) or abort(404)


def _lista(erro=None, dados=None, status=200):
    pessoas = db.session.scalars(select(Pessoa).order_by(Pessoa.ativa.desc(), Pessoa.nome)).all()
    return render_template('admin_pessoas.html', pessoas=pessoas, erro=erro, dados=dados or {},
                           papeis=list(Papel)), status


@web_bp.get('/pessoas')
@exige_administrador
def pessoas():
    return _lista()


@web_bp.post('/pessoas')
@exige_administrador
def criar_pessoa():
    papel = Papel.ADMINISTRADOR if request.form.get('papel') == Papel.ADMINISTRADOR else Papel.MEMBRO
    try:
        pessoa, senha = criar_conta(request.form.get('nome', ''), request.form.get('usuario', ''), papel)
    except ContaInvalida as problema:
        return _lista(erro=str(problema), dados=request.form, status=422)
    db.session.commit()
    return render_template('admin_senha.html', pessoa=pessoa, senha=senha, nova=True)


@web_bp.post('/pessoas/<int:pessoa_id>/senha')
@exige_administrador
def redefinir_senha_da_pessoa(pessoa_id):
    pessoa = _pessoa_ou_404(pessoa_id)
    senha = redefinir_senha(pessoa)
    db.session.commit()
    return render_template('admin_senha.html', pessoa=pessoa, senha=senha, nova=False)


@web_bp.post('/pessoas/<int:pessoa_id>/papel')
@exige_administrador
def mudar_papel(pessoa_id):
    pessoa = _pessoa_ou_404(pessoa_id)
    novo = Papel.ADMINISTRADOR if request.form.get('papel') == Papel.ADMINISTRADOR else Papel.MEMBRO
    try:
        definir_papel(pessoa, novo)
    except ContaInvalida as problema:
        flash(str(problema), 'aviso')
    else:
        db.session.commit()
        flash(f'{pessoa.nome} agora é {"administração" if novo == Papel.ADMINISTRADOR else "membro"}.', 'sucesso')
    return redirect(url_for('web.pessoas'))


@web_bp.post('/pessoas/<int:pessoa_id>/desativar')
@exige_administrador
def desativar_pessoa(pessoa_id):
    pessoa = _pessoa_ou_404(pessoa_id)
    try:
        desativar(pessoa, feito_por=pessoa_atual())
    except ContaInvalida as problema:
        flash(str(problema), 'aviso')
    else:
        db.session.commit()
        flash(f'Conta de {pessoa.nome} desativada. As anotações dela continuam guardadas.', 'info')
    return redirect(url_for('web.pessoas'))


@web_bp.post('/pessoas/<int:pessoa_id>/reativar')
@exige_administrador
def reativar_pessoa(pessoa_id):
    pessoa = _pessoa_ou_404(pessoa_id)
    reativar(pessoa)
    db.session.commit()
    flash(f'Conta de {pessoa.nome} reativada.', 'sucesso')
    return redirect(url_for('web.pessoas'))
