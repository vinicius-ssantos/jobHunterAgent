# SQLite Schema E UTC Checklist

## Objetivo

Planejar a evolucao de schema e timestamps antes de introduzir mais workers independentes ou broker externo.

Esta frente deve ser tratada como etapa propria porque mexe em persistencia existente e pode afetar dados locais do usuario.

## Decisao Para Esta Frente

- [x] Nao executar migracao ampla de banco nesta frente.
- [x] Documentar estrategia antes de alterar tabelas existentes.
- [x] Manter novos eventos e DLQ com timestamps UTC.
- [x] Preservar compatibilidade com bancos locais existentes.
- [x] Validar CI e Docker antes de mergear PRs de codigo.

## Problema Atual

O repositorio ja usa UTC em alguns pontos operacionais, mas ainda existem timestamps gerados por `CURRENT_TIMESTAMP` do SQLite e chamadas locais de `datetime.now()` em caminhos legados.

Para workers separados, isso cria risco de:

- limites diarios inconsistentes;
- ordenacao ambigua entre eventos;
- dificuldade de correlacionar logs, DLQ e eventos;
- migracoes futuras sem controle de versao.

## Schema Versionado

Plano recomendado:

- [x] Criar tabela `schema_migrations` ou `app_metadata`.
- [x] Registrar versao inicial do schema atual.
- [x] Criar helper central de migracoes idempotentes.
- [x] Rodar migracoes no startup do repositorio.
- [x] Adicionar teste com banco vazio.
- [x] Adicionar teste com banco legado sem tabela de versao.
- [x] Documentar rollback manual para banco local.

Tabela implementada:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at_utc TEXT NOT NULL
);
```

## Padronizacao UTC

Plano recomendado:

- [x] Criar helper unico `utc_now_iso()` para persistencia.
- [x] Trocar novos writes operacionais cobertos nesta frente para UTC explicito.
- [x] Documentar que timestamps persistidos novos devem ser UTC explicito.
- [ ] Remover dependencias remanescentes de `CURRENT_TIMESTAMP` em definicoes antigas quando houver uma migracao segura de schema.
- [ ] Converter renderizacao local apenas na borda de UI/CLI/notifier.

Writes operacionais cobertos por UTC explicito:

- [x] `schema_migrations.applied_at_utc`
- [x] `jobs.created_at` em novos jobs salvos pela aplicacao
- [x] `job_status_events.created_at` em novos eventos de vaga
- [x] `seen_jobs.first_seen_at` e `seen_jobs.last_seen_at` em novos writes da aplicacao
- [x] `collection_logs.created_at` em novos logs de coleta
- [x] `collection_cursors.updated_at` em novos writes de cursor
- [x] `job_applications.created_at` e `job_applications.updated_at` em novos writes de candidatura
- [x] `job_application_events.created_at` em novos eventos de candidatura

## Rollback Manual Para Banco Local

Antes de qualquer intervencao manual em banco local, faca backup do arquivo SQLite:

```bash
cp jobs.db jobs.db.backup-$(date -u +%Y%m%dT%H%M%SZ)
```

Para voltar ao backup:

```bash
cp jobs.db.backup-<timestamp> jobs.db
```

Para inspecionar as migracoes registradas:

```bash
sqlite3 jobs.db "SELECT version, name, applied_at_utc FROM schema_migrations ORDER BY version;"
```

Nao remova linhas de `schema_migrations` sem entender quais mudancas ja foram aplicadas.

## Ordem Segura De Execucao

1. [x] adicionar tabela de schema versionado sem alterar tabelas existentes
2. [x] padronizar novos writes para UTC em codigo
3. [x] adicionar testes de regressao para timestamps com `+00:00`
4. [ ] planejar migracao opcional dos campos antigos
5. [ ] so depois considerar broker externo ou Postgres

## Fora De Escopo Agora

- converter dados antigos em massa
- trocar SQLite por Postgres
- criar migrations irreversiveis
- alterar sem necessidade os contratos do runtime atual
