# 0002 — Segmentação com motores intercambiáveis

**Status:** Aceita (a escolha final de modelos depende do teste da Fase 6) · 25/09/2026

## Contexto
Grãos, folhas, flores e frutos são problemas visuais muito diferentes. O algoritmo
atual (watershed) funciona para grãos separados sobre fundo uniforme, mas não para
folhas ou flores. Algumas fotos também chegam **já segmentadas**.

Hardware disponível: GPU **GTX 1050 (2 GB)**, CPU **i5-3570**, **16 GB** de RAM.
Isso descarta modelos grandes como o SAM ViT-H (~2,5 GB de pesos, precisa de ~8 GB de
VRAM).

## Decisão
Criar uma interface única `Segmentador` (entra imagem, saem regiões com polígono e
pontuação). Cada motor é uma implementação:

1. **Clássico (watershed)**, corrigido: padrão para grãos. Rápido, sem dependências novas.
2. **Importado**: lê recortes individuais ou máscaras prontas (COCO / YOLO).
3. **FastSAM-s** (~23 MB): segmentação automática de "tudo" em qualquer tipo de amostra.
   Roda em CPU (poucos segundos por foto) ou na GTX 1050.
4. **MobileSAM / SAM 2.1-tiny**: refinamento interativo, quando a pessoa clica no
   objeto e o modelo desenha o contorno.
5. **Futuro, YOLO11-seg treinado** com as anotações da própria plataforma. Tende a ser
   o mais preciso, porque aprende com as fotos reais da fazenda.

Toda região registra **qual motor e qual versão** a gerou.

## Como a escolha será validada (Fase 6)
Antes de adotar um modelo, comparar suas regiões com contornos feitos à mão em uma
amostra de fotos reais de cada tipo, medindo **IoU** (sobreposição) e tempo por foto.

## Consequências
- ✅ Dá para trocar ou adicionar modelos sem mexer nas telas nem no banco.
- ✅ Dá para comparar motores na mesma foto.
- ⚠️ **Licenças:** FastSAM e YOLO (Ultralytics) usam **AGPL-3.0**, que tudo bem para
  pesquisa acadêmica. Para uso comercial ou distribuição fechada, preferir
  MobileSAM / SAM 2 (Apache-2.0) ou comprar a licença da Ultralytics.
- ⚠️ Modelos de IA adicionam dependências pesadas (PyTorch). Serão opcionais: o sistema
  funciona sem eles, só com o motor clássico e o importado.
