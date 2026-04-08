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

## Checklist por fase

### Fase 1 - Snapshot estruturado do modal

- [x] Registrar um snapshot textual e estrutural da etapa atual do modal
- [x] O inspetor gera payload com campos, botoes, texto principal e sinais de etapa
- [x] O snapshot pode ser usado sem depender do DOM bruto inteiro

### Fase 2 - Classificacao assistida da etapa

- [x] Usar a LLM local para classificar a etapa atual do modal
- [x] A LLM retorna apenas JSON
- [x] A resposta inclui pelo menos `step_type`, `recommended_action`, `confidence` e `rationale`
- [x] Existe fallback deterministico quando a resposta for invalida

### Fase 3 - Guardrails de execucao

- [x] Garantir que a sugestao da LLM so influencie o fluxo quando passar em regras duras
- [x] A execucao so aceita acoes coerentes com os sinais reais do modal
- [x] A LLM nao pode forcar submit sem botao final visivel
- [x] A LLM nao pode preencher campos ambiguos sem validacao adicional

### Fase 4 - Integracao no preflight

- [x] Anexar a interpretacao assistida da LLM ao preflight real do LinkedIn
- [x] O detalhe do preflight inclui a classificacao da etapa quando disponivel
- [x] Falhas da LLM nao quebram o preflight

### Fase 5 - Integracao no submit real

- [x] Usar a interpretacao assistida para decidir o proximo passo quando o modal variar entre vagas
- [x] O submit real consulta a interpretacao da etapa antes de desistir
- [x] A execucao continua deterministica e auditavel
- [x] O bloqueio final fica mais explicito quando a LLM nao ajudar

### Fase 6 - Liveness e prontidao da vaga

- [x] Validar que a pagina aberta realmente corresponde a vaga autorizada e ainda esta apta para candidatura
- [x] O fluxo distingue vaga-alvo, listagem/colecao, vaga expirada e ausencia de CTA
- [x] Preflight e submit falham cedo com motivo explicito quando a pagina estiver errada
- [x] Artefatos locais ajudam a diagnosticar o estado da pagina errada

### Fase 7 - Prontidao operacional antes do submit

- [x] Bloquear o envio real quando faltarem prerequisitos locais do candidato
- [x] O submit verifica storage state, curriculo e dados de contato antes de abrir o applicant
- [x] Falhas de configuracao nao degradam a candidatura para `error_submit`
- [x] O Telegram recebe um bloqueio curto e rastreavel

### Fase 8 - Capacidades explicitas do LinkedIn

- [x] Tornar explicito no codigo o que o portal suporta em coleta, preflight, submit e artefatos
- [x] Preflight e submit consultam capacidades do portal
- [x] Portais sem suporte falham com mensagem operacional estreita
- [x] O fluxo deixa de depender de condicionais espalhadas e implicitas

### Fase 9 - Perguntas obrigatorias seguras

- [x] Separar campos obrigatorios de contato de perguntas adicionais reais
- [x] Registrar perguntas adicionais estruturadas no snapshot e nos artefatos de falha
- [x] Responder automaticamente apenas perguntas seguras baseadas em politica local explicita
- [x] Bloquear perguntas ambiguas ou sensiveis em `manual_review` com motivo curto
- [ ] Validar submit real fim a fim em uma vaga `Easy Apply` ainda aberta

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
- [x] Fase 3 concluida
- [x] Fase 4 concluida
- [x] Fase 5 concluida
- [x] Fase 6 concluida
- [x] Fase 7 concluida
- [x] Fase 8 concluida
- [ ] Fase 9 concluida
- [x] README atualizado se o fluxo operacional mudar
- [x] AGENTS reavaliado ao fim desta trilha

## Validacao esperada

- testes unitarios do parser e da classificacao da LLM
- testes de fallback conservador
- validacao real em preflight antes de qualquer novo submit real
- validacao real em submit assistido apenas depois dos guardrails estarem fechados
