# Roteiro da reestruturação

Cada fase é aprovada antes de começar e termina com commits no git, então tudo pode
ser revisado ou desfeito.

| Fase | Status | Entrega |
|------|--------|---------|
| 0. Fundação | ✅ Concluída (25/09/2026) | Git, backup, limpeza de duplicatas, depurador fechado, esta documentação |
| 1. Dados | ⏳ Próxima | Novo modelo de dados com migrações, classes por tipo de amostra (YAML), banco novo, testes |
| 2. Ingestão | — | Envio por câmera/arquivo/lote, imagens já segmentadas, segmentação em segundo plano com progresso |
| 3. Design system | — | Cores, tipografia, componentes; tema claro/escuro; acessibilidade WCAG 2.2 AA; pensado para celular |
| 4. Dashboard | — | Visão por tipo de amostra: progresso, distribuição de classes, pendências |
| 5. Anotação | — | Atalhos de teclado, avanço automático, anotação em lote, desfazer, edição de contorno |
| 6. IA | — | Segmentação automática (FastSAM / SAM) testada nas fotos reais |
| 7. Exportação e guia | — | CSV, COCO, YOLO, recortes por classe; guia do usuário |

## Decisões já tomadas com o responsável pelo projeto

- **Tipos de amostra na primeira versão:** grãos, folhas, flores e frutos (cerejas).
- **Dados antigos:** começar do zero. O estado antigo está em
  `backups/2026-09-25_estado-original/` (ver o LEIAME de lá: 301 imagens ainda
  precisam ser baixadas do OneDrive para completar o backup).
- **Usuários:** ainda não definido. A expectativa é uso como aplicativo no celular,
  na fazenda. Por isso: interface pensada primeiro para celular, cada pessoa se
  identifica pelo nome (sem senha), e o modelo de dados já prevê login no futuro.
- **Tecnologia:** continua Python + Flask, sem etapa de build no front-end
  (ver [decisoes/0001](decisoes/0001-manter-flask-sem-build.md)).

## Pendências para o responsável

- [ ] Abrir o OneDrive e baixar `app/uploads/` para completar o backup antigo.
- [ ] Validar com agrônomos as listas de classes propostas em
      [MODELO_DE_DADOS.md](MODELO_DE_DADOS.md#classes-propostas-por-tipo-de-amostra).
- [ ] Decidir se os dados (fotos e banco) saem da pasta do OneDrive
      (ver [decisoes/0003](decisoes/0003-dados-fora-do-onedrive.md)).
