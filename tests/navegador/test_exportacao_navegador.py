"""Exportar no navegador: a administração baixa o .zip de verdade."""
import zipfile
from pathlib import Path

import pytest

from app.dominio import Coleta, OrigemRegiao, Regiao, TipoAmostra
from app.extensions import db
from app.servicos.anotacoes import anotar_regiao
from app.servicos.ingestao import receber_foto
from tests.fabrica_imagens import foto_jpeg

pytestmark = pytest.mark.navegador


def test_baixar_exportacao(abrir, aplicacao, tmp_path):
    with aplicacao.app_context():
        graos = db.session.scalars(db.select(TipoAmostra).filter_by(codigo='graos')).one()
        coleta = Coleta(nome='Para exportar', tipo_amostra=graos)
        db.session.add(coleta)
        db.session.flush()
        imagem = receber_foto(coleta, foto_jpeg(cor=(7, 77, 7)), 'exportar.jpg', ja_segmentada=True).imagem
        imagem.regioes.append(Regiao.do_poligono([[5, 5], [60, 5], [60, 60], [5, 60]], origem=OrigemRegiao.MANUAL))
        db.session.flush()
        anotar_regiao(imagem.regioes[0], graos.classes[0])
        db.session.commit()

    pagina = abrir('/exportar?tipo=graos', como='admin')
    with pagina.expect_download() as espera:
        pagina.get_by_role('button', name='Baixar .zip').click()
    download = espera.value
    assert download.suggested_filename.startswith('beanlab_graos_') and download.suggested_filename.endswith('.zip')
    destino = tmp_path / download.suggested_filename
    download.save_as(destino)
    nomes = zipfile.ZipFile(destino).namelist()
    assert any(n.endswith('regioes.csv') for n in nomes) and any(n.endswith('data.yaml') for n in nomes)
    pasta_temporaria = Path(aplicacao.config['PASTA_DADOS']) / 'exportacoes'
    assert list(pasta_temporaria.glob('*.zip')) == []  # o temporário foi apagado depois do envio
    assert pagina.erros_js == []
