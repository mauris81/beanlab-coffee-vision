# Como editar as classes

Cada arquivo `.yaml` desta pasta é um **tipo de amostra** (grãos, folhas, flores,
frutos) com a lista de **classes** que aparecem na hora de anotar. Não é preciso saber
programar para editar: abra o arquivo no Bloco de Notas ou no VS Code.

Depois de salvar, **feche e abra a plataforma de novo**. As mudanças são aplicadas ao
iniciar. Se houver algum erro no arquivo, a janela preta mostra qual arquivo, qual
classe e o que corrigir.

## Formato de uma classe

```yaml
  - codigo: bicho_mineiro      # identificador fixo (veja o aviso abaixo)
    nome: Bicho-mineiro        # o que aparece na tela, pode ter acento e espaço
    tecla: "4"                 # atalho de teclado: um número ou letra, entre aspas
    cor: "#D55E00"             # cor em hexadecimal, entre aspas
    descricao: Lesões marrons…  # dica que ajuda quem anota (opcional)
```

A **ordem** das classes no arquivo é a ordem em que aparecem na tela.

## Segmentação automática (campo `motor`)

Logo abaixo de `ordem:`, o campo opcional `motor:` diz qual motor encontra os objetos
nas fotos deste tipo. Hoje existe só `classico` (grãos sobre fundo uniforme). Sem esse
campo, as fotos precisam chegar já segmentadas (recortes ou COCO).

## O que pode e o que não pode

| Quero... | Como fazer | Seguro? |
|----------|------------|---------|
| Mudar o nome exibido, a cor, a tecla ou a descrição | Edite o campo | ✅ Sim |
| Adicionar uma classe | Copie um bloco `- codigo: ...` e ajuste | ✅ Sim |
| Mudar a ordem | Mova o bloco inteiro | ✅ Sim |
| Remover uma classe | Apague o bloco | ✅ Sim. Ela fica **inativa**: some da tela, mas anotações antigas continuam guardadas. Se voltar ao arquivo, é reativada. |
| Mudar o `codigo` | ⚠️ **Não faça.** | ❌ O sistema entende como "remover uma classe e criar outra": as anotações antigas ficam na classe velha (inativa). |
| Adicionar um tipo de amostra | Crie um arquivo `.yaml` novo com `codigo`, `nome` e `classes` | ✅ Sim |

## Regras que o sistema confere

- `codigo`: só letras minúsculas sem acento, números e `_`, começando por letra.
- Cada `codigo` e cada `tecla` só pode aparecer uma vez no mesmo arquivo.
- `cor` no formato `"#RRGGBB"`.
- As teclas **Z** (desfazer) e **D** (dúvida) são da tela de anotação: não use em classes.

## Sobre as cores

As cores atuais são baseadas na paleta Okabe-Ito, pensada para quem tem daltonismo,
mais um marrom e um cinza-escuro. Serão revisadas na Fase 3 (design system). A cor
nunca aparece sozinha na tela: sempre vem junto com o nome da classe.
