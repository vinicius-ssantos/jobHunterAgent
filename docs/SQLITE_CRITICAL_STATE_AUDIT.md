# SQLite Critical State Audit

## Objetivo

Auditar se a persistencia SQLite atual registra os estados necessarios para deduplicacao, historico, auditoria e revisao humana na v1.

Este documento atende a issue #67 e e intencionalmente documental: nao altera schema, runtime ou migrations.

## Fontes Auditadas

- `job_hunter_agent/infrastructure/repository.py`
- `job_hunter_agent/core/domain.py`
- `docs/SQLITE_SCHEMA_AND_UTC_CHECKLIST.md`
- `docs/V1_HARDENING_CHECKLIST.md`
- `docs/APPLICATION_OPERATIONS.md`

## Resumo Executivo

O SQLite cobre os estados criticos da v1 para:

- vagas coletadas e revisadas;
- deduplicacao por `url` e `external_key`;
- rastreio de vagas vistas mesmo quando nao persistidas como vagas aceitas;
- candidaturas e gates humanos;
- eventos de status de vaga;
- eventos de candidatura;
- logs e runs de coleta;
- cursores de coleta;
- versionamento baseline de schema via `schema_migrations`.

Nao ha necessidade de migracao obrigatoria para considerar a v1 operacional. Existem, porem, oportunidades futuras de hardening para indices, constraint checks, tabela de artefatos e migracao de ajustes ad-hoc para migrations versionadas.

## Tabelas Atuais E Responsabilidades

### `jobs`

Responsabilidade:

- persistir vagas aceitas/coletadas;
- guardar score e rationale do matching;
- manter status de revisao humana da vaga.

Campos criticos:

- `id`;
- `title`;
- `company`;
- `url`;
- `source_site`;
- `relevance`;
- `rationale`;
- `external_key`;
- `status`;
- `created_at`.

Estados validos de vaga:

```text
collected, approved, rejected, error_collect
```

Cobertura:

- [x] status atual da vaga;
- [x] score/rationale persistidos;
- [x] URL unica;
- [x] chave externa persistida;
- [x] timestamp de criacao.

Observacoes:

- `url` tem constraint `UNIQUE`;
- `external_key` e usado para busca/deduplicacao, mas nao tem constraint unica propria;
- isso e aceitavel porque URLs canonicas podem variar por portal e a estrategia `PortalAwareJobIdentityStrategy` complementa a busca.

### `seen_jobs`

Responsabilidade:

- registrar vagas ja vistas;
- evitar repeticao de coleta/processamento;
- preservar motivo e fonte.

Campos criticos:

- `url`;
- `external_key`;
- `source_site`;
- `reason`;
- `first_seen_at`;
- `last_seen_at`.

Cobertura:

- [x] deduplicacao por URL;
- [x] registro de fonte;
- [x] registro de motivo;
- [x] atualizacao de ultimo avistamento.

Observacoes:

- `url` tem constraint `UNIQUE`;
- `external_key` nao e unico;
- `last_seen_at` e atualizado em conflito por URL.

### `job_status_events`

Responsabilidade:

- auditar transicoes e reafirmacoes de status de vagas.

Campos criticos:

- `job_id`;
- `event_type`;
- `detail`;
- `from_status`;
- `to_status`;
- `created_at`.

Cobertura:

- [x] historico de revisao de vaga;
- [x] status anterior e novo;
- [x] detalhe operacional;
- [x] ordenacao por `id`/tempo.

Observacoes:

- eventos SQLite continuam sendo fonte local principal para historico de vaga;
- domain-events sao complementares quando habilitados.

### `job_applications`

Responsabilidade:

- persistir candidatura por vaga;
- guardar estado atual do fluxo assistido;
- guardar suporte operacional, diagnostico e detalhes recentes de preflight/submit/erro.

Campos criticos:

- `id`;
- `job_id`;
- `status`;
- `support_level`;
- `support_rationale`;
- `notes`;
- `last_preflight_detail`;
- `last_submit_detail`;
- `last_error`;
- `submitted_at`;
- `created_at`;
- `updated_at`.

Estados validos de candidatura:

```text
draft, ready_for_review, confirmed, authorized_submit, submitted, error_submit, cancelled
```

Niveis validos de suporte:

```text
auto_supported, manual_review, unsupported
```

Cobertura:

- [x] uma candidatura por vaga via `job_id UNIQUE`;
- [x] estado atual da candidatura;
- [x] gate explicito `authorized_submit`;
- [x] suporte operacional do portal;
- [x] ultimos detalhes de preflight, submit e erro;
- [x] timestamp de submit real quando aplicavel;
- [x] timestamps de criacao e atualizacao.

Observacoes:

- a constraint `job_id UNIQUE` evita candidaturas duplicadas para a mesma vaga;
- o campo `authorized_submit` como status separado e o principal gate persistido para submit real;
- detalhes historicos completos ficam em `job_application_events`, enquanto campos `last_*` dao diagnostico rapido.

### `job_application_events`

Responsabilidade:

- auditar transicoes e eventos de candidatura.

Campos criticos:

- `application_id`;
- `event_type`;
- `detail`;
- `from_status`;
- `to_status`;
- `created_at`.

Cobertura:

- [x] historico local de candidatura;
- [x] transicoes de status;
- [x] detalhes de eventos operacionais;
- [x] suporte a diagnostico por candidatura.

Observacoes:

- e a principal trilha SQLite para explicar como uma candidatura chegou ao estado atual;
- domain-events por `correlation_id=application:<id>` complementam, mas nao substituem esta tabela.

### `collection_runs`

Responsabilidade:

- registrar execucoes de coleta;
- contar vistos, salvos e erros;
- permitir interrupcao/reconciliacao de runs pendentes.

Campos criticos:

- `started_at`;
- `finished_at`;
- `status`;
- `jobs_seen`;
- `jobs_saved`;
- `errors`.

Cobertura:

- [x] auditoria basica de execucao;
- [x] status de run;
- [x] contadores operacionais.

Observacoes:

- status de run nao tem enum central no dominio;
- isso e aceitavel para v1, mas pode virar contrato explicito se os workers crescerem.

### `collection_logs`

Responsabilidade:

- registrar logs operacionais persistidos por fonte.

Campos criticos:

- `source_site`;
- `level`;
- `message`;
- `created_at`.

Cobertura:

- [x] troubleshooting basico por fonte;
- [x] persistencia de mensagens relevantes.

Observacoes:

- nao substitui logging do processo;
- deve evitar segredos e dados sensiveis conforme `docs/DATA_CONTRACT.md`.

### `collection_cursors`

Responsabilidade:

- persistir progresso de paginacao/coleta por fonte e URL de busca.

Campos criticos:

- `source_site`;
- `search_url`;
- `next_page`;
- `updated_at`.

Cobertura:

- [x] cursor por fonte e busca;
- [x] constraint unica por `(source_site, search_url)`;
- [x] atualizacao idempotente por upsert.

Observacoes:

- `next_page` e normalizado para minimo 1 no codigo.

### `schema_migrations`

Responsabilidade:

- registrar baseline e futuras migrations versionadas.

Campos criticos:

- `version`;
- `name`;
- `applied_at_utc`.

Cobertura:

- [x] baseline do schema atual;
- [x] aplicacao idempotente;
- [x] timestamps UTC explicitos.

Observacoes:

- ajustes legados/ad-hoc de `job_applications` ainda existem no bootstrap do repository;
- migracoes futuras devem preferir `schema_migrations.py`.

## Mapa De Deduplicacao

### Vagas Persistidas

Camadas atuais:

1. `jobs.url UNIQUE`;
2. busca por `url` e `external_key`;
3. estrategia `PortalAwareJobIdentityStrategy` para padroes de URL por portal;
4. `seen_jobs` para lembrar vagas vistas.

Status: suficiente para v1.

Risco residual:

- `external_key` sem indice/constraint unica pode permitir duplicatas se URLs diferentes representarem a mesma vaga e a estrategia de identidade nao cobrir o caso.

Acao futura recomendada:

- adicionar indice nao unico para `jobs.external_key` e `seen_jobs.external_key` se houver volume maior;
- avaliar constraint composta por portal/fonte se forem identificadas duplicatas reais.

### Candidaturas

Camada atual:

1. `job_applications.job_id UNIQUE`;
2. `create_application_draft` retorna candidatura existente se ja houver uma para a vaga.

Status: adequado para v1.

Risco residual:

- nao ha conceito de multiplas candidaturas por vaga/fonte/candidato, o que e correto para o MVP local atual.

## Mapa De Auditoria E Historico

### Vaga

Fonte atual:

- estado atual em `jobs.status`;
- historico em `job_status_events`.

Suficiente para responder:

- a vaga foi coletada?
- foi aprovada/rejeitada?
- qual foi a ultima transicao?
- qual detalhe foi registrado?

### Candidatura

Fonte atual:

- estado atual em `job_applications.status`;
- suporte e diagnostico rapido em `job_applications`;
- historico em `job_application_events`.

Suficiente para responder:

- qual e o estado atual?
- houve preflight?
- houve submit?
- houve erro?
- qual foi a ultima transicao?
- existe gate humano antes de submit real?

### Domain Events

Fonte complementar:

- `domain-events` quando habilitado.

Papel:

- trilha adicional e exportavel;
- correlacao por `application:<id>`;
- nao substitui SQLite na v1.

## Estados Criticos Persistidos

| Area | Estado/Dado | Onde fica | Status |
| --- | --- | --- | --- |
| Vaga | status atual | `jobs.status` | Coberto |
| Vaga | score | `jobs.relevance` | Coberto |
| Vaga | explicacao | `jobs.rationale` | Coberto |
| Vaga | historico | `job_status_events` | Coberto |
| Dedup vaga | URL unica | `jobs.url`, `seen_jobs.url` | Coberto |
| Dedup vaga | external key | `jobs.external_key`, `seen_jobs.external_key` | Parcial sem indice/unique |
| Candidatura | uma por vaga | `job_applications.job_id UNIQUE` | Coberto |
| Candidatura | gate de submit | `job_applications.status='authorized_submit'` | Coberto |
| Candidatura | historico | `job_application_events` | Coberto |
| Candidatura | preflight recente | `last_preflight_detail` | Coberto |
| Candidatura | submit recente | `last_submit_detail`, `submitted_at` | Coberto |
| Candidatura | erro recente | `last_error` | Coberto |
| Coleta | execucao | `collection_runs` | Coberto |
| Coleta | logs | `collection_logs` | Coberto |
| Coleta | cursor | `collection_cursors` | Coberto |
| Schema | versao | `schema_migrations` | Coberto |

## Gaps E Melhorias Futuras

### G1. Indices Para Consultas Frequentes

Nao bloqueia v1.

Possiveis indices futuros:

```sql
CREATE INDEX IF NOT EXISTS idx_jobs_external_key ON jobs(external_key);
CREATE INDEX IF NOT EXISTS idx_jobs_status_created_at ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_job_applications_status_updated_at ON job_applications(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_job_application_events_application_id_id ON job_application_events(application_id, id);
CREATE INDEX IF NOT EXISTS idx_job_status_events_job_id_id ON job_status_events(job_id, id);
```

Recomendacao:

- implementar apenas se houver volume ou lentidao observada;
- fazer via migration versionada.

### G2. Migrar Ajustes Ad-Hoc Para Migrations Versionadas

Nao bloqueia v1.

O bootstrap ainda garante colunas legadas de `job_applications` por `ALTER TABLE` direto.

Recomendacao:

- manter enquanto nao houver nova alteracao de schema;
- quando tocar schema novamente, mover esse padrao para `schema_migrations.py`.

### G3. Tabela De Artefatos De Candidatura

Nao bloqueia v1.

Motivacao futura:

- associar relatorios A-F, CVs, cover letters e respostas sugeridas a candidaturas.

Exemplo futuro:

```sql
CREATE TABLE application_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    artifact_type TEXT NOT NULL,
    path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (application_id) REFERENCES job_applications(id)
);
```

Recomendacao:

- criar somente quando a primeira feature de artefato runtime for implementada;
- seguir `docs/DATA_CONTRACT.md`.

### G4. Constraints De Enum No SQLite

Nao bloqueia v1.

Hoje os enums sao validados no dominio/codigo, nao por `CHECK` constraints no banco.

Recomendacao:

- avaliar `CHECK(status IN (...))` em migration futura se houver necessidade de protecao extra contra escrita manual;
- cuidado com bancos legados e compatibilidade.

### G5. Normalizacao Completa De Timestamps Legados

Nao bloqueia v1.

A estrategia ja esta documentada em `docs/SQLITE_LEGACY_TIMESTAMP_MIGRATION_PLAN.md`.

Recomendacao:

- nao converter em massa agora;
- preservar tolerancia a dados antigos;
- converter apenas com backup e migration versionada.

## Conclusao Da Auditoria

A persistencia SQLite atual e suficiente para o MVP local da v1.

Estados criticos de vaga, candidatura, historico, deduplicacao, suporte operacional e diagnostico estao persistidos. A principal recomendacao e nao alterar schema imediatamente; em vez disso, manter os gaps acima como melhorias futuras condicionadas a volume, necessidade de artefatos runtime ou nova mudanca de schema.

## Criterios De Aceite Da Issue #67

- [x] Schema atual revisado.
- [x] Campos obrigatorios para vagas, matches e decisoes mapeados.
- [x] Estrategia de deduplicacao documentada.
- [x] Estados criticos persistidos documentados.
- [x] Gaps e migrations futuras documentados quando aplicavel.
