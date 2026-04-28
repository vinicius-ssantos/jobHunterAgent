# SQLite Schema And UTC Checklist

## Objetivo

Acompanhar a frente de endurecimento da persistencia SQLite antes de novas evolucoes de produto ou broker externo.

Esta checklist cobre dois eixos:

- versionamento idempotente do schema SQLite;
- padronizacao de novos writes operacionais para UTC explicito com `+00:00`.

## Estado Atual

- [x] Criar helper central de migracoes SQLite.
- [x] Criar tabela `schema_migrations` via helper idempotente.
- [x] Registrar versao baseline do schema atual.
- [x] Integrar registro de schema no startup do `SqliteJobRepository` via bootstrap de infraestrutura.
- [x] Consolidar helper duplicado em `schema_migrations.py`.
- [x] Cobrir helper com testes de banco vazio.
- [x] Cobrir helper com testes de banco legado sem tabela de versao.
- [x] Cobrir execucao idempotente de migracoes.
- [x] Cobrir aplicacao ordenada de migracoes pendentes.
- [x] Padronizar novos writes operacionais cobertos nesta frente para UTC explicito.
- [x] Validar suite completa em CI.
- [x] Validar Docker.
- [x] Atualizar checklists ativos ao final.

## Fora Do Escopo Desta Frente

Os pontos abaixo continuam sendo evolucoes futuras e nao bloqueiam a conclusao da issue #34:

- converter dados antigos em massa;
- trocar SQLite por Postgres;
- introduzir broker externo;
- remover todos os defaults antigos com `CURRENT_TIMESTAMP` sem uma migracao segura;
- mover todo ajuste legado/ad-hoc para migracoes versionadas quando houver necessidade real de alterar schema.

## Migracoes SQLite

Arquivo principal:

```text
job_hunter_agent/infrastructure/schema_migrations.py
```

Responsabilidades:

- criar `schema_migrations` se ela nao existir;
- aplicar migracoes pendentes em ordem crescente de versao;
- registrar cada migracao aplicada com timestamp UTC explicito;
- permitir execucao segura em bancos novos e bancos legados.

A versao `1` representa o baseline do schema existente antes do rastreamento formal de migracoes.

## Integracao No Repositorio

A integracao atual ocorre no carregamento do pacote de infraestrutura:

```text
job_hunter_agent/infrastructure/__init__.py
job_hunter_agent/infrastructure/repository_schema_bootstrap.py
```

O bootstrap envolve `_create_tables()` do `SqliteJobRepository` e registra a versao atual apos a criacao/validacao das tabelas existentes.

Requisitos preservados:

- bancos novos criam as tabelas atuais e registram a versao baseline;
- bancos legados preservam dados existentes;
- a execucao repetida nao duplica linhas em `schema_migrations`;
- a tabela `schema_migrations` fica disponivel apos inicializacao do repositorio.

## UTC Explicito

Padrao recomendado para writes novos de timestamp:

```python
datetime.now(timezone.utc).isoformat(timespec="seconds")
```

Ou o helper ja existente:

```python
SqliteJobRepository._utc_now_iso()
```

Writes operacionais cobertos por UTC explicito nesta frente:

- `schema_migrations.applied_at_utc`;
- `jobs.created_at` em novos jobs salvos pela aplicacao;
- `job_status_events.created_at` em novos eventos de vaga;
- `seen_jobs.first_seen_at` e `seen_jobs.last_seen_at` em novos writes da aplicacao;
- `collection_logs.created_at` em novos logs de coleta;
- `collection_cursors.updated_at` em novos writes de cursor;
- `job_applications.created_at` e `job_applications.updated_at` em novos writes de candidatura;
- `job_application_events.created_at` em novos eventos de candidatura.

Criterio esperado:

- novos timestamps gerados pela aplicacao devem conter `+00:00`;
- migracoes devem registrar `applied_at_utc` com `+00:00`;
- comparacoes operacionais devem continuar aceitando dados antigos que nao tenham offset.

## Rollback Manual Para Banco Local

Esta frente nao altera dados antigos em massa. Ainda assim, antes de uma intervencao manual em banco local, faca backup do arquivo SQLite:

```bash
cp jobs.db jobs.db.backup-$(date -u +%Y%m%dT%H%M%SZ)
```

Para voltar ao backup:

```bash
cp jobs.db.backup-<timestamp> jobs.db
```

Se o problema estiver restrito ao registro de versao de schema, inspecione antes de apagar qualquer dado:

```bash
sqlite3 jobs.db "SELECT version, name, applied_at_utc FROM schema_migrations ORDER BY version;"
```

Evite remover linhas de `schema_migrations` manualmente sem tambem entender quais mudancas de schema ja foram aplicadas.

## Pontos Conhecidos Para Revisao Futura

Procurar ocorrencias de:

```bash
grep -R "datetime.now().isoformat" -n job_hunter_agent tests
grep -R "CURRENT_TIMESTAMP" -n job_hunter_agent tests
```

Ajustar apenas quando houver teste cobrindo o comportamento, para evitar migracao massiva sem necessidade.

## Criterio De Conclusao Da Issue #34

- [x] `SqliteJobRepository` registra a versao baseline em bancos novos.
- [x] Bancos legados sem `schema_migrations` recebem a tabela e preservam dados.
- [x] Novos writes operacionais alterados nesta frente usam UTC explicito.
- [x] Testes cobrem banco vazio, banco legado e idempotencia.
- [x] Checklists refletem o que foi concluido.
