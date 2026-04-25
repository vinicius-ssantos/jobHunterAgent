# Event-driven workers: checklist incremental

## Contexto

A evolucao para microservicos deve ser incremental. O caminho recomendado e primeiro consolidar workers event-driven dentro do mesmo repositorio, com contratos versionados e fila local substituivel.

## Principios

- preservar o loop principal atual
- nao quebrar a CLI existente
- manter SQLite/local-first no inicio
- explicitar contratos antes de trocar infraestrutura
- manter revisao humana e autorizacao explicita antes de submissao real

## Fase 0 — Preparacao segura

- [x] abrir branch dedicada `refactor/event-driven-workers`
- [x] registrar plano incremental em checklist propria
- [ ] atualizar documento antigo de arquitetura para remover marcacoes prematuras de conclusao
- [ ] documentar o estado atual dos workers existentes

## Fase 1 — Contratos e EventBus local

- [ ] mover eventos versionados para `job_hunter_agent/core/events.py`
- [ ] criar porta `EventBusPort`
- [ ] criar implementacao local em memoria para o orquestrador atual
- [ ] criar helpers NDJSON reutilizaveis pelos workers de CLI
- [ ] preservar compatibilidade com o formato NDJSON atual
- [ ] adicionar testes dos contratos e serializacao local

## Fase 2 — Workers como processos locais confiaveis

- [ ] revisar `collector_worker` para publicar via contrato/event bus
- [ ] revisar `matching_worker` para consumir contrato versionado e manter idempotencia
- [ ] criar worker de review/notificacao consumindo eventos
- [ ] padronizar DLQ por tipo de worker e evento
- [ ] padronizar metadados: `event_id`, `event_type`, `schema_version`, `created_at_utc`, `run_id`
- [ ] adicionar comandos CLI de replay e inspect de eventos locais

## Fase 3 — Observabilidade e operacao local

- [ ] adicionar resumo por etapa
- [ ] adicionar correlacao por `run_id`
- [ ] adicionar health check dos arquivos/fila local
- [ ] documentar runbook de recuperacao de DLQ

## Fase 4 — Containerizacao

- [ ] adicionar Dockerfile de runtime
- [ ] adicionar docker-compose local com perfis para `collector`, `matching`, `bot` e `scheduler`
- [ ] manter volume local para SQLite/logs/browser state

## Fase 5 — Fila real opcional

- [ ] criar implementacao `RedisStreamEventBus` ou equivalente
- [ ] manter NDJSON/local como fallback de desenvolvimento
- [ ] adicionar testes de contrato para ambas implementacoes

## Fase 6 — Decisao sobre repos separados

So considerar repos separados se houver evidencia operacional: escala independente, multiplos ambientes, multiplos usuarios ou necessidade real de deploy isolado.
