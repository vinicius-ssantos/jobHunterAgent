# Runtime Structured Matching Source

## Papel Deste Documento

- [x] Este arquivo abre a próxima fase estrutural após a redução de hardcodes do legado
- [x] O objetivo aqui é fazer o runtime principal depender claramente de uma fonte estruturada de matching
- [x] A branch desta fase foi aberta: `refactor/runtime-structured-matching-source`
- [x] Continuidade desta fase em branch dedicada: `refactor/runtime-structured-matching-docs-and-exit-criteria`

## Objetivo Da Fase

Levar o projeto de:

- runtime principal ainda baseado em contrato legado encapsulado

para:

- runtime principal baseado em fonte estruturada, com legado residual apenas como compatibilidade marginal

## Escopo

Esta fase cobre:

- [x] introduzir no runtime principal uma fonte estruturada explícita de matching
- [ ] reduzir o papel central de `MatchingCriteria` legado
- [x] ligar a política de senioridade desconhecida ao caminho principal novo
- [x] reduzir ainda mais termos legados em `matching_prompt`, `collector` e `scoring`
- [x] preservar compatibilidade enquanto a transição estiver incompleta

Esta fase não cobre por padrão:

- [x] remoção imediata de todo fallback legado sem plano de migração
- [x] mudança de produto no fluxo principal de coleta/revisão
- [x] reescrita ampla do fluxo de candidatura

## Problema Atual

Mesmo após a fase anterior, o runtime ainda opera principalmente com:

- `LegacyMatchingConfig`
- `MatchingCriteria`
- `matching_prompt` legado
- `collector` e `scoring` ainda orientados por contrato antigo

O resultado é melhor do que antes, mas a fonte estruturada ainda não domina completamente o runtime principal.

## Linha De Trabalho Recomendada

### P0 — Fonte estruturada no runtime

- [x] definir o contrato estruturado mínimo que o runtime principal vai consumir
- [x] introduzir loader/bootstrap desse contrato no fluxo atual
- [x] fazer a composição depender desse contrato como caminho principal
- [x] manter fallback legado explícito e bem delimitado

### P0 — Senioridade como policy do caminho novo

- [x] mover a política de senioridade desconhecida para o contrato estruturado
- [x] fazer prefiltro/scoring respeitarem a mesma policy sem `if` espalhado
- [x] revisar integração com `core/seniority.py`

### P1 — Coleta, prompt e scoring

- [x] reduzir dependência do shape legado em `collector.py`
- [x] reduzir dependência do shape legado em `matching_prompt.py`
- [x] reduzir dependência do shape legado em `scoring.py`
- [ ] revisar rationale e descarte para o caminho principal novo

### P1 — Compatibilidade e documentação

- [x] documentar claramente o caminho principal novo vs fallback legado
- [x] revisar `.env.example`, `README.md` e `AGENTS.md`
- [x] registrar critérios de desligamento futuro do legado

### P1 — Testes

- [x] adicionar testes do runtime principal usando a fonte estruturada
- [x] preservar testes de compatibilidade do legado enquanto necessário
- [x] adicionar testes da policy de senioridade desconhecida no caminho novo

## Definição De Conclusão

Esta fase só fecha quando:

- [ ] o runtime principal depender claramente da fonte estruturada
- [ ] o legado estiver reduzido a compatibilidade marginal
- [x] senioridade desconhecida estiver modelada como policy do caminho novo
- [x] documentação e parte relevante dos testes já refletem esse novo centro de gravidade
