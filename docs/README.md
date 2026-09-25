# Documentação

| Documento | Para quem | O que responde |
|-----------|-----------|----------------|
| [ROADMAP.md](ROADMAP.md) | Todos | Em que fase estamos e o que vem depois |
| [ARQUITETURA.md](ARQUITETURA.md) | Quem programa | Como o código está organizado e por quê |
| [MODELO_DE_DADOS.md](MODELO_DE_DADOS.md) | Quem programa / pesquisa | Quais dados guardamos e como se relacionam |
| [DESENVOLVIMENTO.md](DESENVOLVIMENTO.md) | Quem programa | Como rodar testes e mudar o banco |
| [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) | Quem programa / desenha | Cores, componentes, acessibilidade, como escrever textos da tela |
| [../taxonomias/LEIAME.md](../taxonomias/LEIAME.md) | Agrônomos / pesquisa | Como editar as classes de cada tipo de amostra |
| [PROBLEMAS_CONHECIDOS.md](PROBLEMAS_CONHECIDOS.md) | Todos | Bugs conhecidos e em que fase serão resolvidos |
| [decisoes/](decisoes/) | Quem programa | Registro de decisões técnicas (ADRs) |

Um **guia do usuário** (para quem coleta e anota na fazenda) será escrito na Fase 7,
quando as telas novas estiverem prontas.

## Como manter esta documentação

- Mudou a estrutura do código? Atualize `ARQUITETURA.md`.
- Mudou uma tabela do banco? Atualize `MODELO_DE_DADOS.md` (e gere a migração:
  veja `DESENVOLVIMENTO.md`).
- Tomou uma decisão que alguém vai questionar daqui a 6 meses? Crie um arquivo novo
  em `decisoes/` seguindo o modelo dos existentes.
