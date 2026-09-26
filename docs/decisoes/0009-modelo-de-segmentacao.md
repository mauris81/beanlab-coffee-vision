# 0009 — Segmentação com IA: FastSAM encontra, SAM 2.1 contorna

**Status:** Aceita · 26/09/2026 · Completa a [decisão 0002](0002-segmentacao-plugavel.md)

## Contexto
O motor clássico (watershed) foi feito para grãos sobre **fundo azul**. A única foto
real da equipe mostra o caso comum: grãos amontoados e encostados, num pote plástico
verde-claro sobre fundo branco. Nela o motor clássico:
- perde cerca de um terço dos grãos, justamente os mais claros e os com defeito;
- desenha contornos serrilhados;
- às vezes quebra um grão em pedaços.

Folhas, flores e frutos não têm segmentação automática.

O PC que roda a plataforma: processador **i5-3570, sem as instruções AVX2** (o PyTorch
roda no modo mais lento), 16 GB de memória, placa **GTX 1050 de 2 GB**, que as versões
atuais do PyTorch com CUDA não aceitam. Ou seja, **só processador**.

## O teste
Todos os modelos rodaram na foto real (1.201 × 1.600), no próprio PC. Sem contornos
desenhados à mão para servir de gabarito, o teste usou três medidas:
- **contagem à mão** num recorte ampliado do centro da foto: ~33 grãos, ±3;
- **total de grãos**, comparado com uma estimativa de ~370 pela densidade do recorte;
- **inspeção visual** dos contornos.

| Motor | No recorte (~33) | Na foto (~370) | Tempo por foto | Contorno |
|-------|-----------------:|---------------:|---------------:|----------|
| Clássico 2.1 (antes) | 20 | 286 | 1 s | serrilhado; perde grãos claros |
| FastSAM-s | 32 | 309 | 8 s | "quadrado" (cantos retos) |
| FastSAM-x | 31 | 323 | 21 s | bom |
| SAM 2.1-tiny sozinho | 24 | 228 | 198 s | ótimo, mas perde grãos |
| **FastSAM-s + SAM 2.1-tiny** | **33–34** | **348–356** | **93–127 s** | **ótimo** |

As imagens do teste ficam em `C:\CafeData\avaliacao-fase6`, fora do git, porque a foto é
da equipe. Para repetir o teste com outras fotos: `ferramentas/avaliar_segmentacao.py`.

## Decisão
- **Motor `ia` = FastSAM-s encontra, SAM 2.1-tiny contorna** (`app/segmentacao/ia.py`):
  1. o FastSAM dá uma caixa para cada objeto;
  2. o SAM desenha o contorno do que está dentro de cada caixa;
  3. um filtro deixa **uma região por objeto**. Ele descarta:
     - o que não tem forma de objeto (manchas do fundo);
     - o que foge do tamanho típico **desta foto**: entre ¼ e 4 vezes a área mediana. Assim
       funciona de longe e de perto; o pote nunca entra;
     - repetições do mesmo objeto.
- **É opcional**, cerca de 1 GB, instalado por `Instalar IA.bat`:
  - bibliotecas: `requirements-ia.txt`;
  - pesos: ~180 MB em `C:\CafeData\modelos`, **com conferência de hash**.
  - Sem a IA, a plataforma funciona como antes.
- **Grãos: `motor: [ia, classico]`**: a IA, se instalada; senão, o clássico. A escolha é
  feita a cada abertura da plataforma.
- **Folhas, flores e frutos continuam sem motor** até haver fotos reais de cada tipo para
  testar e ajustar o filtro. O FastSAM é um modelo geral e deve funcionar, mas sem
  validação ele poderia encher a anotação de regiões erradas.
- **Cada segmentação guarda os parâmetros usados** (`JobSegmentacao.parametros`): a
  pesquisa sabe exatamente com que modelo e configuração cada região foi feita.
- **Fotos grandes** (12 MP, direto do celular) são trabalhadas numa cópia com lado de
  1600 px; os contornos voltam à resolução original. Sem isso, cada lote do SAM gastaria
  vários GB de memória. Fotos de até 1600 px, como a de grãos, não mudam.
- **3 dos 4 núcleos**: um fica livre para a plataforma continuar respondendo durante a
  segmentação. Com isso, cerca de 2 minutos por foto em vez de 1,5.
- **Nada vai para a internet durante o uso**: as estatísticas de uso do Ultralytics
  ficam desligadas (`YOLO_OFFLINE`, `sync=False`).
- **Fotos segmentadas por um motor antigo** mostram **"Segmentar de novo"**. O diálogo
  avisa quantas regiões e anotações serão substituídas; regiões feitas à mão ou
  importadas não mudam.

## Primeiro teste com flores (26/09/2026)
A equipe mandou uma foto real de flores: a **planta inteira no campo**, em plena florada
(12 MP). A IA, do jeito que foi ajustada para grãos, **não serve para esse tipo de foto**:
- marcou folhas, pedaços do céu e torrões de terra;
- nas flores, marcou **cachos inteiros**. Cada flor tem só ~60 a 100 px na foto original.

Olhando um trecho em resolução cheia, com um filtro de cor branca, separou só parte das
flores (32 num trecho com bem mais de 100) e às vezes marcou pétalas soltas. As imagens
estão em `C:\CafeData\avaliacao-fase6\flores`.

**Conclusão:** flores continuam **sem motor**. O próximo passo depende de como a equipe
vai fotografar: fotos de perto de um ramo tendem a funcionar como os grãos; fotos da planta
inteira pedem outro tipo de anotação ou um modelo treinado com dados da própria equipe.

## Licença
O FastSAM usa o Ultralytics, que é **AGPL-3.0**. O responsável escolheu esse caminho,
então **o projeto passa a ser AGPL-3.0** (arquivo `LICENSE`):
- o código continua aberto;
- quem oferecer a plataforma modificada pela internet precisa disponibilizar o código
  dessa versão.

O SAM 2.1 é Apache-2.0. A alternativa só com licença livre (o SAM 2.1 sozinho) achou
bem menos grãos e levou mais de 3 minutos por foto.

## Consequências
- ✅ Grãos em **qualquer fundo**, encostados, com contornos precisos, sem trocar o pano azul.
- ✅ Com as mesmas peças, dá para passar a segmentar folhas, flores e frutos quando houver fotos.
- ⚠️ **Lento neste PC** (cerca de 2 minutos por foto, em segundo plano). Num PC com AVX2, ou
  com uma placa de vídeo aceita pelo PyTorch, cai para uma fração disso.
- ⚠️ `pip check` avisa que o Ultralytics "quer" o `opencv-python`. É de propósito: a
  plataforma usa o `opencv-python-headless`, e os dois juntos se sobrescrevem.
- ⚠️ **Validação fraca:** uma foto só e uma contagem a olho num recorte. Serve para escolher
  o caminho; para publicar resultados, repetir com várias fotos e contornos feitos à mão.
- 🔁 Quando houver milhares de grãos anotados, treinar um modelo próprio (YOLO-seg), que
  aprende com as fotos da fazenda e deve ser mais preciso e bem mais rápido
  ([0002](0002-segmentacao-plugavel.md), item 5).
