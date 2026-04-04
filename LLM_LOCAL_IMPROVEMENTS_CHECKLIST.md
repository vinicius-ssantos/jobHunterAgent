# Checklist De Melhorias Com LLM Local

## Objetivo

Esta branch existe para introduzir melhorias que usam o LLM local como camada assistiva, sem substituir a logica deterministica principal do produto.

As melhorias devem:

- manter fallback conservador
- nao inventar dados ausentes
- registrar rationale curto quando o modelo decidir algo relevante
- preservar o loop principal estavel

## Ordem Recomendada

### Fase 1 - Classificacao de aplicabilidade da candidatura

Objetivo:
- enriquecer a classificacao `auto_supported` / `manual_review` / `unsupported`

Escopo:
- usar o LLM local como assessor opcional
- manter a classificacao deterministica atual como fallback obrigatorio
- persistir rationale consistente

Definicao de pronto:
- drafts passam a carregar classificacao mais rica quando o modelo estiver habilitado
- se o LLM falhar, o comportamento atual permanece identico

### Fase 2 - Extracao estruturada de requisitos

Objetivo:
- derivar sinais operacionais adicionais da vaga

Campos alvo:
- senioridade inferida
- stack principal
- stack secundaria
- ingles exigido
- sinais de lideranca

Definicao de pronto:
- os dados estruturados sao derivados sem quebrar a persistencia existente
- o modelo nunca sobrescreve campos confiaveis com invencao

### Fase 3 - Melhor rationale para revisao humana

Objetivo:
- melhorar a legibilidade dos motivos no Telegram

Escopo:
- separar pontos a favor, pontos contra e risco
- manter mensagens curtas

Definicao de pronto:
- o rationale fica mais util para revisao humana sem inflar o card

### Fase 4 - Priorizacao operacional da fila

Objetivo:
- ajudar a ordenar o que revisar primeiro

Escopo:
- sugerir prioridade de revisao e de candidatura
- manter isso como metadado assistivo, nao regra absoluta

Definicao de pronto:
- filas e candidatos podem ser ordenados com apoio do modelo

### Fase 5 - Enriquecimento contextual dos cards de candidatura

Objetivo:
- tornar a fila de candidatura mais acionavel com os sinais estruturados ja extraidos

Escopo:
- reaproveitar senioridade, stack, ingles e lideranca nas mensagens do Telegram
- manter a exibicao curta e operacional

Definicao de pronto:
- os cards de candidatura mostram resumo estruturado util sem inflar a fila

## Regras

- usar LLM apenas como apoio, nao como autoridade unica
- todo uso novo precisa de teste
- fallback deterministico obrigatorio
- commit por fase, em portugues

## Checklist

- [x] Fase 1 concluida
- [x] Fase 2 concluida
- [x] Fase 3 concluida
- [x] Fase 4 concluida
- [x] Fase 5 concluida
- [x] README atualizado se a operacao mudar
- [x] AGENTS atualizado se as regras mudarem
- [x] loop principal validado ao final
