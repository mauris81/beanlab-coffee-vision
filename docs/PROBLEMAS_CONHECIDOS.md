# Problemas conhecidos

Encontrados na análise de 25/09/2026. Cada um diz em que fase será resolvido.

## Afetam os dados

| # | Problema | Onde | Resolvido em |
|---|----------|------|--------------|
| 1 | **Cores invertidas nos recortes.** O recorte já está em RGB e o código converte "BGR→RGB" de novo antes de salvar: vermelho e azul trocam de lugar. | `app/routes.py` linha 65 | Fase 2 |
| 2 | **Progresso falso.** Todo grão começa como `'Pendente'`, e o código conta qualquer texto como "classificado", por isso o painel mostra 100%. | `app/models.py` linha 31, `app/routes.py` linha 94, `app/static/js/annotate.js` linha 104 | Fase 1 |
| 3 | **Exportar CSV dá erro 500.** `data_anotacao` nunca é preenchida. | `app/routes.py` linhas 150-165 e 185 | Fase 1 |
| 4 | **Observações somem.** A API não devolve o texto e a tela limpa o campo ao trocar de grão. | `app/routes.py` linha 120, `app/static/js/annotate.js` linha 204 | Fase 5 |
| 5 | **"Área em pixels" é a área da caixa**, não do grão. | `app/segmentation.py` linha 112 | Fase 2 |
| 6 | **Uploads com o mesmo nome se sobrescrevem.** | `app/routes.py` linhas 39-41 | Fase 2 |

## Estrutura e desempenho

- Não há máscara nem polígono salvos, só recortes: impossível treinar segmentação. → Fase 1/2
- Classes fixas no HTML e só para grãos. → Fase 1
- O banco tem as tabelas `project` e `projeto` (sobra de schema antigo) e não há migrações. → Fase 1 (banco novo)
- A segmentação roda dentro da requisição: a tela congela sem retorno. → Fase 2
- Imagens trafegam em base64 dentro de JSON (33% maiores, sem cache). → Fase 5
- O filtro de fundo (matiz ≤ 60) só funciona para o cenário de grãos. → Fase 2/6
- `reset_db.py` procura o banco na raiz, mas ele fica em `instance/`: o "reset" não
  apaga nada. → Fase 1 (substituído por migrações)

## Usabilidade e acessibilidade

- Anotar um grão exige 3 cliques (classe, salvar, próximo). → Fase 5
- Sem atalhos de teclado e sem anotação em lote. → Fase 5
- Lista de grãos não funciona pelo teclado; foco invisível; avisos com `alert()`. → Fase 3/5
- Sem modo claro e sem layout para celular. → Fase 3

## Resolvidos

| Problema | Fase | Commit |
|----------|------|--------|
| Depurador do Werkzeug exposto na rede local (`debug=True` em `0.0.0.0`) | 0 | `d1e56a3` |
| Arquivos duplicados na raiz e dois ambientes virtuais | 0 | `7717b35` |
