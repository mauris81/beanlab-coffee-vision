"""Guarda cada foto com o nome igual ao hash SHA-256 do seu conteúdo.

    <pasta>/imagens/3f/a2/3fa2c9...e1.jpg

Por quê:
- Dois arquivos "IMG_0001.jpg" diferentes nunca se sobrescrevem.
- A mesma foto enviada duas vezes ocupa espaço uma vez só.
- As duas subpastas (3f/a2) evitam milhares de arquivos numa pasta só.
O nome original do arquivo fica guardado no banco (Imagem.nome_original).
"""
import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Extensões equivalentes viram uma só, para a mesma foto não ser guardada duas vezes.
_EXTENSAO_CANONICA = {'jpeg': 'jpg', 'tif': 'tiff'}


@dataclass(frozen=True)
class ArquivoSalvo:
    hash_sha256: str
    extensao: str
    caminho: Path
    tamanho_bytes: int
    ja_existia: bool


class ArmazenamentoImagens:
    def __init__(self, pasta_base: Path):
        self.pasta_base = Path(pasta_base)

    @staticmethod
    def extensao_canonica(extensao: str) -> str:
        extensao = extensao.lower().lstrip('.')
        return _EXTENSAO_CANONICA.get(extensao, extensao)

    def caminho(self, hash_sha256: str, extensao: str) -> Path:
        extensao = self.extensao_canonica(extensao)
        return self.pasta_base / hash_sha256[:2] / hash_sha256[2:4] / f'{hash_sha256}.{extensao}'

    def caminho_miniatura(self, hash_sha256: str) -> Path:
        """Miniatura JPEG ao lado do original: 3fa2...e1.mini.jpg"""
        return self.pasta_base / hash_sha256[:2] / hash_sha256[2:4] / f'{hash_sha256}.mini.jpg'

    def remover(self, hash_sha256: str, extensao: str) -> None:
        """Apaga o original e a miniatura. Só chame se nenhuma Imagem usar mais este hash."""
        self.caminho(hash_sha256, extensao).unlink(missing_ok=True)
        self.caminho_miniatura(hash_sha256).unlink(missing_ok=True)

    def salvar(self, conteudo: bytes, extensao: str) -> ArquivoSalvo:
        """Grava o conteúdo (se ainda não existir) e devolve onde ficou."""
        hash_sha256 = hashlib.sha256(conteudo).hexdigest()
        extensao = self.extensao_canonica(extensao)
        destino = self.caminho(hash_sha256, extensao)
        ja_existia = destino.exists()

        if not ja_existia:
            destino.parent.mkdir(parents=True, exist_ok=True)
            # Grava num arquivo temporário e só então renomeia: se a energia cair
            # no meio, não sobra uma foto pela metade com o nome definitivo.
            descritor, temporario = tempfile.mkstemp(dir=destino.parent, suffix='.parcial')
            try:
                with os.fdopen(descritor, 'wb') as arquivo:
                    arquivo.write(conteudo)
                os.replace(temporario, destino)
            except BaseException:
                Path(temporario).unlink(missing_ok=True)
                raise

        return ArquivoSalvo(hash_sha256, extensao, destino, len(conteudo), ja_existia)
