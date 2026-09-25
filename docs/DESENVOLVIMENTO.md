# Guia de desenvolvimento

Para quem vai mexer no código. Para só usar a plataforma, veja o [README](../README.md).

## Preparar o ambiente

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` = tudo da plataforma + `pytest`.

## Rodar os testes

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Cada teste cria um banco novo numa pasta temporária, usando as **migrações de
verdade**. Nada toca em `C:\CafeData`. Rode os testes antes de cada commit.

| Arquivo | O que garante |
|---------|---------------|
| `tests/test_anotacoes.py` | Regras de anotação e cálculo de progresso (inclui a regressão do bug "100% com 4 anotados") |
| `tests/test_integridade.py` | Proteções do banco: chaves estrangeiras, cascatas, duplicatas |
| `tests/test_taxonomias.py` | Leitura dos YAML e mensagens de erro para quem edita |
| `tests/test_geometria.py` | Área e bbox dos polígonos |
| `tests/test_pessoas_e_armazenamento.py` | Identificação por nome, fotos por hash, configuração |
| `tests/test_migracoes_e_paginas.py` | Modelos e migrações em sincronia; páginas respondem |

## Mudar o banco de dados (migrações)

1. Altere o modelo em `app/dominio/`.
2. Gere a migração:
   ```powershell
   .\.venv\Scripts\flask.exe --app app db migrate -m "descreva a mudança"
   ```
   (Use `$env:CAFE_DATA_DIR` apontando para uma pasta de teste se não quiser que o
   comando leia o banco real.)
3. **Leia o arquivo gerado** em `migrations/versions/`. O Alembic não percebe tudo:
   renomear uma coluna vira "apagar e criar", o que **perde os dados**. Nesse caso,
   troque por `batch_op.alter_column(..., new_column_name=...)`.
4. Rode os testes. `test_modelos_e_migracoes_estao_em_sincronia` falha se o passo 2
   foi esquecido.
5. A migração é aplicada sozinha na próxima vez que a plataforma iniciar.

## Comandos úteis

```powershell
# Aplicar migrações e sincronizar taxonomias sem iniciar o servidor
.\.venv\Scripts\flask.exe --app app preparar-banco

# Servidor em modo desenvolvimento (recarrega ao salvar; só neste PC)
$env:CAFE_DEBUG = "1"; .\.venv\Scripts\python.exe run.py

# Usar outra pasta de dados (ex.: para experimentar sem mexer nos dados reais)
$env:CAFE_DATA_DIR = "C:\CafeData-teste"; .\.venv\Scripts\python.exe run.py
```

## Onde colocar cada coisa

| Vou criar... | Vai em |
|--------------|--------|
| Uma tabela ou campo novo | `app/dominio/` + migração |
| Uma regra ("não pode anotar X se Y") | `app/servicos/` + teste |
| Uma página | rota em `app/web/rotas.py` + template em `app/templates/` |
| Um endpoint JSON | `app/api/rotas.py` |
| Uma classe ou tipo de amostra | `taxonomias/*.yaml` (sem código) |

Convenções e o porquê da estrutura: [ARQUITETURA.md](ARQUITETURA.md).
