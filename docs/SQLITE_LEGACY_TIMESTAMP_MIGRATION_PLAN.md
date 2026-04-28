# SQLite Legacy Timestamp Migration Plan

## Objetivo

Planejar uma migracao futura e opcional de timestamps legados em SQLite para UTC explicito com `+00:00`.

Este documento nao executa migracao, nao altera runtime e nao recomenda conversao em massa imediata.

## Contexto

A frente #34 padronizou novos writes operacionais gerados pela aplicacao para UTC explicito. Ainda podem existir:

- dados historicos gravados antes da padronizacao;
- colunas com valores gerados por defaults antigos de SQLite, como `CURRENT_TIMESTAMP`;
- timestamps sem offset, que devem ser tratados como legados.

Esses dados devem continuar legiveis. Uma migracao so deve acontecer quando houver necessidade operacional clara.

## Principio De Compatibilidade

- Nao reescrever dados antigos sem backup.
- Nao assumir timezone local para todos os registros sem validacao.
- Nao misturar migracao de dados com mudancas de produto.
- Preferir PR dedicado, pequeno e reversivel.
- Manter leitura compatível com timestamps sem offset.

## Campos Candidatos A Revisao

Campos historicamente sensiveis a timestamp:

- `jobs.created_at`;
- `collection_logs.created_at`;
- `collection_runs.started_at`;
- `collection_runs.finished_at`;
- `seen_jobs.first_seen_at`;
- `seen_jobs.last_seen_at`;
- `job_applications.created_at`;
- `job_applications.updated_at`;
- `job_applications.submitted_at`;
- `job_application_events.created_at`;
- `job_status_events.created_at`;
- `collection_cursors.updated_at`;
- `schema_migrations.applied_at_utc`.

`schema_migrations.applied_at_utc` ja deve usar UTC explicito e serve como referencia do formato desejado.

## Diagnostico Antes De Migrar

Contar valores possivelmente legados por coluna usando consultas do tipo:

```sql
SELECT COUNT(*) FROM jobs
WHERE created_at IS NOT NULL
  AND created_at NOT LIKE '%+00:00';
```

Exemplos por tabela:

```sql
SELECT COUNT(*) AS legacy_jobs_created_at
FROM jobs
WHERE created_at IS NOT NULL AND created_at NOT LIKE '%+00:00';

SELECT COUNT(*) AS legacy_application_events_created_at
FROM job_application_events
WHERE created_at IS NOT NULL AND created_at NOT LIKE '%+00:00';

SELECT COUNT(*) AS legacy_job_events_created_at
FROM job_status_events
WHERE created_at IS NOT NULL AND created_at NOT LIKE '%+00:00';

SELECT COUNT(*) AS legacy_seen_jobs_timestamps
FROM seen_jobs
WHERE (first_seen_at IS NOT NULL AND first_seen_at NOT LIKE '%+00:00')
   OR (last_seen_at IS NOT NULL AND last_seen_at NOT LIKE '%+00:00');
```

Antes de converter, coletar amostras:

```sql
SELECT id, created_at
FROM jobs
WHERE created_at IS NOT NULL AND created_at NOT LIKE '%+00:00'
ORDER BY id
LIMIT 20;
```

## Backup Obrigatorio

Antes de qualquer conversao manual ou automatizada:

```bash
cp jobs.db jobs.db.backup-$(date -u +%Y%m%dT%H%M%SZ)
```

Validar que o backup existe:

```bash
ls -lh jobs.db.backup-*
```

Rollback manual:

```bash
cp jobs.db.backup-<timestamp> jobs.db
```

## Estrategia De Conversao Recomendada

Apenas se a equipe decidir converter historico:

1. Criar uma nova migracao versionada em `schema_migrations.py`.
2. Executar apenas em bancos que ainda nao tenham a versao aplicada.
3. Converter em uma transacao SQLite.
4. Adicionar testes com banco legado contendo timestamps sem offset.
5. Validar que dados ja em `+00:00` nao sao alterados.
6. Validar rollback manual com backup local.

Formato alvo:

```text
YYYY-MM-DDTHH:MM:SS+00:00
```

Para valores SQLite legados no formato `YYYY-MM-DD HH:MM:SS`, converter explicitamente para UTC somente se a origem for conhecida como UTC:

```text
YYYY-MM-DD HH:MM:SS -> YYYY-MM-DDTHH:MM:SS+00:00
```

Se a origem nao for confiavel, preferir manter o valor legado e tratar na camada de leitura.

## Condicoes Para Nao Migrar

Nao migrar se:

- houver duvida sobre a timezone original;
- o volume de dados for pequeno e a leitura ja aceitar valores legados;
- nao houver backup validado;
- a mudanca estiver misturada com feature de produto;
- nao houver teste com banco legado.

## Validacao Depois De Migrar

Rodar consultas de contagem novamente:

```sql
SELECT COUNT(*) FROM jobs
WHERE created_at IS NOT NULL
  AND created_at NOT LIKE '%+00:00';
```

Executar suite automatizada:

```bash
pytest
```

Validar Docker quando a mudanca tocar runtime:

```bash
docker compose config
```

## Criterio Para Um PR Futuro

Um PR que execute a migracao deve incluir:

- migracao versionada;
- teste com banco legado;
- teste de idempotencia;
- documentacao de backup/rollback;
- evidência de CI e Docker verdes, se aplicavel.

## Status

Este documento e apenas um plano. A conversao de dados antigos continua fora de escopo ate haver uma necessidade operacional clara.
