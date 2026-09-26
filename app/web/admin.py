"""Administração de pessoas (só para administradores): criar contas, redefinir senha,
mudar perfil, desativar, reativar e excluir.

Senhas provisórias aparecem UMA vez, na resposta da própria ação (não vão para
mensagens da sessão, que ficam gravadas num cookie).
"""
from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import select

from app.dominio import Papel, Pessoa
from app.extensions import db
from app.servicos.contas import (
    ContaInvalida, criar_conta, definir_papel, desativar, excluir_conta, reativar, redefinir_senha,
    tem_trabalho,
)
from app.web import web_bp
from app.web.identidade import exige_administrador, pessoa_atual


def _pessoa_ou_404(pessoa_id: int) -> Pessoa:
    pessoa = db.session.get(Pessoa, pessoa_id)
    if pessoa is None or pessoa.removida_em:  # conta excluída não tem mais ações
        abort(404)
    return pessoa


def _lista(erro=None, dados=None, status=200):
    todas = db.session.scalars(select(Pessoa).order_by(Pessoa.ativa.desc(), Pessoa.nome)).all()
    pessoas = [p for p in todas if not p.removida_em]
    return render_template('admin_pessoas.html', pessoas=pessoas, erro=erro, dados=dados or {},
                           papeis=list(Papel), removidas=len(todas) - len(pessoas),
                           com_trabalho={p.id for p in pessoas if tem_trabalho(p)}), status


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


@web_bp.post('/pessoas/<int:pessoa_id>/excluir')
@exige_administrador
def excluir_pessoa(pessoa_id):
    pessoa = _pessoa_ou_404(pessoa_id)
    nome = pessoa.nome
    try:
        resultado = excluir_conta(pessoa, feito_por=pessoa_atual())
    except ContaInvalida as problema:
        flash(str(problema), 'aviso')
    else:
        db.session.commit()
        flash(f'Conta de {nome} excluída.' if resultado == 'apagada' else
              f'Conta de {nome} excluída. O que ela anotou continua na pesquisa, sem o nome '
              f'(aparece como "{pessoa.nome}").', 'info')
    return redirect(url_for('web.pessoas'))
