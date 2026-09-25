# Arquitetura

> Este documento descreve a **arquitetura-alvo** da reestruturação. Cada fase do
> [ROADMAP](ROADMAP.md) move o código um passo em direção a ela. Quando uma parte já
> existir de verdade, ela é marcada com ✅.

## Visão geral em uma frase

Um servidor Flask recebe fotos, divide cada foto em **regiões** (um grão, uma folha,
uma flor...), e oferece telas para que pessoas digam **o que é cada região**. Tudo fica
salvo num banco de dados e pode ser exportado para treinar modelos.

## Fluxo de uma foto

```
 Celular / PC                     Servidor                                 Disco
 ────────────                     ────────                                 ─────
 1. Tira ou escolhe a foto  ──►   Ingestão: valida, calcula hash,   ──►   data/imagens/
                                  lê EXIF (data, GPS)                      (nome = hash)
                                        │
                                        ▼
                                  Fila de segmentação (segundo plano)
                                        │  escolhe o motor pelo tipo de amostra
                                        ▼
                                  Segmentador ──► regiões (polígonos)  ──►  banco
                                        │
 2. Acompanha o progresso   ◄──   Status do job (na fila / processando /
                                  concluído / erro)
 3. Anota cada região       ──►   Serviço de anotação (grava histórico) ──►  banco
 4. Exporta                 ◄──   CSV · COCO · YOLO · recortes por classe
```

## Camadas do código

```
app/
├── config.py          Configurações por ambiente (desenvolvimento / produção)
├── extensions.py      Instâncias compartilhadas (banco, migrações)
├── dominio/           ENTIDADES: o que existe no sistema (Coleta, Imagem, Região...)
├── servicos/          CASOS DE USO: importar foto, segmentar, anotar, exportar
├── segmentacao/       MOTORES de segmentação, todos com a mesma interface
├── armazenamento/     Onde e como os arquivos são gravados no disco
├── web/               Rotas que devolvem PÁGINAS (HTML)
├── api/               Rotas que devolvem DADOS (JSON) para o JavaScript
├── templates/         HTML (Jinja)
└── static/            CSS, JavaScript e ícones
taxonomias/            Listas de classes por tipo de amostra (YAML, editável)
migrations/            Histórico de mudanças no banco (Alembic)
tests/                 Testes automáticos
```

**Regra das camadas:** as rotas (`web/`, `api/`) só recebem o pedido e chamam um
serviço. Toda regra de negócio fica em `servicos/`. Assim, a mesma regra serve à tela,
à API e aos testes, e trocar a interface não exige mexer na lógica.

## Convenções

- **Nomes do domínio em português** (`Coleta`, `Regiao`, `anotar_regiao`), porque é a
  língua de quem usa e pesquisa. Termos técnicos consagrados ficam em inglês (`job`,
  `hash`, `bbox`).
- **Nada de lógica em templates.** O template só exibe o que a rota entregou.
- **JavaScript em módulos ES nativos**, sem etapa de build
  (ver [decisão 0001](decisoes/0001-manter-flask-sem-build.md)).
- **Toda mudança no banco passa por migração**; nunca apagar o banco para "consertar".

## Segmentação

Todos os motores implementam a mesma interface: recebem uma imagem e devolvem uma
lista de regiões (polígono + pontuação). Detalhes e escolha dos modelos em
[decisão 0002](decisoes/0002-segmentacao-plugavel.md).

| Motor | Quando usar | Estado |
|-------|-------------|--------|
| Clássico (watershed) | Grãos em fundo uniforme | Existe, com bugs (Fase 2 corrige) |
| Importado | Fotos que já chegam segmentadas | Fase 2 |
| FastSAM | Automático, qualquer tipo de amostra | Fase 6 |
| SAM leve (MobileSAM / SAM 2.1-tiny) | Refinar com cliques | Fase 6 |
| YOLO11-seg treinado | Quando houver dados anotados suficientes | Futuro |

## Estado atual (antes da Fase 1)

Hoje o código ainda está no formato antigo: `app/routes.py`, `app/models.py` e
`app/segmentation.py` concentram tudo. Os problemas conhecidos estão em
[PROBLEMAS_CONHECIDOS.md](PROBLEMAS_CONHECIDOS.md).
