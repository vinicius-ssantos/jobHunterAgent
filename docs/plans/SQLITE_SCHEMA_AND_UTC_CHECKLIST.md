# SQLite Schema E UTC Checklist

## Objetivo

Planejar a evolucao de schema e timestamps antes de introduzir mais workers independentes ou broker externo.

Esta frente deve ser tratada como etapa propria porque mexe em persistencia existente e pode afetar dados locais do usuario.

## Decisao Para Esta PR

- [x] Nao executar migracao ampla de banco nesta frente de workers.
- [x] Documentar estrategia antes de alterar tabelas existentes.
- [x] Manter novos eventos e DLQ com timestamps UTC.
- [x] Preservar compatibilidade com bancos locais existentes.

## Problema Atual

O repositorio ja usa UTC em alguns pontos operacionais, mas ainda existem timestamps gerados por `CURRENT_TIMESTAMP` do SQLite e chamadas locais de `datetime.now()`.

Para workers separados, isso cria risco de:

- limites diarios inconsistentes
- ordenacao ambigua entre eventos
- dificuldade de correlacionar logs, DLQ e eventos
- migracoes futuras sem controle de versao

## Schema Versionado

Plano recomendado:

- [ ] Criar tabela `schema_migrations` ou `app_metadata`.
- [ ] Registrar versao inicial do schema atual.
- [ ] Criar helper central de migracoes idempotentes.
- [ ] Rodar migracoes no startup do repositorio.
- [ ] Adicionar teste com banco vazio.
- [ ] Adicionar teste com banco legado sem tabela de versao.
- [ ] Documentar rollback manual para banco local.

Sugestao de tabela:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at_utc TEXT NOT NULL
);
```

## Padronizacao UTC

Plano recomendado:

- [ ] Criar helper unico `utc_now_iso()` para persistencia.
- [ ] Trocar usos de `datetime.now().isoformat(...)` por UTC.
- [ ] Evitar `CURRENT_TIMESTAMP` em novas tabelas, preferindo timestamp gerado pela aplicacao.
- [ ] Documentar que timestamps persistidos sao UTC.
- [ ] Converter renderizacao local apenas na borda de UI/CLI/notifier.

## Ordem Segura De Execucao

1. adicionar tabela de schema versionado sem alterar tabelas existentes
2. padronizar novos writes para UTC em codigo
3. adicionar testes de regressao para timestamps com `+00:00`
4. planejar migracao opcional dos campos antigos
5. so depois considerar broker externo ou Postgres

## Fora De Escopo Agora

- converter dados antigos em massa
- trocar SQLite por Postgres
- criar migrations irreversiveis
- alterar sem necessidade os contratos do runtime atual
