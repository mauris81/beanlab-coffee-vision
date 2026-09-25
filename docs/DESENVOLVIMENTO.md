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
| `tests/test_design_system.py` | Contraste de todas as cores (dois temas), ícones existentes, páginas sem internet, macros acessíveis |
| `tests/test_ingestao.py` | Fotos válidas/inválidas, rotação de celular, data e GPS, repetidas, recortes, COCO, exclusão segura |
| `tests/test_segmentacao.py` | Motor clássico, cores preservadas (regressão), jobs, erros do motor, retomada da fila |
| `tests/test_web_coletas.py` | "Quem é você?", CSRF, redirecionamento seguro, coletas, envio, status, miniaturas |
| `tests/test_anotacao.py` | Recortes (cache, concorrência), situação das regiões, lote, regras do desfazer, API e páginas de anotação |
| `tests/test_contas.py` | Senhas, login, bloqueio, "nunca sem administração", código do primeiro acesso |
| `tests/test_web_login.py` | Porta de entrada, primeiro acesso, senha provisória, administração, desconectar outros aparelhos, redirecionamento seguro |

Fixtures prontas (`tests/conftest.py`): `cliente` (sem login), `logado` (membro),
`logado_admin`, `administracao`; `criar_pessoa(...)` e `entrar_como(cliente, pessoa)`.

As fotos dos testes são geradas na hora (`tests/fabrica_imagens.py`): nenhum binário no git.

### Testes no navegador (opcionais, mais lentos)

```powershell
.\.venv\Scripts\python.exe -m pytest -m navegador
```

Abrem as páginas no Chrome ou Edge já instalados (via Playwright), num servidor
próprio com banco temporário. Rodam a auditoria de acessibilidade **axe-core** (WCAG 2.2
AA) e testam teclado, tema, diálogo, avisos e layout no celular
(`tests/navegador/`), além do **fluxo completo** de quem coleta (entrar, criar coleta,
enviar foto, acompanhar a segmentação, excluir) no celular e no computador, com a fila
em segundo plano como no uso real, e a **anotação** pelo teclado, pelo toque e em lote
(`test_anotacao_navegador.py`). Rode antes de mexer em telas, CSS ou JavaScript.

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

# Emergência: a única conta de administração esqueceu a senha
.\.venv\Scripts\flask.exe --app app redefinir-senha USUARIO

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
| Uma página | rota em `app/web/rotas.py` + template em `app/templates/` (siga o checklist de [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md)) |
| Um componente visual | macro em `templates/componentes.html` + CSS em `static/css/componentes.css` + exemplo em `/guia-visual` |
| Um ícone | `<symbol>` em `static/icones.svg` |
| Um endpoint JSON | `app/api/rotas.py` |
| Um motor de segmentação | arquivo em `app/segmentacao/` seguindo `base.py` + registro em `MOTORES` + `motor:` no YAML |
| Uma classe ou tipo de amostra | `taxonomias/*.yaml` (sem código) |

Convenções e o porquê da estrutura: [ARQUITETURA.md](ARQUITETURA.md).
