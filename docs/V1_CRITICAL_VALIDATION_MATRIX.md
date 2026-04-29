# V1 Critical Validation Matrix

## Objetivo

Mapear a validacao minima dos fluxos criticos da v1 para evitar regressao em matching, persistencia, gates humanos, CLI e CI.

Este documento atende a issue #69 e complementa:

- `docs/V1_HARDENING_CHECKLIST.md`;
- `docs/V1_ROADMAP_MAINTENANCE.md`;
- `docs/TELEGRAM_HUMAN_REVIEW_GATES.md`;
- `docs/SQLITE_CRITICAL_STATE_AUDIT.md`.

## Fonte De Execucao No CI

Workflow principal:

```text
.github/workflows/ci.yml
```

Comando executado:

```bash
pytest
```

Garantia atual:

- CI roda em `push`;
- CI roda em `pull_request`;
- CI pode ser executado manualmente por `workflow_dispatch`;
- falhas em `pytest` impedem considerar o PR pronto para merge.

Workflow complementar:

```text
.github/workflows/docker.yml
```

Papel:

- validar Compose;
- construir imagem Docker;
- executar comando leve de workers.

## Matriz Minima De Fluxos Criticos

| Fluxo | Risco protegido | Cobertura de referencia |
| --- | --- | --- |
| Bootstrap/runtime | App nao inicializa ou injeta dependencias erradas | `tests/test_app_bootstrap.py`, `tests/test_runtime.py`, `tests/test_runtime_execution.py`, `tests/test_runtime_handlers.py` |
| Configuracao | Variaveis invalidas ou fallback indevido | `tests/test_settings.py`, `tests/test_legacy_matching_config.py`, `tests/test_domain_event_bus_config.py`, `tests/test_telegram_notifier_settings.py` |
| Matching | Score/rationale inconsistentes ou prompt quebrado | `tests/test_matching_prompt.py`, `tests/test_matching_worker.py`, `tests/test_runtime_matching.py`, `tests/test_matching_from_legacy_config.py`, `tests/test_matching_seniority_policy.py` |
| Perfil/taxonomia | Perfil ou skills quebram matching | `tests/test_candidate_profile.py`, `tests/test_candidate_profile_extractor.py`, `tests/test_skill_taxonomy.py` |
| Persistencia SQLite | Schema, migrations, UTC ou deduplicacao regressam | `tests/test_schema_migrations.py`, `tests/test_repository_schema_bootstrap.py`, `tests/test_repository_utc_writes.py`, `tests/test_idempotency.py` |
| Domain events | Auditoria complementar deixa de emitir/listar eventos | `tests/test_event_bus.py`, `tests/test_events.py`, `tests/test_domain_events_cli.py`, `tests/test_domain_transition_events.py` |
| Review humana Telegram | Callback aprova/rejeita ou avanca candidatura indevidamente | `tests/test_notifier.py`, `tests/test_notifier_callbacks.py`, `tests/test_telegram_notifier_settings.py` |
| Candidaturas | Gates, estados e comandos de candidatura quebram | `tests/test_application_flow.py`, `tests/test_application_commands.py`, `tests/test_application_cli_parse.py`, `tests/test_application_cli_dispatch.py`, `tests/test_application_cli_rendering.py` |
| Preflight/dry-run | Submit real e dry-run se confundem | `tests/test_application_cli_dry_run.py`, `tests/test_application_dry_run_services.py`, `tests/test_application_readiness.py` |
| Diagnostico operacional | Diagnostico deixa de explicar estado/erro | `tests/test_application_queries_diagnosis.py`, `tests/test_application_diagnosis_rendering.py`, `tests/test_application_health.py`, `tests/test_application_cli_health.py` |
| LinkedIn application flow | Leitura, preflight, submit e artifacts quebram | `tests/test_linkedin_application_review.py`, `tests/test_linkedin_application_submit.py`, `tests/test_linkedin_application_fields.py`, `tests/test_linkedin_application_runtime.py`, `tests/test_linkedin_application_execution.py`, `tests/test_linkedin_application_artifacts.py` |
| Coleta/workers | Workers deixam de carregar ou executar ciclo leve | `tests/test_worker_catalog.py`, `tests/test_worker_runtime.py`, `tests/test_collector_worker.py` |
| Contratos de ports | Interfaces de app quebram substituibilidade | `tests/test_application_ports.py`, `tests/test_composition_injection.py` |

## Validacoes Que Devem Continuar Bloqueando Merge

Um PR nao deve ser mergeado se falhar:

- `pytest` no CI;
- validacao Docker obrigatoria do repo;
- testes de gates humanos;
- testes de schema/migration;
- testes que diferenciam `confirmed` de `authorized_submit`;
- testes de dry-run/submissao real;
- testes de diagnostico de candidatura.

## Comandos Locais Minimos

Antes de abrir PR com mudanca de runtime:

```bash
pytest
```

Antes de mexer em candidatura/submissao:

```bash
pytest tests/test_application_flow.py tests/test_application_readiness.py tests/test_application_cli_dry_run.py tests/test_notifier_callbacks.py
```

Antes de mexer em SQLite/schema:

```bash
pytest tests/test_schema_migrations.py tests/test_repository_schema_bootstrap.py tests/test_repository_utc_writes.py tests/test_idempotency.py
```

Antes de mexer em matching:

```bash
pytest tests/test_matching_prompt.py tests/test_matching_worker.py tests/test_runtime_matching.py tests/test_matching_seniority_policy.py
```

Antes de mexer em domain-events:

```bash
pytest tests/test_event_bus.py tests/test_domain_events_cli.py tests/test_domain_transition_events.py
```

## Gaps Aceitos Para A V1

Nao bloqueiam a v1 neste momento:

- lint/format dedicado fora do `pytest`;
- coverage gate numerico;
- testes end-to-end reais contra portal externo;
- testes com Telegram real;
- browser automation real em CI.

Motivo:

- a v1 prioriza reproducibilidade local, testes unitarios/integrados leves, CI rapido e safety gates;
- integrações externas reais devem permanecer manuais ou cobertas por mocks/fakes ate haver infraestrutura dedicada.

## Melhorias Futuras

Possiveis proximos passos, se o volume de mudancas aumentar:

- adicionar job separado de lint/format;
- marcar testes lentos com `pytest` markers;
- publicar relatorio de coverage;
- separar suites por dominio (`matching`, `applications`, `sqlite`, `telegram`);
- adicionar smoke test CLI para comandos principais;
- tornar obrigatorio rodar subconjuntos especificos por area alterada.

## Criterios De Aceite Da Issue #69

- [x] CI executa em PR via workflow dedicado.
- [x] `pytest` e a validacao minima de testes.
- [x] Fluxos criticos da v1 estao mapeados para testes existentes.
- [x] Falhas criticas de teste devem bloquear merge.
- [x] Gaps aceitos e melhorias futuras estao documentados.
