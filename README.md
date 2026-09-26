# BeanLab Coffee Vision

Plataforma para **fotografar, segmentar e anotar** amostras de café (grãos, folhas,
flores e frutos). As anotações viram dados para pesquisa e para treinar modelos de
visão computacional.

>  **Em reestruturação.** O plano completo e o andamento estão em
> [docs/ROADMAP.md](docs/ROADMAP.md).

## Como rodar

**Dê dois cliques em `Iniciar BeanLab.bat`.** Pronto.

Na primeira vez ele prepara tudo sozinho (leva alguns minutos). Nas próximas, abre em
segundos. O navegador abre automaticamente, e a janela preta mostra o endereço para
usar nos **celulares conectados ao mesmo Wi-Fi**. Para desligar, feche a janela preta.

> **Na primeira vez**, o Windows pode perguntar se o Python pode acessar a rede.
> Clique em **Permitir** (rede privada). Sem isso os celulares não conseguem acessar.

**Único pré-requisito:** [Python 3.14](https://www.python.org/downloads/) instalado.

### Primeira vez (criar a conta de administração)

Na primeira vez, a plataforma pede um **código de primeiro acesso**: ele aparece na
**janela preta**, logo abaixo dos endereços. Com ele você cria a sua conta de
administração. Depois, em **Pessoas**, crie as contas da equipe: cada pessoa recebe um
usuário e uma senha provisória, e cria a própria senha no primeiro acesso.

> Esqueceu a senha de administração? Com a plataforma fechada, abra o PowerShell na
> pasta do projeto e rode:
> `.\.venv\Scripts\flask.exe --app app redefinir-senha SEU_USUARIO`

### Como usar

1. **Entre** com usuário e senha (a administração passa para você).
2. Em **Coletas → Nova coleta**, escolha o que foi fotografado (grãos, folhas, flores
   ou frutos) e dê um nome.
3. Na página da coleta, **Tirar foto** (abre a câmera do celular) ou **Escolher
   arquivos** (várias de uma vez) e **Enviar**.
4. Fotos de grãos são segmentadas sozinhas: o status muda de "Na fila" para "Pronta"
   sem precisar recarregar. Com a **IA** instalada (veja abaixo), vale qualquer fundo e
   grãos encostados; sem ela, o motor clássico pede **fundo azul**. Folhas, flores e
   frutos, por enquanto, precisam chegar já segmentados (recortes em PNG transparente ou
   um conjunto COCO).
5. **Anotar:** na página da coleta, "Começar a anotar". Escolha a classe de cada região
   com um toque ou uma tecla (1–9) e a tela já vai para a próxima. Z desfaz; D marca
   dúvida; ? mostra os atalhos. Para muitas regiões iguais, use **Anotar em lote**.
6. **Acompanhar:** a página inicial (**Painel**) diz quanto falta, tem o botão
   **Continuar anotando** e lista o que precisa de atenção (fotos com erro, dúvidas).
   Dá para ver só um tipo de amostra (Grãos, Folhas...).
7. **Excluir:** uma foto, pela lixeira no cartão dela; a coleta inteira, no fim da página
   da coleta; uma conta, em **Pessoas** (só a administração).

### No celular, como aplicativo, e fora do Wi-Fi

Dê dois cliques em **`Publicar na internet.bat`** e escolha **1**: a plataforma ganha
um endereço com cadeado (`https://...ts.net`) que funciona em qualquer lugar, até nos
dados móveis. Por esse endereço, o celular **instala a plataforma como aplicativo**
(cartão na página inicial) e ela **abre mesmo sem sinal**: as fotos ficam guardadas no
celular e sobem sozinhas quando a conexão volta.

O PC continua sendo o servidor: precisa ficar ligado, com o Tailscale conectado e a
plataforma aberta. Passo a passo e cuidados: [docs/PUBLICACAO.md](docs/PUBLICACAO.md).

### Segmentação com IA (opcional)

Dê dois cliques em **`Instalar IA.bat`** (uma vez só; baixa cerca de 1 GB). Depois,
feche e abra a plataforma: a janela preta mostra "Grãos (IA)". A IA (FastSAM + SAM 2.1)
acha praticamente todos os grãos em qualquer fundo, com contornos precisos, e leva
cerca de 2 minutos por foto neste PC, em segundo plano. Fotos antigas: "Segmentar de
novo", na página da coleta. Por que estes modelos:
[docs/decisoes/0009](docs/decisoes/0009-modelo-de-segmentacao.md).

### Baixando o projeto em outro computador

Em **https://github.com/mauris81/beanlab-coffee-vision**, clique no botão verde
**Code → Download ZIP**, extraia a pasta e dê dois cliques em `Iniciar BeanLab.bat`.
(Quem usa git: `git clone` e o mesmo duplo clique.)

<details>
<summary>Para quem programa: rodar pelo terminal</summary>

```powershell
py -3.14 -m venv .venv                      # só na primeira vez
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

**Modo desenvolvimento** (recarrega ao salvar e mostra erros detalhados; aceita
conexões só deste computador):

```powershell
$env:CAFE_DEBUG = "1"; .\.venv\Scripts\python.exe run.py
```

Testes, migrações do banco e onde colocar cada coisa:
[docs/DESENVOLVIMENTO.md](docs/DESENVOLVIMENTO.md).
</details>

## Onde está cada coisa

| Pasta / arquivo   | O que é |
|-------------------|---------|
| `Iniciar BeanLab.bat` | Atalho de duplo clique para instalar e iniciar |
| `Publicar na internet.bat` | Liga ou desliga o endereço na internet (Tailscale Funnel) |
| `Instalar IA.bat` | Instala a segmentação com IA (opcional, ~1 GB) |
| `app/`            | Código da aplicação (detalhes em [docs/ARQUITETURA.md](docs/ARQUITETURA.md)) |
| `taxonomias/`     | **Classes de cada tipo de amostra**, editáveis sem programar ([como editar](taxonomias/LEIAME.md)) |
| `migrations/`     | Histórico de mudanças no banco (aplicado sozinho ao iniciar) |
| `tests/`          | Testes automáticos |
| `docs/`           | Documentação: roteiro, arquitetura, modelo de dados, decisões |
| `run.py`          | Ponto de entrada (usado pelo atalho) |
| `ferramentas/`    | Scripts de apoio para quem programa (ex.: gerar os ícones do aplicativo) |
| **`C:\CafeData`** | **Banco de dados e fotos** (fora do projeto e do OneDrive; faça backup desta pasta) |
| `backups/`        | Cópia do sistema antigo (fora do git) |

As pastas `app/uploads/` e `instance/`, se existirem, são do sistema antigo e não são
mais usadas.

## Documentação

Comece por [docs/README.md](docs/README.md).

## Licença

[AGPL-3.0](LICENSE). O código é aberto; quem oferecer uma versão modificada pela
internet precisa disponibilizar o código dessa versão. A escolha vem do FastSAM
(Ultralytics, AGPL-3.0), usado na segmentação com IA
([decisão 0009](docs/decisoes/0009-modelo-de-segmentacao.md)). A fonte Atkinson
Hyperlegible Next é OFL (`app/static/fontes/`).
