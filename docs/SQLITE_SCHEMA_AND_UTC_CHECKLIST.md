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
- [x] Cobrir helper com testes de banco vazio.
- [x] Cobrir helper com testes de banco legado sem tabela de versao.
- [x] Cobrir execucao idempotente de migracoes.
- [ ] Integrar `run_sqlite_migrations` no startup do `SqliteJobRepository`.
- [ ] Mover migracoes ad-hoc de `job_applications` para migracoes versionadas.
- [ ] Padronizar writes restantes que ainda usam `datetime.now().isoformat(...)` para `_utc_now_iso()`.
- [ ] Padronizar writes SQL restantes que ainda usam `CURRENT_TIMESTAMP` quando forem tocados por migracoes futuras.
- [ ] Validar suite completa em CI.

## Migracoes SQLite

Arquivo principal:

```text
job_hunter_agent/infrastructure/sqlite_migrations.py
```

Responsabilidades:

- criar `schema_migrations` se ela nao existir;
- aplicar migracoes pendentes em ordem crescente de versao;
- registrar cada migracao aplicada com timestamp UTC explicito;
- permitir execucao segura em bancos novos e bancos legados.

A versao `1` representa o baseline do schema existente antes do rastreamento formal de migracoes.

## Integracao Pendende No Repositorio

O proximo passo deve chamar o helper durante o startup do repositorio SQLite.

Destino esperado:

```text
SqliteJobRepository.__init__
```

Fluxo recomendado:

```text
_create_tables()
run_sqlite_migrations(connection)
```

Ou equivalente, desde que:

- bancos novos criem as tabelas atuais e registrem a versao baseline;
- bancos legados preservem dados existentes;
- a execucao repetida nao duplique linhas em `schema_migrations`;
- a tabela `schema_migrations` fique disponivel apos inicializacao do repositorio.

## UTC Explicito

Padrao recomendado para writes novos de timestamp:

```python
datetime.now(timezone.utc).isoformat(timespec="seconds")
```

Ou o helper ja existente:

```python
SqliteJobRepository._utc_now_iso()
```

Criterio esperado:

- novos timestamps gerados pela aplicacao devem conter `+00:00`;
- migracoes devem registrar `applied_at` com `+00:00`;
- comparacoes operacionais devem continuar aceitando dados antigos que nao tenham offset.

## Pontos Conhecidos Para Revisao

Procurar ocorrencias de:

```bash
grep -R "datetime.now().isoformat" -n job_hunter_agent tests
grep -R "CURRENT_TIMESTAMP" -n job_hunter_agent tests
```

Ajustar apenas quando houver teste cobrindo o comportamento, para evitar migracao massiva sem necessidade.

## Criterio De Conclusao Da Issue #34

A issue pode ser fechada quando:

- `SqliteJobRepository` registra a versao baseline em bancos novos;
- bancos legados sem `schema_migrations` recebem a tabela e preservam dados;
- novos writes operacionais alterados nesta frente usam UTC explicito;
- testes cobrem banco vazio, banco legado e idempotencia;
- esta checklist reflete o estado final.
