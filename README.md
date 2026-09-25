# BeanLab Coffee Vision

Plataforma para **fotografar, segmentar e anotar** amostras de café (grãos, folhas,
flores e frutos). As anotações viram dados para pesquisa e para treinar modelos de
visão computacional.

> 🚧 **Em reestruturação.** O plano completo e o andamento estão em
> [docs/ROADMAP.md](docs/ROADMAP.md).

## Como rodar

Pré-requisito: Python 3.11 com o ambiente virtual `.venv` já criado.

```powershell
# 1. Ativar o ambiente virtual
.\.venv\Scripts\Activate.ps1

# 2. (Só na primeira vez) instalar as dependências
pip install -r requirements.txt

# 3. Iniciar
python run.py
```

Abra **http://127.0.0.1:5000** no computador. Para usar num celular conectado ao
mesmo Wi-Fi, use o endereço `http://192.168.x.x:5000` que aparece no terminal.

**Modo desenvolvimento** (recarrega ao salvar e mostra erros detalhados; aceita
conexões só deste computador):

```powershell
$env:CAFE_DEBUG = "1"; python run.py
```

## Onde está cada coisa

| Pasta / arquivo   | O que é |
|-------------------|---------|
| `app/`            | Código da aplicação (rotas, modelos, segmentação, telas) |
| `app/uploads/`    | Fotos enviadas e recortes gerados (fora do git) |
| `instance/`       | Banco de dados SQLite (fora do git) |
| `backups/`        | Cópias de segurança (fora do git) |
| `docs/`           | Documentação: arquitetura, modelo de dados, decisões |
| `run.py`          | Ponto de entrada |

## Documentação

Comece por [docs/README.md](docs/README.md).
