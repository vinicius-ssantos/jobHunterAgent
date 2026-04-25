# Event Driven Storage Ownership

## Objetivo

Definir ownership minimo de escrita antes de evoluir os workers para filas externas ou processos mais independentes.

Esta decisao evita que multiplos workers passem a escrever nas mesmas tabelas sem contrato, o que dificultaria idempotencia, retries e troubleshooting.

## Principios

- cada tabela deve ter um owner operacional claro
- cada transicao deve ter uma chave idempotente previsivel
- workers podem ler dados compartilhados, mas escrita deve ser deliberada
- eventos publicados devem carregar `event_id`, `event_type`, `event_version` e `correlation_id`
- reprocessar o mesmo evento nao deve duplicar vagas, candidaturas ou eventos derivados

## Ownership Inicial

| Recurso | Owner Primario | Escritores Permitidos | Observacao |
| --- | --- | --- | --- |
| `jobs` | repository/runtime de coleta | collector/runtime atual | Escrita de vaga persistida continua protegida por URL/external_key. |
| `seen_jobs` | collector/runtime de coleta | collector/runtime atual | Usado para evitar reprocessamento de vagas descartadas. |
| `collection_runs` | scheduler/collector | runtime atual, collector-worker | Cada ciclo deve abrir e fechar exatamente um run. |
| `collection_logs` | collector/runtime | collector/runtime atual | Logs de portal e resumo operacional. |
| `collection_cursors` | collector | coletor especifico de portal | Cursor pertence a fonte/portal. |
| `job_applications` | application-worker | comandos de candidatura, auto-apply | Nao deve ser alterado por collector/matching. |
| `job_application_events` | application-worker | comandos de candidatura, preflight, submit | Eventos de candidatura acompanham transicoes de status. |
| `job_status_events` | review-worker | comandos de revisao | Eventos de vaga acompanham approve/reject/coleta. |
| `worker state` | worker dono | worker especifico | Estado local de idempotencia por worker. |
| NDJSON/event bus local | producer do evento | workers produtores | Transporte local ate existir broker externo. |

## Eventos E Owners

| Evento | Producer | Consumer Inicial | Chave Idempotente Sugerida |
| --- | --- | --- | --- |
| `JobCollectedV1` | collector-worker | matching-worker, review-notifier futuro | `JobCollectedV1:v1:<event_id>` |
| `JobScoredV1` | matching-worker | persistencia/review futuro | `JobScoredV1:v1:<external_key>` |
| `JobReviewRequestedV1` | review-notifier-worker | Telegram/UI futura | `JobReviewRequestedV1:v1:<job_id>` |
| `JobReviewedV1` | Telegram/UI/comando review | application-worker futuro | `JobReviewedV1:v1:<job_id>:<status>` |
| `ApplicationDraftCreatedV1` | application-worker | notifier/UI futura | `ApplicationDraftCreatedV1:v1:<application_id>` |
| `ApplicationAuthorizedV1` | review/application command | application-worker | `ApplicationAuthorizedV1:v1:<application_id>` |
| `ApplicationSubmittedV1` | application-worker | summary/notifier | `ApplicationSubmittedV1:v1:<application_id>` |
| `ApplicationBlockedV1` | application-worker | summary/notifier | `ApplicationBlockedV1:v1:<application_id>:<reason>` |

## Estado Local De Idempotencia

O `matching-worker` usa hoje `worker-match-state.json` com `processed_event_ids`.

A chave inicial para scoring e:

```text
JobScoring:v1:run_id=<run_id>:external_key=<external_key>
```

Essa chave e deliberadamente derivada do assunto processado, nao do `event_id`, porque reemitir o mesmo run/job com outro `event_id` nao deve gerar score duplicado.

## Regras Para Proximas Mudancas

- novo worker deve declarar owner, eventos consumidos e eventos publicados
- nova escrita em tabela existente deve justificar owner ou passar por servico owner
- nova chave de idempotencia deve ter teste unitario
- retry deve ser seguro para executar a mesma mensagem mais de uma vez
- DLQ deve registrar payload original e erro padronizado

## Fora De Escopo Agora

- criar tabela generica de eventos no SQLite
- migrar para Postgres
- trocar NDJSON por broker externo
- tornar todos os eventos de candidatura obrigatorios no runtime atual
