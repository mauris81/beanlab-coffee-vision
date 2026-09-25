"""Leitura dos arquivos de classes (taxonomias/*.yaml) e gravação no banco."""
import shutil
import textwrap

import pytest
import yaml

from app.config import RAIZ_DO_PROJETO
from app.extensions import db
from app.servicos.taxonomias import TaxonomiaInvalida, ler_taxonomias, sincronizar_taxonomias
from tests.conftest import classe, tipo

PASTA_REAL = RAIZ_DO_PROJETO / 'taxonomias'


def escrever(pasta, nome, texto):
    (pasta / nome).write_text(textwrap.dedent(texto), encoding='utf-8')


VALIDO = """\
    codigo: teste
    nome: Teste
    classes:
      - codigo: a
        nome: Classe A
        tecla: 1
        cor: "#112233"
      - codigo: b
        nome: Classe B
        tecla: "2"
        cor: "#445566"
"""


def test_arquivos_do_projeto_sao_validos():
    tipos = ler_taxonomias(PASTA_REAL)
    assert [t.codigo for t in tipos] == ['graos', 'folhas', 'flores', 'frutos']
    assert all(len(t.classes) >= 2 for t in tipos)


def test_banco_recebe_todas_as_classes_ao_iniciar(app):
    assert len(tipo('graos').classes) == 9
    assert classe('folhas', 'ferrugem').nome == 'Ferrugem'
    assert classe('folhas', 'ferrugem').tecla_atalho == '2'


def test_sincronizar_de_novo_nao_muda_nada(app):
    resumo = sincronizar_taxonomias(ler_taxonomias(PASTA_REAL))
    assert not resumo.houve_mudanca
    assert len(tipo('graos').classes) == 9


def test_tecla_numerica_sem_aspas_e_aceita(tmp_path):
    escrever(tmp_path, 'teste.yaml', VALIDO)
    [definicao] = ler_taxonomias(tmp_path)
    assert [c.tecla for c in definicao.classes] == ['1', '2']


def test_classe_removida_fica_inativa_e_volta_se_readicionada(app, tmp_path):
    pasta = tmp_path / 'tax'
    shutil.copytree(PASTA_REAL, pasta)
    arquivo = pasta / 'flores.yaml'
    original = arquivo.read_text(encoding='utf-8')
    dados = yaml.safe_load(original)
    dados['classes'] = [c for c in dados['classes'] if c['codigo'] != 'flor_murcha']
    arquivo.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding='utf-8')

    resumo = sincronizar_taxonomias(ler_taxonomias(pasta))
    assert resumo.classes_desativadas == ['flores/flor_murcha']
    murcha = classe('flores', 'flor_murcha')
    assert murcha.ativa is False
    assert murcha not in tipo('flores').classes_ativas

    arquivo.write_text(original, encoding='utf-8')
    resumo = sincronizar_taxonomias(ler_taxonomias(pasta))
    assert resumo.classes_reativadas == ['flores/flor_murcha']
    assert classe('flores', 'flor_murcha').ativa is True


def test_trocar_teclas_entre_duas_classes(app, tmp_path):
    escrever(tmp_path, 'teste.yaml', VALIDO)
    sincronizar_taxonomias(ler_taxonomias(tmp_path))
    escrever(tmp_path, 'teste.yaml', VALIDO.replace('tecla: 1', 'tecla: X')
             .replace('tecla: "2"', 'tecla: "1"').replace('tecla: X', 'tecla: "2"'))
    sincronizar_taxonomias(ler_taxonomias(tmp_path))
    db.session.commit()
    assert classe('teste', 'a').tecla_atalho == '2'
    assert classe('teste', 'b').tecla_atalho == '1'


@pytest.mark.parametrize('troca, trecho_da_mensagem', [
    (('tecla: "2"', 'tecl: "2"'), 'campo desconhecido "tecl"'),
    (('"#445566"', '"azul"'), 'cor "azul" inválida'),
    (('tecla: "2"', 'tecla: "1"'), '"1" está repetido no campo "tecla"'),
    (('codigo: b', 'codigo: a'), '"a" está repetido no campo "codigo"'),
    (('codigo: b', 'codigo: Média'), 'código "Média" inválido'),
    (('tecla: "2"', 'tecla: "22"'), 'tecla "22" inválida'),
    (('nome: Classe B', 'nome: "  "'), 'o campo "nome" está vazio'),
    (('    cor: "#445566"\n', ''), 'falta o campo "cor"'),
    (('classes:', 'classes: []\nsobra:'), 'campo desconhecido "sobra"'),
    (('  - codigo: a', '  - codigo: a\n  x'), 'erro de formatação'),
])
def test_erros_no_arquivo_geram_mensagem_clara(tmp_path, troca, trecho_da_mensagem):
    escrever(tmp_path, 'teste.yaml', VALIDO)
    arquivo = tmp_path / 'teste.yaml'
    arquivo.write_text(arquivo.read_text(encoding='utf-8').replace(*troca, 1), encoding='utf-8')
    with pytest.raises(TaxonomiaInvalida, match='teste.yaml') as erro:
        ler_taxonomias(tmp_path)
    assert trecho_da_mensagem in str(erro.value)


def test_mesmo_codigo_de_tipo_em_dois_arquivos(tmp_path):
    escrever(tmp_path, 'a.yaml', VALIDO)
    escrever(tmp_path, 'b.yaml', VALIDO)
    with pytest.raises(TaxonomiaInvalida, match='"teste" já é usado em a.yaml'):
        ler_taxonomias(tmp_path)


def test_pasta_sem_arquivos(tmp_path):
    with pytest.raises(TaxonomiaInvalida, match='Nenhum arquivo .yaml'):
        ler_taxonomias(tmp_path)
