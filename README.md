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

### Como usar

1. Toque em **Entrar** (topo) e diga seu nome. Não precisa de senha.
2. Em **Coletas → Nova coleta**, escolha o que foi fotografado (grãos, folhas, flores
   ou frutos) e dê um nome.
3. Na página da coleta, **Tirar foto** (abre a câmera do celular) ou **Escolher
   arquivos** (várias de uma vez) e **Enviar**.
4. Fotos de grãos são segmentadas sozinhas: o status muda de "Na fila" para "Pronta"
   sem precisar recarregar. Folhas, flores e frutos, por enquanto, precisam chegar já
   segmentados (recortes em PNG transparente ou um conjunto COCO).

A tela de anotação (dizer a classe de cada região) chega na Fase 5.

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
| `app/`            | Código da aplicação (detalhes em [docs/ARQUITETURA.md](docs/ARQUITETURA.md)) |
| `taxonomias/`     | **Classes de cada tipo de amostra**, editáveis sem programar ([como editar](taxonomias/LEIAME.md)) |
| `migrations/`     | Histórico de mudanças no banco (aplicado sozinho ao iniciar) |
| `tests/`          | Testes automáticos |
| `docs/`           | Documentação: roteiro, arquitetura, modelo de dados, decisões |
| `run.py`          | Ponto de entrada (usado pelo atalho) |
| **`C:\CafeData`** | **Banco de dados e fotos** (fora do projeto e do OneDrive; faça backup desta pasta) |
| `backups/`        | Cópia do sistema antigo (fora do git) |

As pastas `app/uploads/` e `instance/`, se existirem, são do sistema antigo e não são
mais usadas.

## Documentação

Comece por [docs/README.md](docs/README.md).
