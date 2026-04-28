# Plano De Migracao Opcional De Timestamps SQLite Legados

## Objetivo

Documentar uma estrategia segura para uma migracao futura de timestamps SQLite historicos que foram gravados sem offset explicito ou por `CURRENT_TIMESTAMP`.

Este plano e intencionalmente documental. Ele nao executa conversao de dados, nao altera runtime e nao muda schema nesta etapa.

## Contexto

A frente SQLite/UTC concluiu que novos writes operacionais cobertos devem gravar timestamps UTC explicitos com `+00:00`.

Ainda podem existir:

- registros historicos gravados antes dessa padronizacao;
- defaults antigos de tabelas usando `CURRENT_TIMESTAMP` como fallback;
- bancos locais de usuarios com dados mistos.

A existencia de dados mistos e aceitavel enquanto o codigo continuar tolerando timestamps antigos sem offset.

## Campos Candidatos Para Revisao Futura

Campos que podem conter timestamps legados, dependendo da origem do banco local:

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

`schema_migrations.applied_at_utc` ja deve nascer com UTC explicito. Se aparecer sem offset, trate como anomalia operacional.

## Pre-Condicoes De Seguranca

Antes de qualquer PR que converta dados existentes:

- ter backup manual documentado e testado;
- ter queries de diagnostico antes/depois;
- garantir que o parser de timestamps aceita tanto formato legado quanto UTC explicito;
- executar a migracao em banco de teste com dados mistos;
- manter a migracao idempotente;
- nao converter timestamps que ja tenham offset;
- nao inferir timezone local do usuario sem decisao explicita.

## Backup Manual

Antes de qualquer conversao local:

```bash
cp jobs.db jobs.db.backup-$(date -u +%Y%m%dT%H%M%SZ)
```

Para restaurar:

```bash
cp jobs.db.backup-<timestamp> jobs.db
```

Confirme que o arquivo restaurado abre corretamente:

```bash
sqlite3 jobs.db "SELECT COUNT(*) FROM jobs;"
```

## Diagnostico Antes Da Conversao

Listar amostras de timestamps sem offset aparente:

```bash
sqlite3 jobs.db "SELECT id, created_at FROM jobs WHERE created_at NOT LIKE '%+00:00' LIMIT 20;"
sqlite3 jobs.db "SELECT id, created_at FROM job_status_events WHERE created_at NOT LIKE '%+00:00' LIMIT 20;"
sqlite3 jobs.db "SELECT id, created_at FROM job_application_events WHERE created_at NOT LIKE '%+00:00' LIMIT 20;"
sqlite3 jobs.db "SELECT id, created_at, updated_at, submitted_at FROM job_applications LIMIT 20;"
```

Contar volume por tabela antes de qualquer alteracao:

```bash
sqlite3 jobs.db "SELECT COUNT(*) FROM jobs WHERE created_at NOT LIKE '%+00:00';"
sqlite3 jobs.db "SELECT COUNT(*) FROM job_status_events WHERE created_at NOT LIKE '%+00:00';"
sqlite3 jobs.db "SELECT COUNT(*) FROM job_application_events WHERE created_at NOT LIKE '%+00:00';"
```

## Estrategia Recomendada De Conversao

Se uma migracao futura for aprovada, preferir uma abordagem conservadora:

1. Criar nova migracao versionada em `schema_migrations.py`.
2. Converter apenas valores que correspondam claramente ao formato SQLite legado UTC, por exemplo `YYYY-MM-DD HH:MM:SS`.
3. Transformar para ISO UTC explicito, por exemplo `YYYY-MM-DDTHH:MM:SS+00:00`.
4. Ignorar valores vazios ou nulos.
5. Ignorar valores que ja tenham offset.
6. Registrar a migracao em `schema_migrations`.
7. Cobrir com teste de banco legado contendo dados mistos.

Nao usar timezone local como fallback automatico. Os timestamps legados vindos de `CURRENT_TIMESTAMP` do SQLite devem ser tratados como UTC.

## Diagnostico Depois Da Conversao

Rodar contagens novamente:

```bash
sqlite3 jobs.db "SELECT COUNT(*) FROM jobs WHERE created_at NOT LIKE '%+00:00';"
sqlite3 jobs.db "SELECT COUNT(*) FROM job_status_events WHERE created_at NOT LIKE '%+00:00';"
sqlite3 jobs.db "SELECT COUNT(*) FROM job_application_events WHERE created_at NOT LIKE '%+00:00';"
```

Inspecionar `schema_migrations`:

```bash
sqlite3 jobs.db "SELECT version, name, applied_at_utc FROM schema_migrations ORDER BY version;"
```

Executar comandos leves da aplicacao:

```bash
python main.py status
python main.py jobs list --status collected
python main.py applications list --status draft
```

## Rollback

Se a conversao causar problema, restaurar o backup criado antes da migracao:

```bash
cp jobs.db.backup-<timestamp> jobs.db
```

Depois validar:

```bash
sqlite3 jobs.db "SELECT COUNT(*) FROM jobs;"
python main.py status
```

## Fora De Escopo Deste Plano

- executar a migracao agora;
- converter dados sem backup;
- trocar SQLite por Postgres;
- introduzir broker externo;
- remover defaults antigos sem uma migracao versionada e testada.
