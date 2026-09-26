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
 0. Sem sinal? A foto fica
    guardada no celular e sobe
    sozinha depois ✅ ─ ─ ─ ─ ─►
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
 4. Acompanha no painel     ◄──   Quanto falta, classes, pendências, atividade ✅
 5. Exporta                 ◄──   CSV · COCO · YOLO · recortes por classe
```

## Na internet e no celular ✅

A plataforma roda neste PC e o **Tailscale Funnel** dá a ela um endereço HTTPS na
internet ([decisão 0007](decisoes/0007-publicacao-e-aplicativo.md); guia para quem cuida
do PC: [PUBLICACAO.md](PUBLICACAO.md)).

```
 celular (4G) ──HTTPS──► Tailscale (neste PC) ──http──► 127.0.0.1:5000 (waitress)
 celular (Wi-Fi) ─────────────────────http───────────► 192.168.x.x:5000
```

- **Aplicativo (PWA):** `static/manifest.json` + ícones em `static/aplicativo/`.
- **Service worker** (`templates/sw.js`, servido por `web/aplicativo.py` em `/sw.js`):
  guarda os arquivos de `static/` e a página genérica **"Fotos no celular"**; sem sinal
  (ou após 15 s), mostra essa página. A versão é um hash dos arquivos: mudou algo, o
  celular atualiza sozinho. **Páginas com dados nunca ficam guardadas.**
- **Fila de fotos** (`static/js/fila-fotos.js`, IndexedDB): usada pela página da coleta
  (envio que falha ou "Guardar no celular"), por "Fotos no celular" e pelo service
  worker ("sincronização em segundo plano"). Envia uma foto por pedido, com o
  cabeçalho `X-Envio-Via: fila`; a rota de envio responde em JSON. Cada foto só sobe
  com a mesma pessoa logada. `static/js/aplicativo.js` liga tudo nas páginas.
- **`/api/coletas`**: lista curta que o celular guarda para fotografar sem sinal.

## Segurança ✅

- **Política de conteúdo (CSP) e outros cabeçalhos** em toda resposta
  (`app/seguranca.py`): só roda código da própria plataforma. **Nenhum `<script>` ou
  `onclick` dentro do HTML**; um teste confere todas as páginas.
- **Proxy:** `X-Forwarded-For`/`-Proto` só valem vindos de 127.0.0.1 (o Tailscale);
  do Wi-Fi são apagados. Com HTTPS: cookie `Secure` e HSTS.
- **Limite de tentativas por IP** (login e primeiro acesso), além do bloqueio por conta.
- **Modo desenvolvimento não atende pela internet** (403).
- **Login obrigatório** em tudo, menos entrar/primeiro acesso/estáticos/`/api/saude`
  e as peças do aplicativo (`/sw.js`, "Fotos no celular"): `proteger_paginas` em
  `web/identidade.py`. Pedidos do JavaScript recebem erros em JSON, nunca páginas. Senha provisória só deixa trocar a senha.
  Detalhes e porquês: [decisão 0006](decisoes/0006-login-e-contas.md).
- **Contas:** regras em `servicos/contas.py` (hash scrypt, bloqueio após 5 erros, nunca
  sem administração, código de primeiro acesso). Telas: `web/identidade.py` (entrar,
  primeiro acesso, minha conta) e `web/admin.py` (Pessoas).
- **CSRF:** todo formulário que muda dados leva um código secreto da sessão
  (`{{ campo_csrf() }}`); sem ele o pedido é recusado (`web/identidade.py`).
- **Cookie de sessão** assinado, `SameSite=Lax`, válido por 90 dias; renovado a cada login;
  deixa de valer se a senha mudar ou a conta for desativada (`Pessoa.versao_sessao`).
- **Redirecionamento seguro** depois do login: só para páginas da plataforma.
- **Arquivos:** o formato vem do conteúdo, não do nome; o nome original nunca vira
  caminho no disco (arquivos são gravados pelo hash).

## O que acontece ao iniciar ✅

`Iniciar BeanLab.bat` → `run.py`:
1. Cria a aplicação (`app/__init__.py`) com a configuração de `app/config.py`.
2. `preparar_banco()`: aplica as migrações pendentes (`migrations/`) e sincroniza as
   classes com os arquivos `taxonomias/*.yaml`.
   - Se um YAML tiver erro, a plataforma **não abre** e mostra a mensagem.
3. Mostra os endereços (PC, celulares no Wi-Fi e, se o Funnel estiver ligado, o da
   internet), **retoma as segmentações que ficaram pela metade** e começa a atender
   com o servidor **waitress** (vários celulares ao mesmo tempo), sem deixar o PC
   suspender. No modo desenvolvimento usa o servidor do Flask, que recarrega ao salvar.

## Camadas do código

```
app/
├── __init__.py        ✅ create_app(): monta a aplicação
├── config.py          ✅ configurações (pasta de dados, limites); lidas do ambiente
├── extensions.py      ✅ banco (SQLAlchemy) e migrações; liga proteções do SQLite
├── cli.py             ✅ comandos de terminal (flask --app app preparar-banco)
├── fila.py            ✅ fila de segmentação em segundo plano (decisão 0005)
├── seguranca.py       ✅ CSP e cabeçalhos, proxy só de 127.0.0.1, cookie seguro, limite por IP
├── publicacao.py      ✅ lê o endereço do Tailscale Funnel; não deixa o PC suspender
├── dominio/           ✅ ENTIDADES: o que existe (Coleta, Imagem, Regiao, Anotacao...)
├── servicos/          ✅ CASOS DE USO: anotações, ingestão (fotos, recortes, COCO), imagens
│                         (EXIF, orientação, miniaturas), recortes (cache por geometria),
│                         segmentação (jobs), taxonomias, contas (login e exclusão), coletas
│                         (quem pode excluir e o quê), painel (números da
│                         página inicial, contados no banco)
├── armazenamento/     ✅ onde e como as fotos são gravadas no disco
├── segmentacao/       ✅ motores com interface comum (base.py); hoje: clássico (watershed)
├── web/               ✅ rotas que devolvem PÁGINAS, por assunto: paginas.py, identidade.py
│                         (login + CSRF), admin.py (Pessoas), coletas.py, anotacao.py,
│                         aplicativo.py (service worker, "Fotos no celular");
│                         apresentacao.py = ícones, menu, status, plural
├── api/               ✅ rotas que devolvem DADOS em JSON: saude.py, anotacao.py
│                         (regiões da coleta, anotar, desfazer), coletas.py (lista p/ celular)
├── templates/         ✅ HTML (Jinja); componentes.html = macros do design system; sw.js
└── static/            ✅ css/ (tokens, base, componentes, paginas/), js/ (módulos ES), icones.svg,
                          manifest.json e aplicativo/ (ícones do aplicativo)
ferramentas/           ✅ scripts de apoio (gerar os ícones do aplicativo a partir do logotipo)
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
  (ver [decisão 0001](decisoes/0001-manter-flask-sem-build.md)), **sempre em arquivo**
  (`static/js/`), nunca dentro do HTML: a política de segurança bloqueia.
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
