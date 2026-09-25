"""Contas de acesso: criar, entrar, trocar senha, administrar.

Decisões (docs/decisoes/0006-login-e-contas.md):
- O administrador cria as contas e passa uma senha provisória; a pessoa troca no
  primeiro acesso. Sem e-mail: senha esquecida o administrador redefine.
- Senhas guardadas só como hash (scrypt, via Werkzeug); nunca em texto.
- Mensagem igual para "usuário não existe" e "senha errada" (não revela quem tem conta).
- 5 tentativas erradas seguidas bloqueiam a conta por 5 minutos.
- A plataforma nunca fica sem administrador ativo.
- O PRIMEIRO administrador exige um código mostrado só na janela do servidor, para
  ninguém de fora se cadastrar como administrador se a plataforma for publicada antes.

Os serviços não confirmam (commit): quem chama decide.
"""
import secrets
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select
from werkzeug.security import check_password_hash, generate_password_hash

from app.dominio import Papel, Pessoa
from app.dominio.tipos import agora_utc
from app.extensions import db

TENTATIVAS_ANTES_DO_BLOQUEIO = 5
TEMPO_DE_BLOQUEIO = timedelta(minutes=5)
TAMANHO_MINIMO_SENHA = 8
_SENHAS_OBVIAS = {
    '12345678', '123456789', '1234567890', '87654321', '11111111', '00000000', 'senha123',
    'senha1234', 'password', 'password1', 'qwerty123', 'abcd1234', 'cafe1234', 'cafecafe',
    'mudar123', 'admin123', 'beanlab1', 'brasil123',
}
# Hash de uma senha qualquer: comparar com ele quando o usuário não existe gasta o mesmo
# tempo de uma conta real (não dá para descobrir usuários pelo tempo de resposta).
_HASH_FALSO = generate_password_hash(secrets.token_hex(16))
_PALAVRAS = ('cafe', 'grao', 'folha', 'flor', 'fruto', 'terra', 'chuva', 'sol', 'lua', 'rio',
             'serra', 'campo', 'safra', 'broto', 'raiz', 'semente', 'colheita', 'vale')


class ContaInvalida(ValueError):
    """Pedido que quebra uma regra de contas. A mensagem é para mostrar à pessoa."""


class FalhaDeLogin(ValueError):
    """Não foi possível entrar. A mensagem é para mostrar à pessoa."""


# ------------------------------------------------------------------- senhas

def gerar_senha_provisoria() -> str:
    """Fácil de ditar por telefone e de digitar no celular. Ex.: 'safra-lua-4821'."""
    return f'{secrets.choice(_PALAVRAS)}-{secrets.choice(_PALAVRAS)}-{secrets.randbelow(9000) + 1000}'


def validar_senha(senha: str, usuario: str = '') -> None:
    if len(senha or '') < TAMANHO_MINIMO_SENHA:
        raise ContaInvalida(f'A senha precisa de pelo menos {TAMANHO_MINIMO_SENHA} caracteres.')
    if senha.casefold() in _SENHAS_OBVIAS or len(set(senha)) < 4:
        raise ContaInvalida('Essa senha é fácil demais de adivinhar. Tente uma frase curta, '
                            'como "cafe-da-serra-2026".')
    if usuario and usuario.casefold() in senha.casefold():
        raise ContaInvalida('A senha não pode conter o nome de usuário.')


def _definir_senha(pessoa: Pessoa, senha: str, *, provisoria: bool) -> None:
    pessoa.senha_hash = generate_password_hash(senha)
    pessoa.precisa_trocar_senha = provisoria
    pessoa.tentativas_falhas = 0
    pessoa.bloqueada_ate = None
    pessoa.versao_sessao = (pessoa.versao_sessao or 0) + 1  # desconecta os outros aparelhos


# ------------------------------------------------------------------- contas

def buscar_por_usuario(usuario: str) -> Pessoa | None:
    return db.session.scalar(select(Pessoa).filter_by(usuario=Pessoa.normalizar_usuario(usuario)))


def criar_conta(nome: str, usuario: str, papel: Papel = Papel.MEMBRO,
                senha: str | None = None) -> tuple[Pessoa, str | None]:
    """Cria a conta. Sem `senha`, gera uma provisória e a devolve (mostre UMA vez)."""
    nome = ' '.join((nome or '').split())
    usuario_normalizado = Pessoa.normalizar_usuario(usuario or nome)
    if not nome:
        raise ContaInvalida('Informe o nome da pessoa.')
    if len(usuario_normalizado) < 3:
        raise ContaInvalida('O usuário precisa de pelo menos 3 letras ou números.')
    if buscar_por_usuario(usuario_normalizado):
        raise ContaInvalida(f'O usuário "{usuario_normalizado}" já existe. Escolha outro '
                            f'(ex.: {usuario_normalizado}.2).')
    provisoria = senha is None
    senha = senha if senha is not None else gerar_senha_provisoria()
    if not provisoria:
        validar_senha(senha, usuario_normalizado)
    pessoa = Pessoa(nome=nome[:120], usuario=usuario_normalizado, papel=papel, versao_sessao=0)
    _definir_senha(pessoa, senha, provisoria=provisoria)
    db.session.add(pessoa)
    db.session.flush()
    return pessoa, (senha if provisoria else None)


def autenticar(usuario: str, senha: str) -> Pessoa:
    """Devolve a pessoa se usuário e senha conferem; senão levanta FalhaDeLogin.

    Mesmo quando falha, confirme (commit): a tentativa errada fica registrada e conta
    para o bloqueio.
    """
    pessoa = buscar_por_usuario(usuario)
    agora = agora_utc()
    if pessoa and pessoa.bloqueada_ate and pessoa.bloqueada_ate > agora:
        minutos = max(1, round((pessoa.bloqueada_ate - agora).total_seconds() / 60))
        raise FalhaDeLogin(f'Muitas tentativas erradas. Espere {minutos} minuto(s) e tente de novo.')

    senha_confere = check_password_hash(pessoa.senha_hash if pessoa and pessoa.senha_hash else _HASH_FALSO,
                                        senha or '')
    if not (pessoa and pessoa.senha_hash and senha_confere):
        if pessoa:
            pessoa.tentativas_falhas += 1
            if pessoa.tentativas_falhas >= TENTATIVAS_ANTES_DO_BLOQUEIO:
                pessoa.bloqueada_ate = agora + TEMPO_DE_BLOQUEIO
                pessoa.tentativas_falhas = 0
        raise FalhaDeLogin('Usuário ou senha incorretos.')
    if not pessoa.ativa:
        raise FalhaDeLogin('Esta conta foi desativada. Fale com o administrador da plataforma.')

    pessoa.tentativas_falhas = 0
    pessoa.bloqueada_ate = None
    pessoa.ultimo_acesso = agora
    return pessoa


def trocar_senha(pessoa: Pessoa, senha_atual: str, senha_nova: str) -> None:
    if not check_password_hash(pessoa.senha_hash or _HASH_FALSO, senha_atual or ''):
        raise ContaInvalida('A senha atual está incorreta.')
    if senha_nova == senha_atual:
        raise ContaInvalida('A senha nova precisa ser diferente da atual.')
    validar_senha(senha_nova, pessoa.usuario)
    _definir_senha(pessoa, senha_nova, provisoria=False)


def redefinir_senha(pessoa: Pessoa) -> str:
    """Administrador gera uma nova senha provisória. Desconecta a pessoa de todos os aparelhos."""
    senha = gerar_senha_provisoria()
    _definir_senha(pessoa, senha, provisoria=True)
    return senha


# ---------------------------------------------------------- administração

def administradores_ativos() -> int:
    return db.session.scalar(select(func.count(Pessoa.id)).where(
        Pessoa.papel == Papel.ADMINISTRADOR, Pessoa.ativa, Pessoa.senha_hash.is_not(None)))


def existe_administrador() -> bool:
    return administradores_ativos() > 0


def _garantir_outro_administrador(pessoa: Pessoa) -> None:
    if pessoa.eh_administrador and pessoa.ativa and administradores_ativos() <= 1:
        raise ContaInvalida('Esta é a única conta de administrador. Promova outra pessoa a '
                            'administrador antes.')


def definir_papel(pessoa: Pessoa, papel: Papel) -> None:
    if papel != Papel.ADMINISTRADOR:
        _garantir_outro_administrador(pessoa)
    pessoa.papel = papel


def desativar(pessoa: Pessoa, feito_por: Pessoa) -> None:
    if pessoa.id == feito_por.id:
        raise ContaInvalida('Você não pode desativar a sua própria conta.')
    _garantir_outro_administrador(pessoa)
    pessoa.ativa = False
    pessoa.versao_sessao += 1  # sai de todos os aparelhos na hora


def reativar(pessoa: Pessoa) -> None:
    pessoa.ativa = True


# --------------------------------------------------------- primeiro acesso

def _arquivo_do_codigo(pasta_dados: Path) -> Path:
    return Path(pasta_dados) / '.codigo_primeiro_acesso'


def codigo_de_primeiro_acesso(pasta_dados: Path) -> str | None:
    """Código para criar o primeiro administrador; None se já existe administrador.

    Fica num arquivo da pasta de dados (fora do git) e é mostrado na janela do servidor.
    """
    arquivo = _arquivo_do_codigo(pasta_dados)
    if existe_administrador():
        arquivo.unlink(missing_ok=True)
        return None
    if not arquivo.exists():
        arquivo.write_text(f'{secrets.randbelow(10**4):04d}-{secrets.randbelow(10**4):04d}', encoding='utf-8')
    return arquivo.read_text(encoding='utf-8').strip()


def criar_primeiro_administrador(pasta_dados: Path, codigo: str, nome: str, usuario: str,
                                 senha: str) -> Pessoa:
    esperado = codigo_de_primeiro_acesso(pasta_dados)
    if esperado is None:
        raise ContaInvalida('Já existe um administrador. Entre com a sua conta.')
    if not secrets.compare_digest((codigo or '').strip(), esperado):
        raise ContaInvalida('Código incorreto. Ele aparece na janela preta onde a plataforma está rodando.')
    pessoa, _ = criar_conta(nome, usuario, Papel.ADMINISTRADOR, senha=senha)
    _arquivo_do_codigo(pasta_dados).unlink(missing_ok=True)
    return pessoa
