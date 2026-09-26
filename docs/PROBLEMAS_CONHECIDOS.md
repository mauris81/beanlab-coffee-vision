# Problemas conhecidos

Encontrados na análise de 25/09/2026 e atualizados a cada fase.

## Em aberto

| Problema | Situação | Resolve em |
|----------|----------|------------|
| **Motor de grãos não validado com fotos reais** | Os testes usam fotos sintéticas no cenário esperado (grãos sobre fundo azul): 48 de 48 grãos encontrados, encostados ou separados. Falta confirmar com fotos de verdade. | Pendência do responsável (enviar fotos) |
| **Não dá para corrigir contornos** (ajustar, desenhar, excluir uma região errada) | Estava no plano da Fase 5 e ficou de fora. Por enquanto, região que não é um objeto: classe "Outro" + observação. | A definir |
| **Filtro de fundo do motor clássico só serve para grãos** (matiz ≤ 60) | Folhas, flores e frutos ainda não têm motor: as fotos precisam chegar já segmentadas (recortes ou COCO). | Fase 6 |
| **COCO no formato RLE não é importado** | Só contornos em polígono. Regiões em RLE são contadas e avisadas como ignoradas. | Quando alguém precisar |
| **Fotos HEIC (iPhone) não são aceitas** | O navegador do iPhone costuma converter para JPEG ao enviar; se não converter, a foto é recusada com mensagem. | Quando alguém precisar |
| **Sem excluir ou editar coletas pela tela** | Dá para excluir fotos; a coleta em si, ainda não. | Fase 4 |
| **`C:\CafeData` sem backup automático** | Fica fora do OneDrive de propósito ([decisão 0003](decisoes/0003-dados-fora-do-onedrive.md)). | Pendência do responsável |

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
| **Motor clássico só via o maior grupo de grãos encostados** (com grãos separados, achava 1 de 48) | Versão 2.1 considera todos os grupos com cor de grão | 5 | `test_motor_classico_encontra_cada_grao_uma_vez`, `test_modo_antigo_so_via_o_maior_grupo_de_graos` |
| **Recortes gerados ao mesmo tempo se atrapalhavam** ("arquivo em uso" no Windows) | Trava por foto e arquivos temporários de nome único | 5 | `test_muitos_pedidos_simultaneos_de_recorte_da_mesma_foto` |
| Anotar exigia 3 cliques por item (classe, salvar, próximo) | 1 tecla ou 1 toque; avanço automático para a próxima pendente | 5 | `tests/navegador/test_anotacao_navegador.py` |
| Sem atalhos de teclado e sem anotação em lote | Atalhos 1–9, ←/→, D, Z, ?; tela em lote com "marcar todas", Shift+clique e desfazer | 5 | `tests/navegador/test_anotacao_navegador.py` |
| Observações sumiam ao trocar de item | Observação e dúvida guardadas por anotação e mostradas ao voltar à região | 5 | `test_situacao_das_regioes_mostra_a_anotacao_vigente` |
| **Sem login**: qualquer pessoa na rede podia usar e mudar dados | Login obrigatório, contas criadas pela administração, bloqueio após tentativas | L1 | `tests/test_web_login.py`, `tests/test_contas.py` |
| **Página de senha provisória mostrava o usuário de quem criou a conta** (achado durante a fase, antes de publicar) | Variáveis do topo da página com nomes próprios (`pessoa_logada`) | L1 | `test_administracao_cria_conta_e_a_senha_aparece_uma_vez` |
| **Sem sinal, o envio falhava e as fotos tinham de ser escolhidas de novo** | Fotos guardadas no celular sobem sozinhas quando a conexão volta; "Fotos no celular" funciona sem sinal | L2 | `tests/navegador/test_aplicativo_navegador.py` |
| Scripts escritos dentro das páginas (tema, guia visual) impediam uma política de segurança rígida | Tudo em arquivos `.js`; CSP sem `unsafe-inline` para scripts | L2 | `test_nenhuma_pagina_tem_codigo_embutido` |
| Página inicial ainda dizia que envio e anotação "chegam nas próximas etapas" | Texto trocado por atalhos para as coletas e o cartão "Use como aplicativo" | L2 | — |
| Página inicial não dizia quanto faltava nem por onde continuar | Painel com "Faltam N regiões", "Continuar anotando" e "Precisa de atenção" | 4 | `tests/test_painel.py` |
| Regiões marcadas com dúvida ficavam esquecidas (não havia como achá-las) | Dúvidas listadas no painel; filtro "Em dúvida" na anotação em lote | 4 | `test_duvidas_levam_para_a_revisao_no_lote` |
| "Guia visual" (ferramenta de quem programa) no menu de quem coleta | Movido para o rodapé | 4 | `test_guia_visual_saiu_do_menu_e_foi_para_o_rodape` |
