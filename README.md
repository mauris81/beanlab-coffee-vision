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
</details>

## Onde está cada coisa

| Pasta / arquivo   | O que é |
|-------------------|---------|
| `app/`            | Código da aplicação (rotas, modelos, segmentação, telas) |
| `app/uploads/`    | Fotos enviadas e recortes gerados (fora do git) |
| `instance/`       | Banco de dados SQLite (fora do git) |
| `backups/`        | Cópias de segurança (fora do git) |
| `docs/`           | Documentação: arquitetura, modelo de dados, decisões |
| `Iniciar BeanLab.bat` | Atalho de duplo clique para instalar e iniciar |
| `run.py`          | Ponto de entrada (usado pelo atalho) |

## Documentação

Comece por [docs/README.md](docs/README.md).
