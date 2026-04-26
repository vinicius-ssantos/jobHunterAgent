# Domain Events

## Objetivo

`domain-events` registram fatos importantes do dominio em formato estruturado, versionado e legivel por maquina.

Eles complementam o SQLite e os logs, mas nao substituem a fonte de verdade atual do runtime.

Use este recurso para auditoria local, troubleshooting e preparacao gradual para workers mais independentes.

## Quando Habilitar

Por padrao, a publicacao de eventos de dominio fica desligada:

```bash
JOB_HUNTER_DOMAIN_EVENTS_ENABLED=false
```

Habilite temporariamente quando quiser auditar transicoes reais:

```bash
export JOB_HUNTER_DOMAIN_EVENTS_ENABLED=true
export JOB_HUNTER_DOMAIN_EVENTS_PATH=./logs/domain-events.ndjson
```

O arquivo padrao e:

```text
./logs/domain-events.ndjson
```

## Como Inspecionar

Liste eventos recentes:

```bash
python main.py domain-events list --limit 20
```

Ou aponte para um arquivo especifico:

```bash
python main.py domain-events list --path logs/domain-events.ndjson --limit 50
```

Se o arquivo nao existir ou estiver vazio, o comando deve responder que nenhum evento foi encontrado.

## Eventos Ativos

### `JobReviewedV1`

Emitido quando uma vaga muda de status via review.

Exemplo de linha renderizada:

```text
JobReviewedV1 event_id=<uuid> correlation_id=job:238 job_id=238 decision=approve status=approved reviewed_by=command
```

Uso principal:

- auditar aprovacoes/rejeicoes de vagas
- correlacionar review com rascunhos/candidaturas futuras

### `ApplicationAuthorizedV1`

Emitido quando uma candidatura e autorizada para envio.

Exemplo:

```text
ApplicationAuthorizedV1 event_id=<uuid> correlation_id=application:31 application_id=31 job_id=128 authorized_by=command source=manual status=authorized_submit
```

Uso principal:

- auditar gates humanos antes de submit real
- identificar candidaturas que entraram no estado `authorized_submit`

### `ApplicationSubmittedV1`

Emitido quando uma submissao real e concluida.

Exemplo:

```text
ApplicationSubmittedV1 event_id=<uuid> correlation_id=application:31 application_id=31 job_id=128 portal=LinkedIn confirmation=<ref>
```

Uso principal:

- auditar submissao concluida
- registrar referencia externa quando disponivel

### `ApplicationBlockedV1`

Emitido quando o submit real nao avanca por um bloqueio esperado ou erro controlado.

Exemplo:

```text
ApplicationBlockedV1 event_id=<uuid> correlation_id=application:31 application_id=31 job_id=128 reason=preflight_not_ready retryable=True
```

Uso principal:

- diagnosticar por que uma candidatura nao foi enviada
- separar bloqueios retryable de bloqueios finais

## Fluxo De Validacao Manual

### Review De Vaga

```bash
export JOB_HUNTER_DOMAIN_EVENTS_ENABLED=true
export JOB_HUNTER_DOMAIN_EVENTS_PATH=./logs/domain-events.ndjson
python main.py jobs list --status collected
python main.py jobs approve --id <job_id>
python main.py domain-events list --limit 20
```

Esperado:

```text
JobReviewedV1 ... correlation_id=job:<job_id> ... decision=approve ... status=approved
```

### Autorizacao De Candidatura

```bash
python main.py applications list --status confirmed
python main.py applications authorize --id <application_id>
python main.py domain-events list --limit 20
```

Esperado:

```text
ApplicationAuthorizedV1 ... correlation_id=application:<application_id> ... status=authorized_submit
```

### Submit Bloqueado Ou Enviado

```bash
python main.py applications submit --id <application_id>
python main.py domain-events list --limit 20
```

Esperado: um dos eventos abaixo:

```text
ApplicationSubmittedV1
ApplicationBlockedV1
```

`ApplicationBlockedV1` pode ser resultado correto quando algum gate ainda nao permite envio, por exemplo `preflight_not_ready`.

## Regressao Com Eventos Desabilitados

Confirme que o runtime continua funcionando sem exigir arquivo de eventos:

```bash
export JOB_HUNTER_DOMAIN_EVENTS_ENABLED=false
python main.py status
python main.py jobs list --status collected
```

Com eventos desabilitados, comandos operacionais devem continuar funcionando normalmente e nao devem depender de `logs/domain-events.ndjson`.

## Relacao Com SQLite E Logs

- SQLite continua sendo a fonte principal para vagas, candidaturas e status.
- Logs continuam sendo a melhor fonte para debug textual.
- `domain-events` sao uma trilha estruturada opcional para fatos de negocio.

Nao trate o NDJSON como banco principal nem como fonte unica de verdade.

## Troubleshooting

### `Nenhum evento de dominio encontrado`

Verifique:

```bash
echo $JOB_HUNTER_DOMAIN_EVENTS_ENABLED
echo $JOB_HUNTER_DOMAIN_EVENTS_PATH
ls -la logs/
```

Possiveis causas:

- flag nao habilitada
- path diferente do esperado
- nenhuma transicao real executada desde que a flag foi habilitada
- comando executado em outro diretorio de trabalho

### `domain-events.ndjson` nao e criado

Confirme permissao de escrita no diretorio:

```bash
mkdir -p logs
touch logs/domain-events.ndjson
```

Depois rode novamente uma transicao real.

### Evento esperado nao aparece

Confirme se a transicao realmente mudou estado.

Exemplo: aprovar uma vaga ja aprovada pode ser ignorado e nao publicar novo evento.

### `ApplicationBlockedV1` apareceu no submit

Isso nem sempre e erro. Pode indicar bloqueio seguro esperado, como:

- `preflight_not_ready`
- `portal_not_supported`
- `readiness_incomplete`
- `submit_unavailable`
- `applicant_error`

Verifique `reason`, `detail` e `retryable`.

## Escopo Atual

Ativos hoje:

- `JobReviewedV1`
- `ApplicationAuthorizedV1`
- `ApplicationSubmittedV1`
- `ApplicationBlockedV1`

Candidatos futuros:

- `ApplicationDraftCreatedV1`
- `ApplicationPreflightCompletedV1`
- `JobPersistedV1`

Nao adicionar novos eventos sem valor operacional claro.

## Broker Externo

Nao ha broker externo nesta fase.

O transporte local continua sendo NDJSON via `LocalNdjsonEventBus`.

Considere Redis, RabbitMQ ou NATS apenas se surgir uma dor concreta:

- multiplos consumidores concorrentes
- retries persistentes alem do NDJSON
- workers em maquinas diferentes
- necessidade real de dead-letter por fila
