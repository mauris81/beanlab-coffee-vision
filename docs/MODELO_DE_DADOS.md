# Modelo de dados

Implementado na Fase 1. O código está em `app/dominio/` (um arquivo por assunto) e a
estrutura das tabelas em `migrations/versions/`.

## Diagrama

```
TipoAmostra ──1:N── Classe
    │
   1:N
    │
  Coleta ──1:N── Imagem ──1:N── Regiao ──1:N── Anotacao ──N:1── Pessoa
                   │
                  1:N
                   │
             JobSegmentacao
```

## Entidades

| Entidade | Tabela | O que é | Campos principais |
|----------|--------|---------|-------------------|
| **TipoAmostra** | `tipo_amostra` | Grãos, folhas, flores, frutos. Vem de `taxonomias/*.yaml`. | `codigo`, `nome`, `descricao`, `ordem`, `motor_padrao` (vazio = sem segmentação automática) |
| **Classe** | `classe` | Um rótulo possível para aquele tipo (ex.: "Ferrugem"). Vem do YAML. | `codigo` (fixo), `nome`, `cor`, `tecla_atalho`, `descricao`, `ordem`, `ativa` |
| **Pessoa** | `pessoa` | Conta de quem coleta e anota. Criada pela administração. | `nome`, `usuario` (único, ex. `maria.silva`), `senha_hash`, `papel` (membro/administrador), `ativa`, `precisa_trocar_senha`, `ultimo_acesso`, `tentativas_falhas`, `bloqueada_ate`, `versao_sessao` |
| **Coleta** | `coleta` | Um conjunto de fotos tiradas juntas (o antigo "Projeto"). | tipo de amostra, `nome`, `fazenda`, `talhao`, `variedade`, `data_coleta`, coletor |
| **Imagem** | `imagem` | Uma foto. O arquivo fica no disco, com o nome igual ao hash. | `hash_sha256`, `extensao`, `nome_original`, `largura`, `altura`, EXIF (`capturada_em`, `latitude`, `longitude`), `origem`, `status`, `ja_segmentada` |
| **Regiao** | `regiao` | Um objeto dentro da foto (um grão, uma folha...). | `poligono`, `bbox_*`, `area_px`, `origem`, `motor`, `versao_motor`, `pontuacao` |
| **Anotacao** | `anotacao` | "Esta região é da classe X", dito por alguém. | região, classe, pessoa, `origem`, `confianca`, `observacao`, `criada_em` (com índice: o painel conta os últimos dias) |
| **JobSegmentacao** | `job_segmentacao` | Cada execução de segmentação. | `motor`, `parametros`, `status`, tempos, `num_regioes`, `mensagem_erro` |

### Listas de opções (enums)

| Campo | Valores |
|-------|---------|
| `Imagem.origem` | `camera`, `arquivo`, `importacao` |
| `Imagem.status` | `aguardando`, `segmentando`, `pronta`, `erro` |
| `Regiao.origem` | `automatica`, `manual`, `importada` |
| `Anotacao.origem` | `manual`, `importada`, `modelo` |
| `JobSegmentacao.status` | `na_fila`, `processando`, `concluido`, `erro` |
| `Pessoa.papel` | `membro`, `administrador` |

## Duas regras centrais

**1. "Pendente" é calculado, nunca gravado.** Uma região está pendente quando não tem
nenhuma anotação. (O sistema antigo gravava o texto `'Pendente'` como classificação,
e o código contava isso como "anotado": o painel mostrava 100% com 4 de 309 grãos.)

**2. Anotações só são acrescentadas.** Mudar de ideia cria uma anotação nova; a
**vigente** é a mais recente (maior `id`). O histórico permite desfazer, auditar e
comparar anotadores. O cálculo de progresso está em
`app/servicos/anotacoes.py:progresso_da_coleta`.

## Escolhas de estrutura de dados (e por quê)

| Escolha | Alternativa descartada | Motivo |
|---------|------------------------|--------|
| Região guardada como **polígono** (lista de pontos `[x, y]` em pixels da imagem original, em JSON) | Só o recorte retangular (como era antes) | O polígono é editável na tela, pequeno (dezenas de pontos) e converte direto para COCO e YOLO. Sem ele não há como treinar segmentação. |
| `bbox` em **4 colunas** (`bbox_x`, `bbox_y`, `bbox_largura`, `bbox_altura`), formato COCO | Um campo JSON | Permite consultas no banco (ex.: "regiões menores que 20 px"). |
| `area_px` é a **área real** do objeto (fórmula do laço ou contagem da máscara) | Largura × altura da caixa (como era antes) | A área da caixa superestima objetos que não são retangulares. |
| Arquivos nomeados pelo **hash SHA-256** do conteúdo | Nome original do arquivo | Duas fotos com o mesmo nome não se sobrescrevem, e a mesma foto enviada duas vezes é detectada. O nome original fica no banco. |
| Anotações **só acrescentadas** (histórico) | Sobrescrever a classificação | Desfazer, auditoria, concordância entre anotadores. |
| Classes em **arquivos YAML** (`taxonomias/`) com `codigo` fixo | Classes escritas no HTML (como era antes) | Um agrônomo ajusta a lista sem mexer em código; renomear não quebra dados antigos. |
| Classe removida do YAML fica **inativa**, não é apagada | Apagar | Anotações antigas continuam válidas e exportáveis. |
| Enums guardados como **texto legível** (`'aguardando'`), sem restrição CHECK | Números, ou CHECK no banco | Legível numa consulta direta; adicionar uma opção não exige migração. O SQLAlchemy recusa valores fora da lista. |
| Recortes e máscaras **gerados a partir do polígono** | Guardar recortes como fonte da verdade | Evita cópias que ficam inconsistentes (foi assim que surgiu o bug das cores invertidas). |

## Proteções no próprio banco

Valem mesmo que o código tenha um erro. Cada uma tem um teste em `tests/test_integridade.py`.

- **Chaves estrangeiras ligadas** (`PRAGMA foreign_keys = ON`). O SQLite as deixa
  desligadas por padrão.
- **Apagar uma coleta apaga** suas imagens, regiões, anotações e jobs (`ON DELETE CASCADE`).
- **Classe com anotações não pode ser apagada** (`ON DELETE RESTRICT`), só desativada.
- **A mesma foto não entra duas vezes na mesma coleta** (único: coleta + hash).
- **Uma tecla por classe** e **um código por classe** dentro de cada tipo de amostra.
- **Faixas válidas:** `confianca` e `pontuacao` entre 0 e 1; `area_px`, `largura` e
  `altura` positivas.
- **Modo WAL:** o banco resiste a quedas de energia e permite ler enquanto se grava.

## Classes atuais por tipo de amostra

> ⚠️ **Proposta a validar com agrônomos.** Para mudar, edite os arquivos em
> `taxonomias/` (instruções em [taxonomias/LEIAME.md](../taxonomias/LEIAME.md)).

| Grãos | Folhas | Flores | Frutos |
|-------|--------|--------|--------|
| Sem defeito | Saudável | Botão floral | Chumbinho |
| Preto | Ferrugem | Flor aberta | Verde |
| Ardido | Cercosporiose | Flor murcha | Verde-cana |
| Verde | Bicho-mineiro | Outro | Cereja |
| Brocado | Mancha de Phoma | | Passa |
| Quebrado | Mancha-aureolada | | Seco |
| Concha | Deficiência nutricional | | Brocado |
| Chocho / mal granado | Outro | | Outro |
| Outro | | | |

## Detalhes que confundem

- **Coordenadas valem para a foto já girada.** Fotos de celular vêm "deitadas" com uma
  marca EXIF dizendo como girar. O arquivo original é guardado sem alteração, mas
  `largura`, `altura` e todos os polígonos se referem à foto como ela aparece na tela
  (`app/servicos/imagens.py:abrir_orientada`).
- **`Imagem.capturada_em` é a hora local da câmera**, não UTC: o EXIF não informa o fuso.
  As demais datas do banco são UTC.
- **Segmentar de novo** substitui só as regiões `automatica` daquela foto; as `manual`
  e `importada` ficam.

- **"Tenho dúvida" é `confianca = 0,5`**; sem dúvida, `confianca` fica vazia.
- **Desfazer é a única exceção a "anotações só são acrescentadas"**: apaga a anotação
  recém-feita, e só se ela for da própria pessoa e ainda for a vigente da região
  (`desfazer_anotacoes`). Corrige um engano; mudar de ideia depois é anotar de novo.

- **Senha nunca é guardada**, só o hash (scrypt). `senha_hash` vazio = a conta existe (tem
  anotações) mas ainda não pode entrar: veio do sistema antigo, que era só por nome.
- **`versao_sessao`** muda quando a senha é trocada ou a conta desativada; a sessão guarda
  a versão com que entrou, e se não bater, a pessoa sai (em todos os aparelhos).
