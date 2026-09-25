# 0003 — Guardar fotos e banco fora da pasta do OneDrive

**Status:** ⏳ Proposta, aguardando decisão do responsável · 25/09/2026

## Contexto
O projeto inteiro está dentro de `OneDrive\Documentos`. Isso já causou um problema
real: no backup de 25/09/2026, **301 das 310 imagens não puderam ser lidas** porque
estavam marcadas como "somente online" e o OneDrive não estava aberto.

Outros riscos:
- **SQLite + sincronização em nuvem** pode corromper o banco se o OneDrive copiar o
  arquivo no meio de uma gravação.
- Fotos de coleta ocupam muito espaço e consomem a cota do OneDrive.

## Opções
| Opção | Prós | Contras |
|-------|------|---------|
| **A. Pasta de dados configurável fora do OneDrive** (ex.: `C:\CafeData`), com backup próprio | Seguro para SQLite; sem arquivos "somente online" | É preciso ter uma rotina de backup |
| B. Manter no OneDrive e marcar "Sempre manter neste dispositivo" | Nada muda | Risco de corrupção do banco continua |

## Recomendação
**Opção A.** O código continua no OneDrive (e no git). Só `data/` (fotos e banco) sai,
por uma variável de configuração. A Fase 1 já deixa essa configuração pronta. Onde os
dados ficam é decisão do responsável.
