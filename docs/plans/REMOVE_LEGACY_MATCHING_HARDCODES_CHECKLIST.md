# Remove Legacy Matching Hardcodes

## Papel Deste Documento

- [x] Este arquivo abre a proxima fase da limpeza de matching
- [x] O objetivo aqui nao e criar um modelo novo; e reduzir residuos do caminho legado depois da consolidacao do `job_target.json`
- [x] A branch desta fase foi aberta: `refactor/remove-legacy-matching-hardcodes`

## Objetivo Da Fase

Levar o projeto de:

- fonte de verdade estruturada com compatibilidade ampla

para:

- fonte de verdade estruturada dominante, com legado residual minimo e encapsulado

## Escopo

Esta fase cobre:

- [ ] remocao de hardcodes residuais de matching fora do `job_target.json`
- [x] reducao da dependencia de `JOB_HUNTER_PROFILE_TEXT` no caminho principal
- [x] revisao das heuristicas de senioridade ainda espalhadas
- [x] reducao de duplicacao entre prefiltro, scorer e defaults operacionais
- [ ] deixar mais claro o que permanece como compatibilidade e o que sai do caminho principal

Esta fase nao cobre por padrao:

- [ ] remocao imediata e definitiva de todo fallback legado sem plano de migracao
- [ ] mudanca de produto no fluxo principal de coleta/revisao
- [ ] reescrita completa da fase de candidatura

## Problemas Residuais Esperados

Mesmo com `job_target.json` consolidado, ainda podem existir residuos como:

- [x] defaults ou listas de matching ainda acoplados ao `Settings`
- [x] heuristicas de senioridade duplicadas entre modulos
- [ ] termos de matching ainda presentes em prompts ou helpers fora do caminho oficial
- [ ] pontos do runtime que ainda tratam o legado como caminho quase equivalente ao novo
- [ ] documentacao que ainda descreve o legado com peso excessivo

## Linha De Trabalho Recomendada

### P0 — Mapear e isolar residuos

- [x] localizar hardcodes residuais de senioridade em `core/`, `collectors/` e `llm/`
- [ ] localizar termos de matching ainda espalhados fora do `job_target.json`
- [x] separar claramente o que e:
  - [x] regra oficial de dominio
  - [x] compatibilidade temporaria
  - [x] heuristica local de suporte

### P0 — Reduzir peso do legado no runtime principal

- [x] revisar `Settings` para manter apenas o minimo de compatibilidade necessario
- [x] reduzir defaults legados que ainda parecem fonte primaria
- [x] revisar `JOB_HUNTER_PROFILE_TEXT` para que continue apenas como compatibilidade passiva
- [x] garantir que o caminho principal do runtime continue nascendo de um contrato explicito, e nao do shape inteiro de `Settings`

### P0 — Senioridade

- [x] centralizar inferencia e normalizacao de senioridade em um unico ponto
- [x] eliminar heuristicas duplicadas ou divergentes
- [x] revisar aliases como `pleno -> mid`
- [x] revisar tokens como `staff`, `principal`, `lead`, `specialist`, `coord`, `head` quando fizer sentido
- [ ] manter politica explicita para senioridade desconhecida sem espalhar `if` local

### P1 — Prompt e rationale

- [x] revisar o prompt do scorer para garantir que nao restaram termos legados irrelevantes em hardcodes soltos
- [x] revisar a rationale para manter tokens curtos e consistentes
- [ ] evitar drift entre rationale deterministica e rationale do scorer

### P1 — Documentacao e setup

- [ ] revisar `.env.example` para ver se algum campo legado ainda pode sair do exemplo principal
- [ ] revisar `README.md` para diminuir ainda mais o protagonismo do legado
- [ ] atualizar `AGENTS.md` se a fase alterar regras arquiteturais ou de migracao

### P1 — Testes

- [ ] adicionar testes para garantir ausencia de regressao ao podar defaults legados
- [x] adicionar testes cobrindo centralizacao da senioridade
- [x] adicionar testes cobrindo helper de prompt/rationale legado
- [x] adicionar teste do contrato explicito de matching legado
- [ ] adicionar testes de regressao do caminho principal sem depender de `PROFILE_TEXT`

## Definicao De Conclusao

Esta fase so fecha quando:

- [ ] o caminho principal de matching depender claramente do `job_target.json`
- [ ] os residuos legados estiverem encapsulados e minimizados
- [x] heuristicas de senioridade estiverem centralizadas
- [ ] documentacao refletir o novo peso do legado
- [ ] os testes cobrirem a reducao de acoplamento sem quebrar o runtime

## Primeira Sequencia Recomendada

- [x] mapear hardcodes residuais
- [x] centralizar senioridade
- [x] reduzir defaults legados no runtime principal
- [x] revisar prompt/rationale
- [ ] revisar `.env.example`, `README.md` e `AGENTS.md`
- [ ] fechar com testes de regressao
