# Plataforma na internet e no celular

Guia para **quem cuida do PC** onde a plataforma roda. Por que é assim:
[decisão 0007](decisoes/0007-publicacao-e-aplicativo.md).

## Como funciona, em uma figura

```
 Celular na fazenda ──(4G, com cadeado)──► Tailscale ──► este PC (plataforma aberta)
 Celular no Wi-Fi do escritório ─────────────────────────► este PC
```

A plataforma continua **rodando neste PC**. O Tailscale só dá um endereço na internet
para ela. Então o PC precisa estar **ligado**, com o **Tailscale conectado** e a
plataforma **aberta** (janela do `Iniciar BeanLab.bat`).

## Primeira vez

1. **Crie a conta de administração antes de publicar** (veja o README: código de
   primeiro acesso). Assim ninguém chega na plataforma sem senha.
2. Dê dois cliques em **`Publicar na internet.bat`** e escolha **1**.
3. Na primeira vez aparece um link: abra no navegador, entre na sua conta do Tailscale
   e **aprove** (liga o HTTPS e o Funnel na sua rede). A janela continua sozinha.
4. Aparece o endereço, algo como `https://desktop-xxxx.tailxxxx.ts.net`. É esse o
   endereço da plataforma na internet. **Mande para a equipe.**
5. Feche e abra a plataforma de novo: a janela preta passa a mostrar o endereço da
   internet junto com os outros.

Para **tirar da internet**: `Publicar na internet.bat` → **2**. No Wi-Fi continua
funcionando.

## No celular: instalar como aplicativo

1. Abra o endereço `https://...ts.net` no **Chrome** (Android) ou **Safari** (iPhone).
2. Entre com usuário e senha.
3. Na página inicial aparece **"Use como aplicativo no celular"**:
   - **Android:** toque em **Instalar o aplicativo**.
   - **iPhone:** **Compartilhar** → **Adicionar à Tela de Início**.
4. Pronto: o ícone do BeanLab fica na tela inicial e abre em tela cheia.

> Pelo endereço do Wi-Fi (`http://192.168...`) o celular não deixa instalar: só pelo
> endereço com `https://`.

## Sem sinal no campo

- **Dá para continuar fotografando.** Sem sinal, o aplicativo abre a página
  **"Fotos no celular"**: escolha a coleta e tire as fotos. Elas ficam guardadas no
  celular.
- Se o sinal cair **no meio de um envio**, as fotos também ficam guardadas. Com sinal
  fraco, dá para tocar em **"Guardar no celular e enviar depois"** e seguir trabalhando.
- **Quando o sinal voltar, as fotos sobem sozinhas.** No topo das páginas aparece
  "N fotos guardadas no celular" enquanto houver alguma esperando.
- **Crie a coleta antes de ir para o campo** e abra a plataforma com sinal uma vez:
  a lista de coletas fica guardada no celular.

## Cuidados com o PC

- Enquanto a plataforma está aberta, **o PC não suspende sozinho** (a tela pode apagar
  normalmente). Mas não desligue, não reinicie para atualizar o Windows no meio do
  expediente e não feche a tampa, se for notebook.
- Faça **backup de `C:\CafeData`** (banco e fotos) com frequência.
- Se o PC desligar, a plataforma sai do ar. As fotos esperam nos celulares e sobem
  quando ela voltar.

## Segurança (o que já está pronto)

- Endereço com **HTTPS** (cadeado): ninguém no caminho vê senhas nem fotos.
- **Login obrigatório**; contas só pela administração; bloqueio após tentativas erradas
  (por conta e por endereço de internet).
- O navegador só roda código da própria plataforma (política de conteúdo).
- O **modo desenvolvimento** (para programar) não atende pela internet, mesmo com o
  endereço ligado.
- Para um celular perdido ou alguém que saiu da equipe: em **Pessoas**, desative a
  conta ou gere uma nova senha. A pessoa sai de todos os aparelhos na hora.

## Problemas comuns

| O que acontece | O que fazer |
|----------------|-------------|
| O endereço `https://...ts.net` não abre | Confira: PC ligado? Tailscale conectado (ícone perto do relógio)? Janela da plataforma aberta? `Publicar na internet.bat` diz que está ligado? |
| "Muitas tentativas erradas a partir desta conexão" | Espere 15 minutos. Se esqueceu a senha, peça uma nova à administração. |
| As fotos guardadas não sobem | Abra a plataforma com sinal. Se aparecer "Entre na plataforma de novo", entre com o seu usuário: as fotos só sobem com a mesma pessoa que as guardou. |
| Uma foto guardada ficou "com problema" | Veja a mensagem em "Fotos no celular". Se a coleta foi excluída, use "Salvar no aparelho" antes de excluir a foto guardada. |
