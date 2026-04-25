# Event Driven Workers Checklist

## Objetivo

Evoluir o runtime atual para uma arquitetura orientada a eventos e workers separados, sem migrar imediatamente para microservicos em repositorios distintos.

A meta desta frente e criar seams reais para execucao distribuida futura, mantendo o produto atual estavel e evitando uma reescrita big bang.

## Decisao Arquitetural

- [x] Manter o repositorio atual como fonte de verdade do produto.
- [x] Evitar criar um novo repositorio para microservicos antes de estabilizar contratos e eventos.
- [x] Evoluir primeiro para um modular monolith com workers executaveis separadamente.
- [x] Preservar o loop principal atual de coleta, matching, revisao humana e candidatura assistida.
- [x] Tratar microservicos reais como opcao futura, nao como destino imediato obrigatorio.

## Principios

- contratos antes de infraestrutura
- workers antes de multiplos repositorios
- eventos versionados antes de filas externas
- idempotencia antes de paralelismo
- observabilidade antes de automacao mais agressiva
- compatibilidade com o runtime atual durante toda a transicao

## Estado Atual Relevante

O CLI ja possui comandos de worker isolado:

- `python main.py worker list`
- `python main.py worker collect`
- `python main.py worker match`

Esses comandos sao a base inicial para a extracao gradual.

## Fase 0 — Plano E Fronteiras

- [x] Criar checklist da frente event-driven workers.
- [ ] Mapear fluxos atuais que viram eventos.
- [ ] Definir glossario minimo de eventos e comandos.
- [ ] Registrar decisoes de fronteira entre runtime atual, workers e storage.
- [ ] Garantir que nenhuma mudanca desta fase altere comportamento operacional.

## Fase 1 — Contratos De Eventos Versionados

Criar contratos pequenos, explicitos e testaveis para eventos do pipeline.

Eventos candidatos:

- `JobCollectedV1`
- `JobScoredV1`
- `JobPersistedV1`
- `JobReviewRequestedV1`
- `JobReviewedV1`
- `ApplicationDraftCreatedV1`
- `ApplicationPreflightCompletedV1`
- `ApplicationAuthorizedV1`
- `ApplicationSubmittedV1`
- `ApplicationBlockedV1`

Checklist:

- [x] Criar modulo de contratos de eventos em `job_hunter_agent/core/events.py` ou pacote equivalente.
- [x] Definir campos minimos para `JobCollectedV1`.
- [x] Definir campos minimos para `JobScoredV1`.
- [ ] Definir campos minimos para eventos de revisao.
- [ ] Definir campos minimos para eventos de candidatura.
- [x] Incluir `event_id`, `event_type`, `event_version`, `occurred_at` e `correlation_id` onde fizer sentido.
- [x] Adicionar serializacao/deserializacao JSON.
- [x] Adicionar testes de round-trip dos eventos.
- [x] Garantir compatibilidade dos eventos com NDJSON atual dos workers.

## Fase 2 — Porta De Event Bus Local

Introduzir uma abstracao de transporte antes de escolher Redis, RabbitMQ, NATS ou outro broker.

Checklist:

- [x] Criar `EventBusPort` com `publish` e `consume`/`read` conforme necessidade real.
- [x] Implementar `LocalNdjsonEventBus` usando arquivos locais.
- [x] Adaptar `worker collect` para publicar via porta em vez de escrever diretamente no detalhe do transporte.
- [x] Adaptar `worker match` para consumir via porta.
- [x] Adicionar idempotencia minima por `event_id` ou chave natural.
- [x] Adicionar testes unitarios do event bus local.
- [x] Manter CLI atual compativel com `--input`, `--output` e `--state`.

## Fase 3 — Separacao Dos Workers Sem Separar Repos

Transformar os comandos existentes em workers mais explicitos, mas ainda no mesmo repositorio.

Workers alvo:

- `collector-worker`
- `matching-worker`
- `review-notifier-worker`
- `application-worker`
- `scheduler-worker`

Checklist:

- [x] Documentar responsabilidade de cada worker.
- [x] Criar entrypoints ou comandos CLI claros para cada worker.
- [x] Garantir que cada worker inicialize apenas as dependencias necessarias.
- [x] Evitar que worker de coleta inicialize Telegram quando nao precisa.
- [x] Evitar que worker de matching inicialize browser quando nao precisa.
- [x] Adicionar logs com `correlation_id`.
- [x] Adicionar testes de inicializacao leve dos workers.

## Fase 4 — Storage E Idempotencia

Antes de filas externas, o projeto precisa garantir consistencia quando workers rodam separados.

Checklist:

- [x] Definir ownership de escrita em `jobs`, `seen_jobs`, `job_applications` e eventos.
- [x] Criar estrategia de idempotencia por evento.
- [x] Avaliar schema versionado para SQLite.
- [x] Padronizar timestamps em UTC para novos eventos/artefatos de worker.
- [ ] Registrar eventos de dominio para transicoes relevantes.
- [x] Garantir que reprocessar o mesmo evento nao duplica vagas ou candidaturas.

## Fase 5 — Docker Compose Local

Criar ambiente local reprodutivel antes de microservicos reais.

Servicos candidatos:

- `scheduler`
- `collector-worker`
- `matching-worker`
- `telegram-bot`
- `application-worker`
- `ollama` externo/local documentado
- volume para banco e artefatos

Checklist:

- [ ] Criar `Dockerfile` da aplicacao.
- [ ] Criar `docker-compose.yml` inicial.
- [ ] Configurar volumes para SQLite, browser state e artefatos.
- [ ] Documentar bootstrap de sessao LinkedIn em ambiente containerizado.
- [ ] Documentar limites e riscos de automacao com browser.
- [ ] Garantir modo sem Telegram para workers internos.

## Fase 6 — Broker Externo Opcional

Somente apos contratos, workers e idempotencia estarem estaveis.

Opcoes:

- Redis Streams
- RabbitMQ
- NATS

Checklist:

- [ ] Escolher broker com base em simplicidade operacional.
- [ ] Implementar adapter mantendo `EventBusPort`.
- [ ] Manter `LocalNdjsonEventBus` para testes e desenvolvimento.
- [ ] Criar testes de contrato compartilhados entre adapters.
- [ ] Documentar retries, dead-letter e poison messages.

## Fase 7 — Avaliacao De Microservicos Reais

So separar repositorios se houver beneficio concreto.

Criterios para considerar multiplos repos:

- [ ] deploy independente realmente necessario
- [ ] ciclos de mudanca muito diferentes entre componentes
- [ ] necessidade de escalar workers independentemente
- [ ] contratos versionados ja estaveis
- [ ] observabilidade e retry ja resolvidos
- [ ] custo de operacao aceito conscientemente

## Fora De Escopo Nesta Frente

- reescrever todo o produto
- remover o runtime atual
- trocar SQLite por Postgres sem necessidade imediata
- introduzir Kubernetes
- separar repositorios antes dos contratos
- automatizar submissao sem gates humanos e operacionais

## Definicao De Pronto Da Frente

Esta frente sera considerada concluida quando:

- workers principais puderem rodar separadamente no mesmo repositorio
- contratos de eventos tiverem testes de round-trip
- o transporte local NDJSON estiver atras de uma porta
- reprocessamento basico for idempotente
- Docker Compose local estiver documentado
- o runtime atual continuar funcionando sem regressao

## Proximo Passo Imediato

Iniciar a Fase 5 com Dockerfile e Docker Compose local, mantendo SQLite, browser state e artefatos em volumes e sem introduzir broker externo ainda.
