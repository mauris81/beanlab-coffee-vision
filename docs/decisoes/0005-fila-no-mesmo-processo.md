# 0005 — Fila de segmentação dentro da própria plataforma

**Status:** Aceita · 25/09/2026

## Contexto
A segmentação de uma foto leva de menos de 1 s a vários segundos. Fazer isso durante o
envio travaria a tela (era assim no sistema antigo). É preciso processar em segundo
plano e mostrar o andamento.

A solução mais comum na web é um servidor de filas separado (Celery + Redis, RQ...).
Aqui isso significaria instalar e manter mais dois programas num PC Windows, para uma
plataforma usada por poucas pessoas ao mesmo tempo.

## Decisão
- **Uma linha de execução (thread) dentro da própria plataforma** processa os jobs, um
  por vez (`app/fila.py`). O i5 não ganharia nada fazendo vários ao mesmo tempo.
- **O banco é a fila:** cada job é uma linha em `job_segmentacao` com status
  (`na_fila`, `processando`, `concluido`, `erro`). Se a plataforma for fechada no meio,
  ao abrir de novo os jobs pendentes são **retomados** automaticamente.
- A página acompanha pelo endereço `/coletas/<id>/situacao.json`, consultado a cada 2 s
  enquanto houver fotos pendentes.
- Nos testes, os jobs rodam na hora (`SEGMENTACAO_SINCRONA`), para serem previsíveis.

## Consequências
- ✅ Nada novo para instalar: continua o duplo clique.
- ✅ Nada se perde se a plataforma fechar no meio.
- ⚠️ Só funciona com **um processo** servindo a plataforma (é o caso do waitress com
  várias threads). Se um dia houver hospedagem com vários processos ou servidores,
  trocar por uma fila de verdade (a interface `fila().enviar(ids)` fica igual).
- ⚠️ Motores de IA pesados (Fase 6) podem precisar de um processo separado para não
  disputar memória com o site. Reavaliar lá.
