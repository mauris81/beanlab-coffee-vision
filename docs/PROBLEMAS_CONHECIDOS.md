# Problemas conhecidos

Encontrados na análise de 25/09/2026 e atualizados a cada fase.

## Em aberto

| Problema | Situação | Resolve em |
|----------|----------|------------|
| **Tela de anotação ainda não existe** | As regiões são criadas e contadas, mas ainda não dá para dizer a classe de cada uma pela tela. | Fase 5 |
| **Filtro de fundo do motor clássico só serve para grãos** (matiz ≤ 60) | Folhas, flores e frutos ainda não têm motor: as fotos precisam chegar já segmentadas (recortes ou COCO). | Fase 6 |
| **COCO no formato RLE não é importado** | Só contornos em polígono. Regiões em RLE são contadas e avisadas como ignoradas. | Quando alguém precisar |
| **Fotos HEIC (iPhone) não são aceitas** | O navegador do iPhone costuma converter para JPEG ao enviar; se não converter, a foto é recusada com mensagem. | Quando alguém precisar |
| **Sem excluir ou editar coletas pela tela** | Dá para excluir fotos; a coleta em si, ainda não. | Fase 4 |
| **`C:\CafeData` sem backup automático** | Fica fora do OneDrive de propósito ([decisão 0003](decisoes/0003-dados-fora-do-onedrive.md)). | Pendência do responsável |

## Requisitos de usabilidade para as telas novas

Problemas das telas antigas que as novas precisam evitar:

- Anotar um item exigia 3 cliques (classe, salvar, próximo). → Fase 5: 1 tecla ou 1 toque.
- Sem atalhos de teclado e sem anotação em lote. → Fase 5
- Lista não funcionava pelo teclado. → Fase 5 (foco visível e avisos acessíveis já existem: Fase 3)
- Observações sumiam ao trocar de item. → Fase 5 (o dado já é guardado por anotação)
- Imagens trafegavam em base64 dentro de JSON. → resolvido na Fase 2: fotos e miniaturas servidas direto, com cache de 1 ano

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
| **Cores invertidas nos recortes** (vermelho ↔ azul) | Recortes gerados a partir da foto original, sem conversões | 2 | `test_recorte_preserva_as_cores` |
| **Motor clássico media a área pela caixa** | Motor v2.0 devolve o contorno e a contagem real de pixels | 2 | `test_motor_classico_encontra_os_graos_da_bandeja` |
| **Segmentação dentro do envio** (a tela congelava) | Fila em segundo plano, com status ao vivo e retomada após reinício | 2 | `test_fila_retoma_o_que_ficou_pela_metade`, `tests/navegador/test_fluxo_coleta.py` |
| **Servidor de desenvolvimento em uso normal** | waitress no modo normal (vários celulares) | 2 | — |
| **Formulários sem proteção CSRF** | Código secreto por sessão em todo formulário | 2 | `test_formulario_sem_codigo_csrf_e_recusado` |
