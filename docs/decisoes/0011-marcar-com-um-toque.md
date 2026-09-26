# 0011 — Marcar objetos com um toque (SAM 2.1)

**Status:** Aceita · 26/09/2026

## Contexto
A equipe fotografa as flores do jeito da foto real: **a planta inteira no campo**, com
as flores em cachos. Nenhum modelo geral separa essas flores sozinho com confiança
([decisão 0009](0009-modelo-de-segmentacao.md)). Nos grãos, a segmentação automática
acerta quase tudo, mas às vezes perde um grão ou junta dois. E até aqui não havia como
**acrescentar** um objeto que faltou nem **excluir** uma região errada.

## Decisão
Tela **"Marcar na foto"** (`/imagens/<id>/marcar`), uma foto por vez:
- **Tocar num lugar vazio:** o SAM 2.1 desenha o contorno do objeto a partir do ponto
  tocado.
  - Ele devolve até três contornos (ex.: pétala, flor, cacho). **Menor/Maior** trocam
    entre eles, e o sugerido é o que o modelo acha melhor.
  - **A tela lembra o tamanho preferido**, por tipo de amostra. Na foto real de flores, o
    sugerido costuma pegar um cachinho de 2 a 5 botões e o botão sozinho é o "Menor". Quem
    salva com "Menor" passa a receber o menor já no próximo toque.
  - **Escolher a classe salva a região já anotada.** São dois toques por objeto.
- **Tocar num contorno** seleciona a região: dá para trocar a classe ou **excluir**.
  - Excluir apaga as anotações da região.
  - Quem pode: a administração sempre; as outras pessoas, se ninguém mais anotou a região.
- **Zoom** com dois dedos, a roda do mouse ou os botões; arrastar move a foto. Com a
  foto bem ampliada, a tela troca a versão média pelo arquivo original, mais nítido.
- **Teclado:** setas movem a foto, +/− fazem o zoom e Enter marca ou seleciona o que
  está na mira central. É a alternativa acessível ao toque.
- **No celular**, com um contorno proposto, o painel vira uma **gaveta fixa** acima do
  menu (título, Menor/Maior, dúvida, classes numa fila). Assim não é preciso rolar a
  página a cada objeto.

**Como o SAM enxerga flores pequenas:** ele não recebe a foto inteira reduzida, e sim uma
**janela de 1024 px em resolução cheia** ao redor do toque (`app/segmentacao/toque.py`).
- A análise de cada janela é a parte lenta (7 a 20 s neste PC), e fica guardada: até 12
  janelas.
- A página pede para preparar a parte que está na tela quando a pessoa para de mover a
  foto, então o toque costuma já encontrar a janela pronta.
- Depois disso, cada toque leva **menos de meio segundo**.
- O marcador usa **uma cópia própria do modelo**: um toque não espera a fila de
  segmentação (que leva ~2 min por foto) terminar.

Regiões criadas assim são **manuais** (motor `toque`). "Segmentar de novo" não mexe nelas.

## Sugestões automáticas de flores: testadas e descartadas (26/09/2026)
Numa segunda foto real (planta inteira, de baixo, com céu e nuvens), foram testadas regras
de cor para a IA sugerir as flores sozinha:
- flor = creme (claro, levemente amarelado, tom neutro);
- só dentro da copa (cercada de folhas verde-escuras).

A regra separou bem as nuvens, o céu e as folhas. Mas:
- perdeu as **flores na sombra**, no meio da planta, que ficam acinzentadas;
- confundiu com a **palha seca** do chão e com o **brilho do céu nas folhas**;
- qualquer ajuste feito para esta luz quebraria na foto seguinte.

Sugestões que erram muito dão mais trabalho do que ajudam (cada região errada custa dois
toques para apagar). **Caminho escolhido:** marcar com o toque e, com algumas centenas de
flores anotadas, **treinar um modelo próprio** (YOLO de segmentação, com a exportação que já
existe), que aprende com a luz e o jeito de fotografar da equipe.

## Consequências
- ✅ Folhas, flores e frutos, que não têm segmentação automática, passam a poder ser
  anotados a partir de fotos inteiras.
- ✅ Grãos: dá para completar o que o motor perdeu e excluir o que ele errou.
- ✅ As flores marcadas à mão viram dados de treino (exportação YOLO): o caminho para um
  modelo próprio que ache as flores sozinho.
- ⚠️ Precisa da IA instalada. Sem ela, a tela só seleciona, reclassifica e exclui.
- ⚠️ A primeira análise de cada parte da foto demora (7 a 20 s neste PC). A tela avisa
  "Preparando esta parte da foto".
- 🔁 Ainda não dá para **ajustar** um contorno ponto a ponto; hoje, exclui-se e marca-se
  de novo.
