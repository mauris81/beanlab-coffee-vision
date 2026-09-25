# Design system

O conjunto de cores, textos, componentes e regras que dá à plataforma uma cara única
e fácil de usar. **Veja tudo funcionando em `/guia-visual`**
(http://127.0.0.1:5000/guia-visual com a plataforma aberta).

## Para quem desenhamos

| Quem | Onde | O que isso exige da interface |
|------|------|-------------------------------|
| **Quem coleta** | No campo, no celular, muitas vezes sob sol forte, às vezes com uma mão só e internet fraca ou nenhuma | Contraste alto, alvos grandes, menu ao alcance do polegar, nada que dependa de internet para aparecer |
| **Quem anota** | No laboratório ou em casa, no computador, por horas seguidas | Atalhos de teclado, pouca fadiga visual (tema escuro), foco visível, uma decisão por vez |
| **Quem pesquisa / coordena** | No computador | Números claros, progresso honesto, exportação |

## Princípios (e a heurística de Nielsen por trás de cada um)

| Princípio | Como aparece | Heurística |
|-----------|--------------|------------|
| **Feito para o campo** | Tema claro com contraste alto por padrão; alvos de toque de 48 px; menu na base da tela no celular | Flexibilidade e eficiência de uso |
| **Uma decisão por vez** | Um botão primário por área; o resto é secundário ou fantasma | Estética e design minimalista |
| **Sempre dizer o que está acontecendo** | Selos de status com texto (Na fila, Segmentando, Pronta, Erro); progresso com números escritos; avisos | Visibilidade do status do sistema |
| **Errar sem medo** | Anotações guardam histórico; desfazer (Fase 5) em vez de "tem certeza?"; diálogo de confirmação só para o que não tem volta, com o foco na opção segura | Controle e liberdade; prevenção de erros |
| **Falar a língua de quem usa** | Português simples, termos do café (talhão, coleta, ardido), nada de "submit" ou "segmentation job" | Correspondência com o mundo real |
| **Mensagens de erro que ajudam** | Dizem o que houve e como resolver: "O arquivo não é uma imagem. Envie JPG, PNG ou WEBP." | Ajudar a reconhecer, diagnosticar e recuperar erros |
| **Reconhecer em vez de lembrar** | Classes sempre visíveis com cor, nome e tecla; atalhos lembrados na tela | Reconhecimento em vez de memorização |
| **Consistência** | Um componente para cada coisa (macros em `componentes.html`); mesmos nomes e ícones em todas as telas | Consistência e padrões |
| **Cor nunca sozinha** | Todo status tem ícone e texto; toda classe tem nome; paleta segura para daltonismo | WCAG 1.4.1 |
| **Funciona sem internet** | Fonte e ícones guardados no projeto, nenhum arquivo de fora ([decisão 0004](decisoes/0004-visual-offline.md)) | — |
| **Letras que não se confundem** | Atkinson Hyperlegible Next: I, l e 1 e também 0 e O são diferentes; texto base de 17 px | WCAG 1.4.4 / 1.4.12 |

## Acessibilidade (WCAG 2.2, nível AA)

**Conferido automaticamente a cada mudança** (`pytest`):
- Contraste de **todos** os pares de cor usados, nos dois temas: texto ≥ 4,5:1; contornos,
  ícones e anel de foco ≥ 3:1 (`tests/test_design_system.py`).
- Nenhuma página baixa nada da internet.
- Campos ligados ao rótulo, à dica e ao erro (`aria-describedby`, `aria-invalid`).
- Botões só com ícone têm nome para o leitor de tela.

**Conferido no navegador** (`pytest -m navegador`, usa o Chrome ou Edge instalados):
- Auditoria **axe-core** (regras WCAG 2.0, 2.1 e 2.2, A e AA) em todas as páginas, nos
  dois temas, no celular e no computador.
- Primeiro Tab = "Pular para o conteúdo"; foco sempre visível.
- Alvos de toque ≥ 44 px no celular; sem rolagem horizontal.
- Diálogo abre com o foco na ação segura e fecha com Esc.
- Avisos de erro não somem sozinhos (WCAG 2.2.1: tempo suficiente).
- Tema lembrado entre visitas.

**Ainda não conferido** (precisa de gente): uso com leitor de tela real (NVDA, TalkBack),
com zoom de 200% e com pessoas da fazenda. Planejado para quando as telas de envio e
anotação existirem.

## Tokens

Arquivo: `app/static/css/tokens.css`. **Componentes nunca usam valores soltos**, só tokens.

| Grupo | Exemplos | Regra |
|-------|----------|-------|
| Cores | `--cor-texto`, `--cor-primaria`, `--cor-sucesso-suave` | Cada cor existe nos dois temas. Mudou uma cor? Rode os testes. |
| Texto | `--texto-xs` (14) … `--texto-4xl` (36) | Base 17 px. Nunca abaixo de 14 px, e 14 só para rótulos curtos. Fonte: Atkinson Hyperlegible Next (`--fonte`). |
| Espaço | `--espaco-1` (4) … `--espaco-8` (64) | Múltiplos de 4 px. |
| Formas | `--raio-md`, `--sombra-2` | Cantos moderados; sombras discretas. |
| Tamanhos | `--alvo-toque` (48 px) | Altura mínima de tudo que se toca. |

**Tema:** segue o aparelho até a pessoa escolher no botão do topo; a escolha fica
guardada no navegador. O tema claro é o padrão porque é o mais legível sob sol.

## Componentes

Macros em `app/templates/componentes.html`; estilos em `app/static/css/componentes.css`.
Use a macro em vez de escrever o HTML: a acessibilidade vem junto.

```jinja
{% import 'componentes.html' as c %}

{{ c.botao('Enviar fotos', icone_nome='enviar') }}
{{ c.botao('Ver detalhes', 'fantasma', href=url, icone_nome='avancar', icone_depois=True) }}
{{ c.botao_icone('fechar', 'Fechar') }}
{{ c.campo('talhao', 'Talhão', dica='Ex.: 3', erro=erros.talhao) }}
{{ c.selo_status(imagem.status) }}
{{ c.chip_classe(classe) }}
{{ c.progresso(anotadas, total, 'Talhão 3') }}
{{ c.estatistica('Pendentes', 305, 'faltam ~25 min') }}
{% call c.alerta('aviso', 'Foto muito escura') %}<p>…</p>{% endcall %}
{% call c.vazio('Nenhuma coleta ainda', 'Crie a primeira.') %}{{ c.botao('Criar coleta') }}{% endcall %}
{{ plural(3, 'região', 'regiões') }}   {# "3 regiões"; nunca "região(ões)" #}
{{ icone('camera') }}            {# decorativo, ao lado de texto #}
{{ icone('camera', 'Tirar foto') }}  {# sozinho: precisa de rótulo #}
```

Componentes só em CSS (sem macro), com exemplo no guia: **opções em cartão**
(`.opcoes-cartao` + `.opcao-cartao`, rádios grandes), **filtros** (`.filtros` + `.filtro`
com `aria-current`), **cartão de foto** (`.grade-fotos` + `.foto`) e **área de envio**
(`.envio`, com botão de câmera e botão de arquivos separados), **botão de classe**
(`.botao-classe` com `aria-pressed` e `aria-keyshortcuts`), **tabela** (`.tabela` dentro de
`.tabela-rolagem` focável) e **"Mostrar senha"** (macro `mostrar_senha`).

Datas na tela: `{{ data|hora_local }}` (o banco guarda em UTC).

Atalhos de teclado: todo botão com atalho declara `aria-keyshortcuts`; os atalhos nunca
disparam enquanto a pessoa digita num campo; Z e D são reservados na anotação.

Mensagens depois de uma ação: `flash('…', 'sucesso' | 'info' | 'aviso' | 'perigo')` na
rota; o `base.html` mostra como alerta no topo da página seguinte.

Pelo JavaScript: `avisar('Anotação salva', { tipo: 'sucesso' })` (`static/js/avisos.js`).
Comportamentos sem JS na página: `data-abrir-dialogo="id"`, `data-fechar-dialogo`,
`data-aviso="sucesso" data-aviso-texto="…"` (`static/js/app.js`).

## Como escrever os textos da interface

| Faça | Evite |
|------|-------|
| Botão diz o que acontece: **"Enviar fotos"**, **"Excluir coleta"** | "OK", "Confirmar", "Submeter" |
| Erro diz o que houve e o que fazer: "Informe o talhão ou marque 'Não sei'." | "Campo inválido", "Erro 422" |
| Frases curtas, voz ativa, "você" | Jargão técnico: "job", "segmentation", "payload" |
| Números escritos junto das barras: "4 de 309 · 1%" | Só a barra colorida |
| Plural certo: "1 foto", "3 fotos" (`plural()`) | "3 foto(s)", "região(ões)" |
| Não interromper: atualizações automáticas esperam a pessoa terminar o que está fazendo | Recarregar a página com um diálogo aberto |
| Termos do café e da fazenda: coleta, talhão, ardido, florada | Traduções literais do inglês |
| Estado vazio explica e oferece o próximo passo | Página em branco |

## Checklist para uma tela nova

- [ ] Usa só componentes e tokens (nenhuma cor ou tamanho solto)
- [ ] Um botão primário por área; o texto do botão diz o que acontece
- [ ] Funciona só com teclado: Tab em ordem lógica, Enter e Esc onde fizer sentido
- [ ] Todo campo tem rótulo visível; erros dizem como corrigir
- [ ] Status sempre com texto; cor nunca sozinha
- [ ] Estado vazio, carregando e erro pensados (não só o "caminho feliz")
- [ ] Testada no celular (390 px) e no computador, nos dois temas
- [ ] Página adicionada à lista de `tests/navegador/test_acessibilidade.py`
- [ ] Novo componente? Macro + CSS + exemplo no `/guia-visual`
