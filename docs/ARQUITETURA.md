# Arquitetura

> Partes marcadas com ✅ já existem. As demais são o alvo das próximas fases do
> [ROADMAP](ROADMAP.md).

## Visão geral em uma frase

Um servidor Flask recebe fotos, divide cada foto em **regiões** (um grão, uma folha,
uma flor...) e oferece telas para que pessoas digam **o que é cada região**. Tudo fica
salvo num banco de dados e pode ser exportado para treinar modelos.

## Fluxo de uma foto

```
 Celular / PC                     Servidor                                 Disco
 ────────────                     ────────                                 ─────
 1. Tira ou escolhe a foto  ──►   Ingestão: valida, calcula hash,   ──►   C:\CafeData\imagens\
                                  lê EXIF (data, GPS), miniatura           (nome = hash)  ✅
                                        │
                                        ▼
                                  Fila de segmentação (segundo plano) ✅
                                        │  escolhe o motor pelo tipo de amostra
                                        ▼
                                  Segmentador ──► regiões (polígonos)  ──►  banco ✅
                                        │
 2. Acompanha o progresso   ◄──   Status do job (na fila / processando /    ✅
                                  concluído / erro), consultado a cada 2 s
 3. Anota cada região       ──►   Tela de anotação (API JSON) ─► serviço  ✅ ──► banco
    (uma por vez ou em lote)       recortes e foto média em cache no disco  ✅
 4. Exporta                 ◄──   CSV · COCO · YOLO · recortes por classe
```

## Segurança ✅

- **CSRF:** todo formulário que muda dados leva um código secreto da sessão
  (`{{ campo_csrf() }}`); sem ele o pedido é recusado (`web/identidade.py`).
- **Cookie de sessão** assinado, `SameSite=Lax`, válido por 90 dias.
- **Redirecionamento seguro** depois de "Quem é você?": só para páginas da plataforma.
- **Arquivos:** o formato vem do conteúdo, não do nome; o nome original nunca vira
  caminho no disco (arquivos são gravados pelo hash).

## O que acontece ao iniciar ✅

`Iniciar BeanLab.bat` → `run.py`:
1. Cria a aplicação (`app/__init__.py`) com a configuração de `app/config.py`.
2. `preparar_banco()`: aplica as migrações pendentes (`migrations/`) e sincroniza as
   classes com os arquivos `taxonomias/*.yaml`.
   - Se um YAML tiver erro, a plataforma **não abre** e mostra a mensagem.
3. Mostra os endereços (PC e celulares), **retoma as segmentações que ficaram pela
   metade** e começa a atender com o servidor **waitress** (vários celulares ao mesmo
   tempo). No modo desenvolvimento usa o servidor do Flask, que recarrega ao salvar.

## Camadas do código

```
app/
├── __init__.py        ✅ create_app(): monta a aplicação
├── config.py          ✅ configurações (pasta de dados, limites); lidas do ambiente
├── extensions.py      ✅ banco (SQLAlchemy) e migrações; liga proteções do SQLite
├── cli.py             ✅ comandos de terminal (flask --app app preparar-banco)
├── fila.py            ✅ fila de segmentação em segundo plano (decisão 0005)
├── dominio/           ✅ ENTIDADES: o que existe (Coleta, Imagem, Regiao, Anotacao...)
├── servicos/          ✅ CASOS DE USO: anotações, ingestão (fotos, recortes, COCO), imagens
│                         (EXIF, orientação, miniaturas), recortes (cache por geometria),
│                         segmentação (jobs), taxonomias, pessoas
├── armazenamento/     ✅ onde e como as fotos são gravadas no disco
├── segmentacao/       ✅ motores com interface comum (base.py); hoje: clássico (watershed)
├── web/               ✅ rotas que devolvem PÁGINAS, por assunto: paginas.py, identidade.py
│                         ("Quem é você?" + CSRF), coletas.py, anotacao.py (uma por vez, lote);
│                         apresentacao.py = ícones, menu, status, plural
├── api/               ✅ rotas que devolvem DADOS em JSON: saude.py, anotacao.py
│                         (regiões da coleta, anotar, desfazer)
├── templates/         ✅ HTML (Jinja); componentes.html = macros do design system
└── static/            ✅ css/ (tokens, base, componentes, paginas/), js/ (módulos ES), icones.svg
taxonomias/            ✅ listas de classes por tipo de amostra (YAML, editável)
migrations/            ✅ histórico de mudanças no banco (Alembic)
tests/                 ✅ testes automáticos (pytest)
```

**Dados ficam fora do projeto**, em `C:\CafeData` (ou na pasta da variável
`CAFE_DATA_DIR`): banco `beanlab.db`, fotos em `imagens/` e a chave secreta.
Ver [decisão 0003](decisoes/0003-dados-fora-do-onedrive.md).

### Regras das camadas

- **Rotas só recebem o pedido e chamam um serviço.** Toda regra de negócio fica em
  `servicos/`. Assim a mesma regra serve à tela, à API e aos testes.
- **Serviços preparam, quem chama confirma.** Os serviços fazem `add`/`flush`; a rota,
  o comando ou o teste faz `db.session.commit()`. Uma operação que usa vários
  serviços é gravada inteira ou não é gravada.
- **O domínio não conhece Flask nem disco.** `dominio/` só descreve dados e cálculos
  (ex.: área do polígono), então pode ser testado sem servidor.

## Convenções

- **Nomes do domínio em português** (`Coleta`, `Regiao`, `anotar_regiao`), porque é a
  língua de quem usa e pesquisa. Termos técnicos consagrados ficam em inglês (`job`,
  `hash`, `bbox`).
- **Datas sempre em UTC** no banco (`agora_utc()`); a conversão para o horário local
  é feita só na tela.
- **Nada de lógica em templates.** O template só exibe o que a rota entregou.
- **JavaScript em módulos ES nativos**, sem etapa de build
  (ver [decisão 0001](decisoes/0001-manter-flask-sem-build.md)).
- **Visual só com tokens e componentes do design system**; nada carregado da internet
  (ver [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) e [decisão 0004](decisoes/0004-visual-offline.md)).
- **Toda mudança no banco passa por migração**; nunca apagar o banco para "consertar".
  Um teste falha se um modelo mudar sem migração. Como fazer:
  [DESENVOLVIMENTO.md](DESENVOLVIMENTO.md).

## Segmentação

Todos os motores implementam a mesma interface (`app/segmentacao/base.py`): recebem a
foto como matriz RGB, já girada, e devolvem regiões (polígono + área + pontuação). O
motor de cada tipo de amostra é o campo `motor:` do YAML (`taxonomias/`). Detalhes e escolha dos modelos em
[decisão 0002](decisoes/0002-segmentacao-plugavel.md).

| Motor | Quando usar | Estado |
|-------|-------------|--------|
| Clássico (watershed) | Grãos sobre **fundo azul**, encostados ou separados | ✅ `app/segmentacao/classico.py` v2.1 (contornos, área real, cores corretas, todos os grupos de grãos) |
| Importado | Recortes prontos (PNG transparente) ou COCO | ✅ `app/servicos/ingestao.py` |
| FastSAM | Automático, qualquer tipo de amostra | Fase 6 |
| SAM leve (MobileSAM / SAM 2.1-tiny) | Refinar com cliques | Fase 6 |
| YOLO11-seg treinado | Quando houver dados anotados suficientes | Futuro |
