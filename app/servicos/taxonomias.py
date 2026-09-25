"""Lê as listas de classes de `taxonomias/*.yaml` e as grava no banco.

Fluxo: ler_taxonomias() valida os arquivos -> sincronizar_taxonomias() cria ou
atualiza TipoAmostra e Classe. Rodar várias vezes não duplica nada.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from sqlalchemy import select

from app.dominio import Classe, TipoAmostra
from app.extensions import db

_CODIGO = re.compile(r'^[a-z][a-z0-9_]{0,39}$')
_COR = re.compile(r'^#[0-9A-Fa-f]{6}$')
_TECLA = re.compile(r'^[0-9a-z]$')
_CAMPOS_TIPO = {'codigo', 'nome', 'descricao', 'ordem', 'classes'}
_CAMPOS_CLASSE = {'codigo', 'nome', 'descricao', 'cor', 'tecla'}


class TaxonomiaInvalida(ValueError):
    """Um arquivo de taxonomia tem erro. A mensagem diz qual arquivo e o quê."""


@dataclass(frozen=True)
class DefinicaoClasse:
    codigo: str
    nome: str
    cor: str
    tecla: str | None
    descricao: str | None
    ordem: int


@dataclass(frozen=True)
class DefinicaoTipo:
    codigo: str
    nome: str
    descricao: str | None
    ordem: int
    classes: tuple[DefinicaoClasse, ...]


@dataclass
class ResumoSincronizacao:
    tipos_criados: list[str] = field(default_factory=list)
    classes_criadas: list[str] = field(default_factory=list)
    classes_desativadas: list[str] = field(default_factory=list)
    classes_reativadas: list[str] = field(default_factory=list)

    @property
    def houve_mudanca(self) -> bool:
        return any([self.tipos_criados, self.classes_criadas,
                    self.classes_desativadas, self.classes_reativadas])


# ---------------------------------------------------------------- leitura

def ler_taxonomias(pasta: Path) -> list[DefinicaoTipo]:
    """Lê e valida todos os .yaml da pasta. Para no primeiro erro, com mensagem clara."""
    arquivos = sorted(Path(pasta).glob('*.yaml'))
    if not arquivos:
        raise TaxonomiaInvalida(f'Nenhum arquivo .yaml encontrado em {pasta}.')

    tipos = [_ler_arquivo(arquivo) for arquivo in arquivos]
    vistos = {}
    for arquivo, tipo in zip(arquivos, tipos):
        if tipo.codigo in vistos:
            raise TaxonomiaInvalida(
                f'{arquivo.name}: o código "{tipo.codigo}" já é usado em {vistos[tipo.codigo]}.')
        vistos[tipo.codigo] = arquivo.name
    return sorted(tipos, key=lambda t: (t.ordem, t.codigo))


def _ler_arquivo(caminho: Path) -> DefinicaoTipo:
    local = caminho.name
    try:
        dados = yaml.safe_load(caminho.read_text(encoding='utf-8'))
    except yaml.YAMLError as erro:
        linha = getattr(getattr(erro, 'problem_mark', None), 'line', None)
        onde = f' (perto da linha {linha + 1})' if linha is not None else ''
        raise TaxonomiaInvalida(f'{local}: erro de formatação{onde}. Confira recuos e aspas.') from erro

    if not isinstance(dados, dict):
        raise TaxonomiaInvalida(f'{local}: o arquivo deve começar com "codigo:", "nome:" e "classes:".')
    _conferir_campos(dados, _CAMPOS_TIPO, {'codigo', 'nome', 'classes'}, local)

    codigo = _codigo(dados['codigo'], local)
    classes_brutas = dados['classes']
    if not isinstance(classes_brutas, list) or not classes_brutas:
        raise TaxonomiaInvalida(f'{local}: "classes" deve ser uma lista com pelo menos uma classe.')

    classes = tuple(
        _ler_classe(bruta, ordem, f'{local}, classe nº {ordem + 1}')
        for ordem, bruta in enumerate(classes_brutas)
    )
    _conferir_repetidos(classes, 'codigo', local)
    _conferir_repetidos([c for c in classes if c.tecla], 'tecla', local)

    return DefinicaoTipo(
        codigo=codigo,
        nome=_texto(dados['nome'], 'nome', local, maximo=80),
        descricao=_texto_opcional(dados.get('descricao')),
        ordem=int(dados.get('ordem', 0)),
        classes=classes,
    )


def _ler_classe(dados, ordem: int, local: str) -> DefinicaoClasse:
    if not isinstance(dados, dict):
        raise TaxonomiaInvalida(f'{local}: cada classe deve ter "codigo", "nome" e "cor".')
    _conferir_campos(dados, _CAMPOS_CLASSE, {'codigo', 'nome', 'cor'}, local)

    cor = str(dados['cor'])
    if not _COR.match(cor):
        raise TaxonomiaInvalida(f'{local}: cor "{cor}" inválida. Use o formato "#RRGGBB", entre aspas.')

    tecla = dados.get('tecla')
    if tecla is not None:
        tecla = str(tecla).lower()  # o YAML lê `tecla: 1` como número
        if not _TECLA.match(tecla):
            raise TaxonomiaInvalida(f'{local}: tecla "{tecla}" inválida. Use um único número ou letra.')

    return DefinicaoClasse(
        codigo=_codigo(dados['codigo'], local),
        nome=_texto(dados['nome'], 'nome', local, maximo=80),
        cor=cor.upper(),
        tecla=tecla,
        descricao=_texto_opcional(dados.get('descricao')),
        ordem=ordem,
    )


def _conferir_campos(dados: dict, validos: set, obrigatorios: set, local: str):
    if desconhecidos := set(dados) - validos:
        raise TaxonomiaInvalida(
            f'{local}: campo desconhecido "{sorted(desconhecidos)[0]}". '
            f'Campos válidos: {", ".join(sorted(validos))}.')
    if faltando := obrigatorios - set(dados):
        raise TaxonomiaInvalida(f'{local}: falta o campo "{sorted(faltando)[0]}".')


def _conferir_repetidos(classes, atributo: str, local: str):
    vistos = {}
    for classe in classes:
        valor = getattr(classe, atributo)
        if valor in vistos:
            raise TaxonomiaInvalida(
                f'{local}: "{valor}" está repetido no campo "{atributo}" '
                f'(classes "{vistos[valor]}" e "{classe.codigo}").')
        vistos[valor] = classe.codigo


def _codigo(valor, local: str) -> str:
    valor = str(valor)
    if not _CODIGO.match(valor):
        raise TaxonomiaInvalida(
            f'{local}: código "{valor}" inválido. Use só letras minúsculas sem acento, '
            f'números e "_", começando por letra (ex.: "bicho_mineiro").')
    return valor


def _texto(valor, campo: str, local: str, maximo: int) -> str:
    texto = ' '.join(str(valor or '').split())
    if not texto:
        raise TaxonomiaInvalida(f'{local}: o campo "{campo}" está vazio.')
    if len(texto) > maximo:
        raise TaxonomiaInvalida(f'{local}: o campo "{campo}" passa de {maximo} caracteres.')
    return texto


def _texto_opcional(valor) -> str | None:
    if valor is None:
        return None
    return ' '.join(str(valor).split()) or None


# ---------------------------------------------------------------- gravação

def sincronizar_taxonomias(definicoes: list[DefinicaoTipo]) -> ResumoSincronizacao:
    """Deixa o banco igual aos arquivos. Não confirma (commit): quem chama decide.

    - Tipo ou classe novos são criados.
    - Nome, cor, descrição, tecla e ordem são atualizados.
    - Classe que sumiu do arquivo fica INATIVA (não é apagada, pode ter anotações).
    """
    resumo = ResumoSincronizacao()
    for definicao in definicoes:
        tipo = db.session.scalar(select(TipoAmostra).filter_by(codigo=definicao.codigo))
        if tipo is None:
            tipo = TipoAmostra(codigo=definicao.codigo)
            db.session.add(tipo)
            resumo.tipos_criados.append(definicao.codigo)
        tipo.nome = definicao.nome
        tipo.descricao = definicao.descricao
        tipo.ordem = definicao.ordem

        # Libera todas as teclas antes de redistribuir; senão trocar a tecla de duas
        # classes entre si violaria a regra "uma tecla por classe" no meio do caminho.
        for classe in tipo.classes:
            classe.tecla_atalho = None
        db.session.flush()

        existentes = {c.codigo: c for c in tipo.classes}
        for def_classe in definicao.classes:
            classe = existentes.pop(def_classe.codigo, None)
            nome_completo = f'{definicao.codigo}/{def_classe.codigo}'
            if classe is None:
                classe = Classe(codigo=def_classe.codigo, tipo_amostra=tipo)
                db.session.add(classe)
                resumo.classes_criadas.append(nome_completo)
            elif not classe.ativa:
                classe.ativa = True
                resumo.classes_reativadas.append(nome_completo)
            classe.nome = def_classe.nome
            classe.cor = def_classe.cor
            classe.tecla_atalho = def_classe.tecla
            classe.descricao = def_classe.descricao
            classe.ordem = def_classe.ordem

        for classe in existentes.values():  # sobraram: não estão mais no arquivo
            if classe.ativa:
                classe.ativa = False
                resumo.classes_desativadas.append(f'{definicao.codigo}/{classe.codigo}')
    db.session.flush()
    return resumo
