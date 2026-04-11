# Arquitetura do Projeto

## Visao Geral

O `jobHunterAgent` e uma aplicacao local-first para coleta, triagem, revisao e candidatura assistida a vagas.
O desenho atual prioriza:

- fluxo principal estreito e rastreavel
- gate humano antes de qualquer acao de alto impacto
- separacao entre dominio, orquestracao, adaptadores de portal, persistencia e apoio com LLM

Fluxo principal:

`coletar -> normalizar -> ranquear -> persistir -> notificar -> revisar`

Fluxo de candidatura:

`draft -> ready_for_review -> confirmed -> authorized_submit -> submitted`

## Entrypoints

- `main.py`
  entrypoint fino; apenas delega para `job_hunter_agent.run()`
- `job_hunter_agent/application/application_cli.py`
  interface operacional principal via CLI
- `job_hunter_agent/application/app.py`
  fachada de alto nivel da aplicacao; coordena ciclos, comandos, notificacao e casos de uso

## Camadas

### `job_hunter_agent/core/`

Responsabilidades:

- modelos e estados do dominio
- settings validados
- identidade/deduplicacao de vaga
- matching criteria e policy
- runtime guard e suporte de browser
- perfil estruturado do candidato

Esta camada nao deve depender de infraestrutura.

### `job_hunter_agent/application/`

Responsabilidades:

- composicao das dependencias
- casos de uso de candidatura
- comandos de revisao e transicao
- consultas operacionais
- CLI dispatch e rendering
- mensagens operacionais

Modulos centrais:

- `app.py`
- `composition.py`
- `application_preparation.py`
- `application_preflight.py`
- `application_submission.py`
- `application_commands.py`
- `application_queries.py`
- `application_cli.py`

### `job_hunter_agent/collectors/`

Responsabilidades:

- coleta por portal
- normalizacao de vagas
- adaptadores de navegacao
- automacao do LinkedIn
- interpretacao operacional do fluxo Easy Apply

Modulos centrais:

- `collector.py`
- `linkedin.py`
- `linkedin_application.py`
- `linkedin_application_opening.py`
- `linkedin_application_execution.py`
- `linkedin_application_entry_strategies.py`
- `linkedin_application_review.py`
- `linkedin_application_artifacts.py`

### `job_hunter_agent/infrastructure/`

Responsabilidades:

- persistencia SQLite
- historico de eventos
- notificacao Telegram
- rendering de fila e callbacks

Modulos centrais:

- `repository.py`
- `notifier.py`
- `notifier_callbacks.py`
- `notifier_rendering.py`

### `job_hunter_agent/llm/`

Responsabilidades:

- scoring assistivo
- extracao de requisitos
- rationale de revisao
- priorizacao operacional
- interpretacao assistida de modal
- sugestao de perfil do candidato a partir do curriculo

Regras:

- sempre com fallback conservador quando aplicavel
- nunca como fonte unica de verdade para transicoes criticas

## Composicao de Dependencias

O wiring acontece em `job_hunter_agent/application/composition.py`.

Factories principais:

- `create_repository()`
- `create_runtime_guard()`
- `create_collection_service()`
- `create_application_preparation_service()`
- `create_application_preflight_service()`
- `create_application_submission_service()`
- `create_notifier()`

Esse modulo conecta:

- `Settings` validados
- repositorio SQLite
- coletor/score
- fluxo de candidatura do LinkedIn
- notifier Telegram
- componentes opcionais de LLM

## Desenho Operacional

### Coleta

`JobHunterApplication.run_collection_cycle()`:

1. abre um `collection_run`
2. executa `JobCollectionService.collect_new_jobs_report()`
3. coleta vagas por portal habilitado
4. remove duplicatas conhecidas
5. aplica prefiltro deterministico
6. aplica scorer hibrido
7. persiste novas vagas
8. notifica vagas para revisao humana

### Revisao

A revisao humana acontece por CLI ou Telegram.

Transicoes de vaga:

- `collected -> approved`
- `collected -> rejected`

Ao aprovar uma vaga, a aplicacao pode gerar um rascunho de candidatura associado.

### Candidatura

Casos de uso principais:

- `ApplicationPreparationService`
  cria e prepara rascunhos
- `ApplicationPreflightService`
  executa preflight real no LinkedIn sem submit
- `ApplicationSubmissionService`
  executa submit real somente a partir de `authorized_submit`

Regras importantes:

- preflight nao pode pular o gate humano
- submit real depende de readiness check e de autorizacao explicita
- falhas relevantes podem gerar artefatos para depuracao

## Persistencia

O repositorio ativo e `SqliteJobRepository`.

Entidades persistidas principais:

- `jobs`
- `job_status_events`
- `seen_jobs`
- `collection_runs`
- `job_applications`
- `job_application_events`
- `collection_logs`
- `collection_cursors`

Objetivos da camada:

- encapsular SQL
- expor contratos semanticamente estreitos
- oferecer consultas operacionais prontas para CLI/Telegram
- evitar parsing de texto livre para operar o fluxo

## Estados Oficiais

### Vagas

- `collected`
- `approved`
- `rejected`
- `error_collect`

### Candidaturas

- `draft`
- `ready_for_review`
- `confirmed`
- `authorized_submit`
- `submitted`
- `error_submit`
- `cancelled`

## Interfaces de Operacao

### CLI

Interface operacional principal.

Responsavel por:

- status geral
- revisao de vagas
- criacao e transicao de candidaturas
- preflight
- autorizacao de submit
- submit real
- inspecao de eventos e artefatos
- sugestao de perfil estruturado do candidato

### Telegram

Interface de revisao assincrona opcional.

Responsavel por:

- notificar vagas para revisao
- receber callbacks de aprovacao/rejeicao
- disparar operacoes curtas e rastreaveis

As regras de negocio de callback foram extraidas para `notifier_callbacks.py`, reduzindo acoplamento com o transporte.

## LinkedIn: Subdesenho

O modulo de LinkedIn foi quebrado em componentes menores para separar leitura, abertura de fluxo, execucao e deteccao de review final.

Partes principais:

- `linkedin_application.py`
  fachada do inspector/applicant
- `linkedin_application_opening.py`
  coordenacao de abertura do fluxo apply
- `linkedin_application_entry_strategies.py`
  estrategias de entrada, inclusive via URL direta
- `linkedin_application_execution.py`
  execucao do fluxo Easy Apply
- `linkedin_application_review.py`
  deteccao de review final e submit visivel
- `linkedin_application_artifacts.py`
  captura de artefatos em falhas

Regra arquitetural:

- decisao de estado e casos de uso vivem fora do adaptador Playwright
- o adaptador do portal deve ficar focado em navegacao, leitura e acao no portal

## LLMs no Sistema

Uso atual de LLM e assistivo, nao autonomo:

- scoring de vaga
- extracao estruturada de requisitos
- rationale de revisao
- prioridade de candidatura
- interpretacao de modal do LinkedIn com fallback deterministico
- sugestao de perfil do candidato a partir do curriculo

Regra de seguranca:

- saida estruturada deve ser parseada
- falha de LLM deve cair para comportamento conservador
- LLM nao autoriza submit, nao altera gates humanos e nao substitui persistencia oficial

## Documentos Relacionados

- `AGENTS.md`
  regras operacionais e arquiteturais do repositorio
- `docs/plans/POS_MVP_ESTRUTURA_E_REFATORACAO_CHECKLIST.md`
  backlog vivo e registro de fechamento estrutural
- `docs/archive/ARCHITECTURE_REFACTOR_PLAN.md`
  material historico de refatoracao
