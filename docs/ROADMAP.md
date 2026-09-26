# Roteiro da reestruturação

Cada fase é aprovada antes de começar e termina com commits no git, então tudo pode
ser revisado ou desfeito.

| Fase | Status | Entrega |
|------|--------|---------|
| 0. Fundação | ✅ Concluída (25/09/2026) | Git, backup, limpeza de duplicatas, depurador fechado, esta documentação |
| 1. Dados | ✅ Concluída (25/09/2026) | Novo modelo de dados com migrações, classes por tipo de amostra (YAML), banco novo em `C:\CafeData`, 56 testes automáticos |
| 2. Ingestão | ✅ Concluída (25/09/2026) | Coletas, "Quem é você?", envio pela câmera ou em lote (rotação, GPS, repetidas, miniaturas), recortes prontos e COCO, segmentação em segundo plano com status ao vivo, motor clássico corrigido, servidor waitress |
| 3. Design system | ✅ Concluída (25/09/2026) | Tokens, componentes e guia visual (`/guia-visual`); tema claro/escuro; WCAG 2.2 AA verificada por testes (axe-core); pensado para celular; funciona offline |
| 4. Painel (dashboard) | ✅ Concluída (25/09/2026) | Página inicial com "quanto falta", filtro por tipo de amostra, progresso e classes, "Continuar anotando", "Precisa de atenção" (erros, dúvidas, coletas sem foto), atividade por dia e, para a administração, quem anotou ([decisão 0008](decisoes/0008-painel.md)) |
| 5. Anotação | ✅ Concluída (25/09/2026) | Uma por vez (atalhos, avanço automático, dúvida, observação, desfazer, contexto na foto) e em lote (marcar várias, aplicar, desfazer); motor clássico 2.1 (grãos separados). **Ficou de fora:** edição de contornos |
| 6. IA | ✅ Concluída para grãos (26/09/2026) | Motor `ia`: FastSAM encontra, SAM 2.1 contorna; testado na foto real (33 de ~33 grãos no recorte, contra 20 do motor clássico); opcional ("Instalar IA.bat"); parâmetros de cada segmentação guardados; "Segmentar de novo". Folhas, flores e frutos aguardam fotos reais ([decisão 0009](decisoes/0009-modelo-de-segmentacao.md)) |
| 7. Exportação e guia | ⏳ Próxima | CSV, COCO, YOLO, recortes por classe; guia do usuário |
| L1. Login e contas | ✅ Concluída (25/09/2026) | Login obrigatório; contas criadas pela administração (senha provisória); perfis membro/administração; bloqueio após tentativas; primeiro acesso com código ([decisão 0006](decisoes/0006-login-e-contas.md)) |
| L2. Aplicativo e publicação | ✅ Concluída (25/09/2026) | Instalar no celular como aplicativo; abre sem sinal; fotos guardadas no celular sobem sozinhas quando o sinal volta; segurança para a internet (CSP, limite por IP); "Publicar na internet.bat" com Tailscale Funnel ([decisão 0007](decisoes/0007-publicacao-e-aplicativo.md), [guia](PUBLICACAO.md)) |

Extras já entregues fora das fases:
- **Atalho de duplo clique** `Iniciar BeanLab.bat`: instala e inicia sozinho.
- **Python atualizado de 3.11 para 3.14**, com as bibliotecas nas versões mais recentes.
- **Excluir coleta e excluir conta** (pedido do responsável, 25/09/2026). Coleta: a
  administração sempre; quem criou, enquanto ninguém anotou; com anotações, confirma
  digitando o nome. Conta: nunca usada some; com trabalho vira "Pessoa removida nº X"
  (as anotações continuam, sem identificar ninguém).

## Decisões já tomadas com o responsável pelo projeto

- **Tipos de amostra na primeira versão:** grãos, folhas, flores e frutos (cerejas).
- **Dados antigos:** começar do zero. O estado antigo está em
  `backups/2026-09-25_estado-original/` (ver o LEIAME de lá: 301 imagens ainda
  precisam ser baixadas do OneDrive para completar o backup).
- **Usuários:** a equipe usa como aplicativo no celular, na fazenda. Por isso a
  interface é pensada primeiro para celular (login e contas: fase L1).
- **Tecnologia:** continua Python (3.14) + Flask, sem etapa de build no front-end
  (ver [decisoes/0001](decisoes/0001-manter-flask-sem-build.md)).
- **Código no GitHub, em repositório público:**
  https://github.com/mauris81/beanlab-coffee-vision. Fotos e banco nunca sobem
  (`.gitignore`). **Licença AGPL-3.0** (26/09/2026), por causa do FastSAM
  ([decisão 0009](decisoes/0009-modelo-de-segmentacao.md)).
- **Segmentação com IA:** FastSAM + SAM 2.1, opcional, testada na foto real de grãos.
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

- [ ] **Publicar:** criar a conta de administração (código na janela preta) e depois
      `Publicar na internet.bat` → 1, aprovando o link do Tailscale na primeira vez
      ([guia](PUBLICACAO.md)). Testar no celular com os dados móveis (Wi-Fi desligado).
- [ ] Deixar o PC sem atualização automática do Windows no horário de trabalho.

- [x] ~~Testar o motor de grãos com fotos reais~~: feito na Fase 6 com a foto da equipe.

- [ ] Abrir o OneDrive e baixar `app/uploads/` para completar o backup antigo.
      Depois disso, as pastas antigas `app/uploads/` e `instance/` podem ser apagadas
      (a plataforma nova não as usa mais).
- [ ] Validar com agrônomos as listas de classes em
      [MODELO_DE_DADOS.md](MODELO_DE_DADOS.md#classes-atuais-por-tipo-de-amostra).
- [ ] Definir uma rotina de backup para `C:\CafeData` (fica fora do OneDrive).
- [x] ~~Escolher uma licença~~: AGPL-3.0 (26/09/2026).
- [ ] **Instalar a IA** no PC da plataforma: `Instalar IA.bat` (já feito neste PC em 26/09/2026).
- [ ] **Mandar 5 a 10 fotos reais de folhas, flores e frutos** (e mais de grãos), para
      ligar e ajustar a IA nesses tipos (`ferramentas/avaliar_segmentacao.py`).
