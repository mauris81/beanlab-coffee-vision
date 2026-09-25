# Roteiro da reestruturação

Cada fase é aprovada antes de começar e termina com commits no git, então tudo pode
ser revisado ou desfeito.

| Fase | Status | Entrega |
|------|--------|---------|
| 0. Fundação | ✅ Concluída (25/09/2026) | Git, backup, limpeza de duplicatas, depurador fechado, esta documentação |
| 1. Dados | ✅ Concluída (25/09/2026) | Novo modelo de dados com migrações, classes por tipo de amostra (YAML), banco novo em `C:\CafeData`, 56 testes automáticos |
| 2. Ingestão | ✅ Concluída (25/09/2026) | Coletas, "Quem é você?", envio pela câmera ou em lote (rotação, GPS, repetidas, miniaturas), recortes prontos e COCO, segmentação em segundo plano com status ao vivo, motor clássico corrigido, servidor waitress |
| 3. Design system | ✅ Concluída (25/09/2026) | Tokens, componentes e guia visual (`/guia-visual`); tema claro/escuro; WCAG 2.2 AA verificada por testes (axe-core); pensado para celular; funciona offline |
| 4. Dashboard | ⏳ Próxima (depois da 5, por decisão) | Visão por tipo de amostra: progresso, distribuição de classes, pendências |
| 5. Anotação | ✅ Concluída (25/09/2026) | Uma por vez (atalhos, avanço automático, dúvida, observação, desfazer, contexto na foto) e em lote (marcar várias, aplicar, desfazer); motor clássico 2.1 (grãos separados). **Ficou de fora:** edição de contornos |
| 6. IA | — | Segmentação automática (FastSAM / SAM) testada nas fotos reais |
| 7. Exportação e guia | — | CSV, COCO, YOLO, recortes por classe; guia do usuário |
| L1. Login e contas | ✅ Concluída (25/09/2026) | Login obrigatório; contas criadas pela administração (senha provisória); perfis membro/administração; bloqueio após tentativas; primeiro acesso com código ([decisão 0006](decisoes/0006-login-e-contas.md)) |
| L2. Aplicativo e publicação | ⏳ Próxima | Instalar no celular como aplicativo; fila de fotos no celular para sinal fraco; publicar no PC do responsável com Tailscale Funnel (HTTPS grátis) |

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
- **Hospedagem:** no PC do responsável, com Tailscale Funnel (endereço HTTPS grátis). As
  opções gratuitas na nuvem foram descartadas: Render apaga os arquivos e dorme; a
  Oracle cortou o plano grátis pela metade em 06/2026 e recolhe servidores ociosos.
- **Login:** contas criadas pela administração; perfis membro e administração; sem
  e-mail. Sinal no campo às vezes fraco: o aplicativo vai guardar fotos no celular.
- **Ordem:** Fase 3 (design system) feita antes da Fase 2, para as telas de envio já
  nascerem no visual novo, sem retrabalho.
- **Dados (fotos e banco) em `C:\CafeData`**, fora do OneDrive
  (ver [decisoes/0003](decisoes/0003-dados-fora-do-onedrive.md)).
- **Classes:** começar com as listas propostas; ajustes depois, editando `taxonomias/`.

## Pendências para o responsável

- [ ] **Testar o motor de grãos com fotos reais** (fundo azul). Os testes usam fotos
      sintéticas; a foto original do projeto (`teste_1.jpeg`) está só na nuvem do OneDrive.

- [ ] Abrir o OneDrive e baixar `app/uploads/` para completar o backup antigo.
      Depois disso, as pastas antigas `app/uploads/` e `instance/` podem ser apagadas
      (a plataforma nova não as usa mais).
- [ ] Validar com agrônomos as listas de classes em
      [MODELO_DE_DADOS.md](MODELO_DE_DADOS.md#classes-atuais-por-tipo-de-amostra).
- [ ] Definir uma rotina de backup para `C:\CafeData` (fica fora do OneDrive).
- [ ] Escolher uma licença para o repositório público (ou manter sem).
