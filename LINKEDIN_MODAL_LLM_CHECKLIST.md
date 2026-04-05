# Checklist Do Interpretador LLM Do Modal Do LinkedIn

## Objetivo

Esta branch existe para melhorar a automacao assistida de candidatura no LinkedIn usando LLM local como interpretador do estado do modal.

O objetivo nao e entregar o controle do fluxo para a LLM.
O objetivo e:

- capturar o estado atual do modal de candidatura
- resumir o que a interface esta mostrando
- classificar a etapa atual do fluxo
- sugerir o proximo passo provavel
- manter a execucao real sob controle deterministico e com guardrails

## Principios

- a LLM e assistiva, nao autoridade de execucao
- seletores, cliques e persistencia continuam deterministicos
- submit real continua bloqueado por autorizacao humana explicita
- respostas da LLM devem ser estruturadas e validadas antes de uso
- se a LLM falhar, o fluxo volta para comportamento conservador

## Fases

### Fase 1 - Snapshot estruturado do modal

Objetivo:
- registrar um snapshot textual e estrutural da etapa atual do modal

Definicao de pronto:
- o inspetor gera um payload com campos, botoes, texto principal e sinais de etapa
- o snapshot pode ser usado sem depender do DOM bruto inteiro

### Fase 2 - Classificacao assistida da etapa

Objetivo:
- usar a LLM local para classificar a etapa atual do modal

Definicao de pronto:
- a LLM retorna apenas JSON
- a resposta inclui pelo menos:
  - `step_type`
  - `recommended_action`
  - `confidence`
  - `rationale`
- existe fallback deterministico quando a resposta for invalida

### Fase 3 - Guardrails de execucao

Objetivo:
- garantir que a sugestao da LLM so influencie o fluxo quando passar em regras duras

Definicao de pronto:
- a execucao so aceita acoes coerentes com os sinais reais do modal
- a LLM nao pode forcar submit sem botao final visivel
- a LLM nao pode preencher campos ambiguos sem validacao adicional

### Fase 4 - Integracao no preflight

Objetivo:
- anexar a interpretacao assistida da LLM ao preflight real do LinkedIn

Definicao de pronto:
- o detalhe do preflight inclui a classificacao da etapa quando disponivel
- falhas da LLM nao quebram o preflight

### Fase 5 - Integracao no submit real

Objetivo:
- usar a interpretacao assistida para decidir o proximo passo quando o modal variar entre vagas

Definicao de pronto:
- o submit real consulta a interpretacao da etapa antes de desistir
- a execucao continua deterministica e auditavel
- o bloqueio final fica mais explicito quando a LLM nao ajudar

## Regras

- nao remover os guardrails atuais do submit
- nao permitir que a LLM clique arbitrariamente em qualquer botao
- nao substituir seletores confiaveis por heuristica da LLM
- manter logs suficientes para comparar:
  - snapshot real
  - classificacao da LLM
  - acao realmente executada

## Checklist

- [x] Fase 1 concluida
- [x] Fase 2 concluida
- [ ] Fase 3 concluida
- [ ] Fase 4 concluida
- [ ] Fase 5 concluida
- [ ] README atualizado se o fluxo operacional mudar
- [ ] AGENTS reavaliado ao fim desta trilha

## Validacao esperada

- testes unitarios do parser e da classificacao da LLM
- testes de fallback conservador
- validacao real em preflight antes de qualquer novo submit real
- validacao real em submit assistido apenas depois dos guardrails estarem fechados
