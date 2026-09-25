# Problemas conhecidos

Encontrados na análise de 25/09/2026 e atualizados a cada fase.

## Em aberto

| Problema | Situação | Resolve em |
|----------|----------|------------|
| **Telas de envio de fotos e de anotação fora do ar** | Intencional: as telas antigas usavam o modelo de dados antigo e foram retiradas. A página inicial mostra as classes disponíveis. | Fases 2 (envio) e 5 (anotação) |
| **Cores invertidas nos recortes** (vermelho ↔ azul) | O código com o bug (`routes.py`) foi removido. Na Fase 2 os recortes passam a ser gerados a partir do polígono, com um teste específico de cores. | Fase 2 |
| **Motor clássico calcula a área pela caixa** | O modelo novo já guarda a área real e aceita a área exata do motor, mas `app/segmentacao/classico.py` ainda devolve largura × altura. | Fase 2 |
| **Filtro de fundo só serve para grãos** (matiz ≤ 60) | Limitação do motor clássico. | Fases 2 e 6 |
| **Segmentação dentro da requisição** (tela congela) | Ainda não há envio de fotos; será feito em segundo plano, com `JobSegmentacao`. | Fase 2 |
| **Servidor de desenvolvimento do Flask** (aviso "development server" no terminal) | Funciona na rede local, mas não é feito para vários celulares ao mesmo tempo. Trocar por um servidor de produção (ex.: waitress). | Fase 2 |
| **`C:\CafeData` sem backup automático** | Fica fora do OneDrive de propósito ([decisão 0003](decisoes/0003-dados-fora-do-onedrive.md)). | Pendência do responsável |

## Requisitos de usabilidade para as telas novas

Problemas das telas antigas que as novas precisam evitar:

- Anotar um item exigia 3 cliques (classe, salvar, próximo). → Fase 5: 1 tecla ou 1 toque.
- Sem atalhos de teclado e sem anotação em lote. → Fase 5
- Lista não funcionava pelo teclado. → Fase 5 (foco visível e avisos acessíveis já existem: Fase 3)
- Observações sumiam ao trocar de item. → Fase 5 (o dado já é guardado por anotação)
- Imagens trafegavam em base64 dentro de JSON. → Fase 5: arquivos servidos direto, com cache

## Resolvidos

| Problema | Como foi resolvido | Fase | Garantido por teste |
|----------|--------------------|------|---------------------|
| Depurador do Werkzeug exposto na rede local | Debug desligado por padrão; ligado só com `CAFE_DEBUG=1` e restrito ao PC | 0 | — |
| Arquivos duplicados na raiz e dois ambientes virtuais | Removidos | 0 | — |
| **Progresso falso** (`'Pendente'` contava como anotado; 100% com 4 de 309) | "Pendente" passou a ser calculado: região sem anotação | 1 | `test_progresso_conta_so_o_que_foi_anotado` |
| **Exportar CSV dava erro 500** (data da anotação nunca preenchida) | Toda anotação tem `criada_em` obrigatório; a exportação será refeita na Fase 7 | 1 | — |
| **Uploads com o mesmo nome se sobrescreviam** | Fotos gravadas pelo hash do conteúdo | 1 | `test_fotos_diferentes_com_mesmo_nome_nao_se_sobrescrevem` |
| **"Área" era a da caixa** (no modelo de dados) | `area_px` guarda a área real do polígono | 1 | `test_area_de_um_triangulo_nao_e_a_da_caixa` |
| Sem polígono nem máscara (impossível treinar segmentação) | Região guarda o polígono como fonte da verdade | 1 | `test_geometria.py` |
| Classes fixas no HTML, só para grãos | Classes em `taxonomias/*.yaml`, 4 tipos de amostra | 1 | `test_taxonomias.py` |
| Tabelas `project` e `projeto` duplicadas; sem migrações | Banco novo em `C:\CafeData`, com migrações Alembic | 1 | `test_modelos_e_migracoes_estao_em_sincronia` |
| `reset_db.py` não apagava o banco certo | Removido; as migrações substituem o "reset" | 1 | — |
| Banco dentro do OneDrive (risco de corrupção) | Dados em `C:\CafeData` | 1 | — |
| Sem modo claro e sem layout para celular | Tema claro/escuro; menu na base da tela no celular; alvos de 48 px | 3 | `tests/navegador/test_interacao.py` |
| Foco invisível ao usar teclado; avisos com `alert()` | Foco sempre visível; avisos acessíveis (`aria-live`, erros não somem sozinhos) | 3 | `tests/navegador/` |
| Fonte do Google: página dependia de internet | Fonte do sistema e ícones próprios | 3 | `test_paginas_nao_dependem_de_internet` |
