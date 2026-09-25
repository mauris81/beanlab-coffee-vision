# Roteiro da reestruturação

Cada fase é aprovada antes de começar e termina com commits no git, então tudo pode
ser revisado ou desfeito.

| Fase | Status | Entrega |
|------|--------|---------|
| 0. Fundação | ✅ Concluída (25/09/2026) | Git, backup, limpeza de duplicatas, depurador fechado, esta documentação |
| 1. Dados | ✅ Concluída (25/09/2026) | Novo modelo de dados com migrações, classes por tipo de amostra (YAML), banco novo em `C:\CafeData`, 56 testes automáticos |
| 2. Ingestão | ⏳ Próxima | Envio por câmera/arquivo/lote, imagens já segmentadas, segmentação em segundo plano com progresso |
| 3. Design system | — | Cores, tipografia, componentes; tema claro/escuro; acessibilidade WCAG 2.2 AA; pensado para celular |
| 4. Dashboard | — | Visão por tipo de amostra: progresso, distribuição de classes, pendências |
| 5. Anotação | — | Atalhos de teclado, avanço automático, anotação em lote, desfazer, edição de contorno |
| 6. IA | — | Segmentação automática (FastSAM / SAM) testada nas fotos reais |
| 7. Exportação e guia | — | CSV, COCO, YOLO, recortes por classe; guia do usuário |
| H. Hospedagem online | ⏸️ Decidir após a Fase 2 | Acesso pelos celulares na fazenda sem este PC ligado. Comparar opções (Render, Railway, PythonAnywhere, servidor próprio), custo, internet na fazenda e troca de SQLite por PostgreSQL |

Extras já entregues fora das fases:
- **Atalho de duplo clique** `Iniciar BeanLab.bat`: instala e inicia sozinho.
- **Python atualizado de 3.11 para 3.14**, com as bibliotecas nas versões mais recentes.

## Decisões já tomadas com o responsável pelo projeto

- **Tipos de amostra na primeira versão:** grãos, folhas, flores e frutos (cerejas).
- **Dados antigos:** começar do zero. O estado antigo está em
  `backups/2026-09-25_estado-original/` (ver o LEIAME de lá: 301 imagens ainda
  precisam ser baixadas do OneDrive para completar o backup).
- **Usuários:** ainda não definido. A expectativa é uso como aplicativo no celular,
  na fazenda. Por isso: interface pensada primeiro para celular, cada pessoa se
  identifica pelo nome (sem senha), e o modelo de dados já prevê login no futuro.
- **Tecnologia:** continua Python (3.14) + Flask, sem etapa de build no front-end
  (ver [decisoes/0001](decisoes/0001-manter-flask-sem-build.md)).
- **Código no GitHub, em repositório público:**
  https://github.com/mauris81/beanlab-coffee-vision. Fotos e banco nunca sobem
  (`.gitignore`). Ainda sem licença, a decidir.
- **Hospedagem online:** decidir depois da Fase 2.
- **Dados (fotos e banco) em `C:\CafeData`**, fora do OneDrive
  (ver [decisoes/0003](decisoes/0003-dados-fora-do-onedrive.md)).
- **Classes:** começar com as listas propostas; ajustes depois, editando `taxonomias/`.

## Pendências para o responsável

- [ ] Abrir o OneDrive e baixar `app/uploads/` para completar o backup antigo.
      Depois disso, as pastas antigas `app/uploads/` e `instance/` podem ser apagadas
      (a plataforma nova não as usa mais).
- [ ] Validar com agrônomos as listas de classes em
      [MODELO_DE_DADOS.md](MODELO_DE_DADOS.md#classes-atuais-por-tipo-de-amostra).
- [ ] Definir uma rotina de backup para `C:\CafeData` (fica fora do OneDrive).
- [ ] Escolher uma licença para o repositório público (ou manter sem).
