# 0010 — Exportar os dados para analisar e para treinar modelos

**Status:** Aceita · 26/09/2026

## Contexto
As anotações existem para virar pesquisa: análises (quantos grãos de cada defeito, por
talhão) e modelos treinados (segmentar e classificar sozinho). Quem analisa usa Excel,
R ou Python. Quem treina usa formatos padrão de visão computacional.

## Decisão
**Exportar** (só a administração) gera um `.zip` por **tipo de amostra**, com as coletas
escolhidas. Dentro dele:

| Arquivo | Para quê |
|---------|----------|
| `regioes.csv` | **Sempre.** Uma linha por região (coleta, foto, caixa, área, classe, dúvida, quem anotou). |
| `historico_anotacoes.csv` | **Sempre.** Todas as anotações, inclusive as substituídas (concordância, revisões). |
| `images/{train,val}/`, `coco.json` | COCO, polígonos. Volta para a plataforma pela importação COCO: um teste faz a ida e volta. |
| `data.yaml`, `labels/{train,val}/` | YOLO de segmentação, no arranjo padrão do Ultralytics. Um teste abre o conjunto com o próprio Ultralytics. |
| `recortes/<classe>/` | Um recorte por região anotada, uma pasta por classe (classificadores). |
| `manifesto.json`, `LEIAME.txt` | Filtros, contagens, classes com os índices do COCO/YOLO, motores e parâmetros usados; explicação em português. |

- **Planilha para o Excel em português:**
  - separador `;` e vírgula decimal;
  - UTF-8 com BOM, senão o Excel troca os acentos;
  - no Python: `pandas.read_csv(..., sep=";", decimal=",")`.
- **Treino sem lixo, por padrão** (as duas opções podem ser desligadas):
  - ficam de fora as regiões **em dúvida**, porque rótulo incerto ensina errado;
  - COCO/YOLO usam **só fotos sem regiões pendentes**: um grão sem rótulo numa foto de
    treino ensinaria ao modelo que ele é "fundo".
  - A planilha sempre traz tudo, com colunas para filtrar.
- **Separação treino/validação fixa:** cerca de 1 foto em 5 vai para validação, decidido
  pelo conteúdo da foto. Exportar de novo mantém a mesma separação e não mistura as duas
  partes entre versões do conjunto.
- **Fotos na orientação dos contornos:** foto gravada deitada pelo celular (marca de
  rotação no EXIF) sai já girada; as demais saem idênticas ao original.
- **Nomes neutros** (`000123.jpg` = foto 123): o nome original fica na planilha e no COCO.
- **Só a administração exporta:** o arquivo leva tudo o que a equipe produziu. Se
  pesquisadores precisarem exportar sozinhos, dá para abrir para membros depois.
- **O `.zip` é montado num temporário e apagado ao fim do envio.** Foi usado um iterador
  próprio, porque com o `send_file` do Flask a limpeza registrada nunca roda (um teste
  pegou isso). Para exportações grandes: `flask --app app exportar graos`.

## Consequências
- ✅ Um clique leva da anotação ao treino: `yolo segment train data=data.yaml model=yolo11n-seg.pt`.
- ✅ Reprodutível: o manifesto diz exatamente o que entrou e com quais motores e parâmetros.
- ⚠️ O `.zip` com fotos pode ficar grande (centenas de MB). A tela mostra uma estimativa antes.
- 🔁 Quando houver dados suficientes, treinar o YOLO próprio
  ([decisão 0002](0002-segmentacao-plugavel.md), item 5) usando esta exportação.
