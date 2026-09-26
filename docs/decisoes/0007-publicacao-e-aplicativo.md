# 0007 — Publicar no PC do responsável e usar como aplicativo, mesmo sem sinal

**Status:** Aceita · 25/09/2026

## Contexto
A equipe usa a plataforma no celular, na fazenda, onde o sinal **às vezes é fraco**. Até
aqui ela só funcionava no Wi-Fi do PC onde roda. O responsável pediu hospedagem
**grátis** e decidiu hospedar **no próprio PC**.

As alternativas gratuitas na nuvem foram descartadas (pesquisa de 09/2026):
- **Render (grátis):** apaga os arquivos a cada reinício (as fotos sumiriam) e "dorme"
  sem uso (a primeira abertura demora quase um minuto).
- **Oracle Cloud (grátis):** o plano foi cortado pela metade em 06/2026, e servidores
  ociosos são recolhidos.
- **Túnel da Cloudflare:** gratuito, mas o endereço fixo exige um domínio próprio (pago).

## Decisão

### Publicação: Tailscale Funnel
O Tailscale (já instalado no PC) cria um endereço fixo com HTTPS de verdade
(`https://<nome-do-pc>.<rede>.ts.net`) e repassa os acessos para a plataforma no PC.
- **Liga e desliga com "Publicar na internet.bat"**, sem abrir portas no roteador.
- A plataforma **mostra o endereço** na janela preta e sugere-o na página inicial.
- Enquanto a janela está aberta, **o PC não suspende sozinho** (a tela ainda apaga).

### Segurança para ficar exposta na internet (`app/seguranca.py`)
- **Política de conteúdo (CSP):** o navegador só roda código vindo da própria
  plataforma. Nenhum `<script>` escrito dentro da página. Com isso, um texto
  malicioso que escapasse para a página (XSS) não roda. Um teste confere todas as
  páginas.
- **Cabeçalhos do Tailscale só valem vindos deste PC.** O Funnel conta o IP real do
  celular (`X-Forwarded-For`) e que o acesso foi HTTPS (`X-Forwarded-Proto`). Quem está
  no Wi-Fi fala direto com a plataforma, então nesses pedidos os cabeçalhos são
  apagados: ninguém consegue fingir outro endereço.
- **Cookie "Secure" e HSTS quando o acesso é HTTPS.** Pelo Wi-Fi (http) continua
  funcionando; os dois endereços são "sites" diferentes para o navegador.
- **Limite de tentativas por endereço (IP):** 20 erros em 15 minutos, somados em todas
  as contas. Complementa o bloqueio por conta (5 erros) e protege o código de
  primeiro acesso de adivinhação.
- **Modo desenvolvimento nunca atende pela internet** (responde 403), mesmo que o
  Funnel esteja ligado apontando para ele.

### Aplicativo instalável (PWA)
O navegador instala a plataforma como aplicativo (ícone, tela cheia). Exige HTTPS, que o
Funnel dá. Manifesto em `static/manifest.json`; ícones gerados do logotipo por
`ferramentas/gerar_icones_do_aplicativo.py`. O cartão "Instalar" aparece só onde dá.

### Sem sinal: a fila de fotos no celular
- Um **service worker** (`templates/sw.js`, servido em `/sw.js`) guarda no celular os
  arquivos da plataforma e a página **"Fotos no celular"**. Sem sinal (ou se a página
  demorar mais de 15 s), o aplicativo abre essa página em vez de uma tela de erro.
- **Páginas com dados nunca ficam guardadas no celular.** "Fotos no celular" é genérica:
  a lista de coletas e as fotos vêm do próprio aparelho.
- **Fotos sem sinal ficam no banco do navegador (IndexedDB)** até conseguirem subir
  (`static/js/fila-fotos.js`). Entram na fila quando:
  - o envio falha por falta de conexão;
  - o celular já está sem sinal ao tocar em "Enviar";
  - a pessoa desiste de esperar um envio lento ("Guardar no celular e enviar depois");
  - a pessoa fotografa direto pela página "Fotos no celular".
- **Sobem sozinhas:** quando a conexão volta, a cada minuto com a plataforma aberta e,
  no Chrome/Android, até com o aplicativo fechado ("sincronização em segundo plano").
  Uma de cada vez: com sinal fraco, pedidos pequenos têm mais chance.
- **Enviar duas vezes não duplica:** a plataforma reconhece a foto pelo conteúdo (hash).
- **Cada foto guardada tem dona:** só sobe quando a mesma pessoa estiver logada naquele
  celular. Num celular compartilhado, ninguém envia fotos no nome de outra pessoa.

## Consequências
- ✅ Custo zero e fotos no mesmo disco de sempre (`C:\CafeData`).
- ✅ Dá para trabalhar no campo sem sinal; nada se perde quando a conexão cai.
- ⚠️ **O PC precisa ficar ligado**, com a plataforma e o Tailscale abertos. Se o PC
  desligar, a plataforma sai do ar (as fotos esperam nos celulares).
- ⚠️ A velocidade depende da internet de onde o PC está (principalmente o envio de
  fotos grandes).
- ⚠️ A fila guarda fotos só para coletas que já existiam quando o celular teve sinal.
  Criar coleta sem sinal fica para depois, se fizer falta.
- ⚠️ No iPhone não há sincronização em segundo plano: as fotos sobem quando o
  aplicativo é aberto com sinal.
- 🔁 Se o uso crescer (muita gente, muitas fotos), reavaliar um servidor dedicado.
