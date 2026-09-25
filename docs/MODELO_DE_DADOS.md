# Modelo de dados

> **Rascunho.** Será implementado e revisado na Fase 1. Serve para discutir antes de
> programar.

## Diagrama

```
TipoAmostra ──1:N── Classe
    │
   1:N
    │
  Coleta ──1:N── Imagem ──1:N── Região ──1:N── Anotação ──N:1── Pessoa
                   │
                  1:N
                   │
             JobSegmentação
```

## Entidades

**TipoAmostra**: grão, folha, flor, fruto. Define quais classes existem e qual motor
de segmentação usar por padrão.

**Classe**: um rótulo possível para aquele tipo (ex.: "Ferrugem" para folhas).
Campos: `codigo` (fixo, ex. `ferrugem`), `nome` (exibido), `cor`, `tecla_atalho`,
`descricao`, `ordem`. O `codigo` nunca muda, então renomear uma classe não quebra
dados antigos.

**Coleta**: um conjunto de fotos tiradas juntas (o antigo "Projeto"). Campos: tipo de
amostra, nome, fazenda/talhão, variedade, data da coleta, quem coletou, observações.

**Imagem**: uma foto. Campos: `hash_sha256`, nome original, largura, altura, data e
GPS do EXIF (se houver), origem (`camera`, `arquivo`, `importacao`), status
(`aguardando`, `segmentando`, `pronta`, `erro`), `ja_segmentada` (sim/não).

**Região**: um objeto dentro da imagem (um grão, uma folha...). Campos: `poligono`,
`bbox`, `area_px` (área real), origem (`automatica`, `manual`, `importada`),
`motor` e `versao_motor`, `pontuacao` do modelo.

**Anotação**: "esta região é da classe X", dito por uma pessoa. Campos: região,
classe, pessoa, confiança, observação, data.

**Pessoa**: quem coleta e anota. Por enquanto só `nome`. Os campos de login serão
adicionados se e quando for decidido usar senha.

**JobSegmentação**: registro de cada execução de segmentação: motor, parâmetros,
status, tempo gasto, mensagem de erro.

## Escolhas de estrutura de dados (e por quê)

| Escolha | Alternativa descartada | Motivo |
|---------|------------------------|--------|
| Região guardada como **polígono** (lista de pontos `[x, y]` em pixels da imagem original, em JSON) | Só o recorte retangular (como era antes) | O polígono é editável na tela, pequeno (dezenas de pontos) e converte direto para COCO e YOLO. Sem ele não há como treinar segmentação. |
| `bbox` no formato COCO `[x, y, largura, altura]` | `[x1, y1, x2, y2]` | É o padrão da ferramenta de exportação mais usada. |
| Arquivos nomeados pelo **hash SHA-256** do conteúdo | Nome original do arquivo | Duas fotos com o mesmo nome não se sobrescrevem, e a mesma foto enviada duas vezes é detectada. O nome original fica guardado no banco. |
| Anotações **só são adicionadas, nunca editadas** (histórico) | Sobrescrever a classificação | Permite desfazer, auditar e comparar anotadores. A anotação vigente é a mais recente. |
| Classes definidas em **arquivos YAML** (`taxonomias/`) | Classes escritas no HTML (como era antes) | Um agrônomo ajusta a lista sem mexer em código. |
| Recortes e máscaras são **gerados a partir do polígono** | Guardar recortes como fonte da verdade | Evita dados duplicados que podem ficar inconsistentes (foi assim que surgiu o bug das cores invertidas). |

## Classes propostas por tipo de amostra

> ⚠️ **Proposta para validar com agrônomos.** São um ponto de partida e mudam
> editando os arquivos YAML.

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
