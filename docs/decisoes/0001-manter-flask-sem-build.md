# 0001 — Manter Python + Flask, sem etapa de build no front-end

**Status:** Aceita · 25/09/2026

## Contexto
A plataforma precisa de telas bem mais ricas (dashboard, anotação com atalhos, edição
de contorno, uso no celular). Uma opção comum seria reescrever o front-end em React ou
Vue. Mas o Node.js não está instalado na máquina de desenvolvimento, a equipe trabalha
em Python e o processamento de imagem já está em Python.

## Decisão
- Back-end continua em **Flask**.
- Páginas renderizadas com **Jinja**.
- Interatividade com **JavaScript moderno em módulos ES nativos** (`<script type="module">`),
  carregados direto pelo navegador, **sem npm e sem build**.

## Consequências
- ✅ Uma única linguagem e um único comando (`python run.py`) para rodar tudo.
- ✅ Qualquer pessoa com Python consegue manter o projeto.
- ⚠️ Sem as facilidades de um framework reativo. Mitigação: componentes JS pequenos e
  isolados, um por arquivo.
- 🔁 Reavaliar se a tela de anotação crescer a ponto de o JS ficar difícil de manter,
  ou se for preciso um app instalável com modo offline completo.
