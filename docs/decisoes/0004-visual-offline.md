# 0004 — Visual que funciona sem internet: fonte e ícones guardados no projeto

**Status:** Aceita · 25/09/2026

## Contexto
A versão antiga carregava a fonte Inter do Google Fonts. Na fazenda, a internet é fraca
ou inexistente, e o celular acessa o servidor pela rede local. Sem internet, a página
esperava a fonte até desistir e depois trocava de letra no meio da leitura. Bibliotecas
de ícones em CDN teriam o mesmo problema.

## Decisão
- **Fonte guardada no projeto**: *Atkinson Hyperlegible Next* (Braille Institute,
  licença SIL OFL), em `app/static/fontes/`: um arquivo de 34 KB com todos os pesos e
  todos os acentos do português. Escolhida pelo responsável numa comparação lado a lado
  com a fonte do sistema, Inter e Lexend (25/09/2026), por ser a mais fácil de ler:
  não confunde I, l e 1 nem 0 e O. Se não carregar, a página usa a fonte do sistema.
  *(Versão anterior desta decisão: só a fonte do sistema.)*
- **Ícones próprios** num único arquivo SVG (`app/static/icones.svg`), desenhados na
  mesma grade (24 px, traço de 2 px).
- **Nenhum arquivo externo** em página nenhuma. Um teste garante isso
  (`test_paginas_nao_dependem_de_internet`).

## Consequências
- ✅ A página aparece completa e na hora, com ou sem internet.
- ✅ Menos dados trafegando no celular.
- ✅ A mesma letra em todos os aparelhos.
- ⚠️ 34 KB a mais na primeira visita (depois fica no cache do navegador).
- ⚠️ Ícone novo precisa ser desenhado. O teste avisa se um ícone usado não existir.
