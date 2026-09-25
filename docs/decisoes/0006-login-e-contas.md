# 0006 — Login com contas criadas pela administração

**Status:** Aceita · 25/09/2026

## Contexto
Até a Fase 5 cada pessoa só dizia o próprio nome, sem senha. Isso bastava dentro da
rede da fazenda, mas a plataforma vai ser publicada na internet (no PC do responsável,
com endereço HTTPS; ver ROADMAP, fase L2). Sem login, qualquer pessoa com o endereço
veria e mudaria os dados.

Decisões do responsável: **a administração cria as contas**; perfis **membro** e
**administração**; nada de e-mail (muita gente no campo não usa).

## Decisão
- **Toda página exige login**, menos entrar, primeiro acesso, arquivos estáticos e
  `/api/saude`. A regra fica num lugar só (`proteger_paginas`, em
  `app/web/identidade.py`): uma página nova já nasce protegida.
- **A administração cria a conta** e recebe uma **senha provisória** fácil de ditar
  (ex.: `safra-lua-4821`), mostrada **uma única vez**. No primeiro acesso a pessoa é
  obrigada a criar a própria senha.
- **Senha esquecida:** a administração gera uma nova provisória. Se o único
  administrador esquecer a senha, há o comando de emergência
  `flask --app app redefinir-senha USUARIO`, que exige acesso ao computador.
- **Primeiro administrador:** exige um **código mostrado só na janela do servidor**.
  Assim, mesmo com a plataforma já publicada, ninguém de fora consegue se cadastrar
  como administrador antes do responsável.
- **Segurança das senhas:**
  - guardadas só como hash (scrypt);
  - mínimo de 8 caracteres, recusando as óbvias;
  - a mesma mensagem para usuário inexistente e senha errada;
  - 5 erros seguidos bloqueiam a conta por 5 minutos.
- **Sessão:**
  - fica aberta por 90 dias no aparelho, como um aplicativo;
  - é renovada a cada login, o que evita "fixação de sessão";
  - trocar a senha ou desativar a conta **desconecta os outros aparelhos na hora**, porque a "versão da sessão" muda.
- **A plataforma nunca fica sem administrador ativo:** não dá para desativar a si mesmo nem rebaixar o último.

## Consequências
- ✅ Pronto para publicar na internet.
- ✅ Quem anotou o quê continua confiável (cada anotação tem dono com senha).
- ⚠️ Sem "esqueci a senha" automático: depende da administração. É aceitável para uma equipe pequena.
- ⚠️ Pessoas do sistema antigo (só nome) viraram contas **sem senha**. Elas aparecem
  como "Sem senha" em Pessoas, e a administração define uma com "Nova senha".
- 🔁 Se um dia houver muitas pessoas, reavaliar autocadastro com aprovação ou login
  pela instituição.
