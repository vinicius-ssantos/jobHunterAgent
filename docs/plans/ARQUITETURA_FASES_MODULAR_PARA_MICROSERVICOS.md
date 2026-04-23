# Arquitetura em fases: monolito modular -> microservicos

## Contexto

Para o cenario atual (uso pessoal, local-first, confiabilidade acima de escala), a estrategia recomendada e evoluir em fases:

1. fortalecer modularidade e isolamento operacional dentro do monolito
2. so depois considerar microservicos, quando houver sinais claros de necessidade

## Fase 1 (agora): monolito modular com workers

### Objetivo

Aumentar organizacao, testabilidade e isolamento de falhas sem explodir complexidade operacional.

### Componentes

- `orchestrator`: agenda ciclos, dispara etapas e consolida metricas
- `collector_worker`: coleta e normaliza vagas por portal
- `matching_worker`: aplica regra deterministica + scoring assistivo
- `review_worker`: prepara draft/preflight/submit respeitando gate humano
- `store`: SQLite unico como fonte de verdade
- `queue`: fila local simples (SQLite ou NDJSON)

### Contratos de evento (JSON versionado)

- `JobCollectedV1`
- `JobNormalizedV1`
- `JobScoredV1`
- `ApplicationActionRequestedV1`
- `ApplicationActionResultV1`

### Regras tecnicas

- dominio e transicoes de estado permanecem centralizados no core
- workers reutilizam modulo comum de regras (sem duplicacao)
- idempotencia por `external_key` + `run_id`
- retry com backoff por etapa
- DLQ local para falhas recorrentes

## Checklist de execucao da fase 1

- [x] Introduzir contratos de evento versionados na camada `application`.
- [x] Criar fila local em memoria para desacoplar coleta e despacho de revisao.
- [x] Refatorar o ciclo para `CollectionCycleOrchestrator` + workers sem mudar o comportamento externo.
- [x] Extrair `collector_worker` para processo separado mantendo contratos estaveis.
- [ ] Extrair `matching_worker` para processo separado mantendo idempotencia por evento.
- [ ] Adicionar DLQ local e politica padrao de retry/backoff por etapa.

## Fase 2 (depois, opcional): microservicos reais

### Quando considerar

So avancar se aparecerem gatilhos concretos:

- necessidade de escalar coleta separadamente
- multiplos usuarios/ambientes em paralelo
- volume/concorrrencia alem do confortavel no processo unico
- exigencia de SLO com isolamento forte por dominio

### Servicos alvo

- `crawler-service`
- `matching-service`
- `application-service`
- `control-plane` (orquestracao/estado)

### Comunicacao

- eventos assincronos (ex.: NATS/Rabbit/Kafka)
- contratos versionados e compativeis por evolucao
- banco por servico apenas quando houver necessidade comprovada

## Plano de migracao (incremental)

1. Introduzir fila local e execucao por estagio sem quebrar a CLI atual.
2. Extrair coletor para processo separado (`collector_worker`).
3. Extrair matching para processo separado (`matching_worker`).
4. Medir por 2 semanas (estabilidade, throughput, ruido, manutencao).
5. Decidir sobre fase 2 apenas com evidencia operacional.

## Criterios de sucesso

- reduzir acoplamento sem regressao no loop principal
- manter transicoes de estado explicitas e auditaveis
- melhorar observabilidade por etapa
- preservar operacao local simples para uso diario
