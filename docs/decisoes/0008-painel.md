# 0008 — O painel da página inicial

**Status:** Aceita · 25/09/2026

## Contexto
A página inicial mostrava só a lista de tipos de amostra e classes. Quem abre a
plataforma precisa saber, logo de cara, **quanto falta, por onde continuar e o que está
com problema**. A administração também quer acompanhar o andamento por tipo de amostra
(grãos, folhas, flores, frutos).

## Decisão

### O que o painel mostra (nesta ordem)
1. **Uma frase:** "Faltam 305 regiões para anotar em 4 coletas." É o que a pessoa lê
   primeiro, e o botão principal é **"Continuar anotando"**.
2. **Filtro por tipo de amostra** (Todos, Grãos, Folhas...), no endereço (`/?tipo=graos`):
   dá para guardar ou mandar o link.
3. **Números:** coletas, fotos, % anotada, regiões em dúvida.
4. **Todos:** um cartão por tipo, com progresso e as classes mais anotadas. **Um tipo:**
   a tabela de todas as classes, **mesmo zerada**, que também serve de consulta.
5. **Continuar anotando:** até 5 coletas com pendências, começando pela mexida por último.
6. **Precisa de atenção:** fotos com erro, regiões em dúvida (link direto para revisá-las
   no lote), coletas sem fotos, fotos sendo segmentadas.
7. **Atividade:** anotações por dia (14 dias) e "você: N hoje".
8. **Quem anotou (30 dias): só a administração vê.**

### Regras de contagem
As mesmas da tela de anotação (`servicos/anotacoes.py`):
- uma região está **anotada** se tem alguma anotação;
- vale a classe da anotação **mais recente**;
- **em dúvida** = a anotação mais recente foi marcada com "Tenho dúvida".

A **atividade** conta trabalho feito: trocar a classe de uma região conta de novo.

### Como é feito
- **Contas no banco, não em Python:** uma consulta resume todas as coletas; os números
  por tipo saem da soma desses resumos. Com 20 mil regiões, o painel leva cerca de 0,1 s,
  e um teste garante que o número de consultas não cresce com o número de coletas.
- **Índice em `anotacao.criada_em`**, para contar só os últimos dias.
- **Gráficos em HTML e CSS, sem biblioteca:**
  - funciona offline e não exige etapa de build ([0001](0001-manter-flask-sem-build.md),
    [0004](0004-visual-offline.md));
  - os números vão sempre escritos ao lado das barras;
  - o leitor de tela lê tabelas e textos, nunca as barras.
- **O guia visual saiu do menu** (é ferramenta de quem programa) e foi para o rodapé.

## Consequências
- ✅ Quem chega sabe o que fazer em um toque ("Continuar anotando").
- ✅ Problemas (erros de segmentação, dúvidas esquecidas) aparecem sem precisar procurar.
- ⚠️ "Quem anotou" mede quantidade, não qualidade. Por isso fica só para a
  administração: ranking à vista de todos pressiona a correr e errar mais.
- 🔁 Se precisarem de relatórios mais detalhados (por fazenda, por período), eles entram
  na Fase 7 (exportação), não no painel.
