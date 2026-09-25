# 0004 — Visual que funciona sem internet: fonte do sistema e ícones próprios

**Status:** Aceita · 25/09/2026

## Contexto
A versão antiga carregava a fonte Inter do Google Fonts. Na fazenda, a internet é fraca
ou inexistente, e o celular acessa o servidor pela rede local. Sem internet, a página
esperava a fonte até desistir e depois trocava de letra no meio da leitura. Bibliotecas
de ícones em CDN teriam o mesmo problema.

## Decisão
- **Fonte do sistema** (`system-ui`): Segoe UI no Windows, Roboto no Android, SF no
  iPhone. São fontes feitas para tela, legíveis e já instaladas.
- **Ícones próprios** num único arquivo SVG (`app/static/icones.svg`), desenhados na
  mesma grade (24 px, traço de 2 px).
- **Nenhum arquivo externo** em página nenhuma. Um teste garante isso
  (`test_paginas_nao_dependem_de_internet`).

## Consequências
- ✅ A página aparece completa e na hora, com ou sem internet.
- ✅ Menos dados trafegando no celular.
- ⚠️ A letra muda um pouco de aparelho para aparelho. Aceitável: cada uma é a mais
  legível daquele sistema.
- ⚠️ Ícone novo precisa ser desenhado. O teste avisa se um ícone usado não existir.
