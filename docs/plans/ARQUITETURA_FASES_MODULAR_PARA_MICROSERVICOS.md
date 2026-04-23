# Arquitetura em Fases: Monólito Modular -> Microserviços

## Contexto

Para o cenário atual (uso pessoal, local-first, confiabilidade acima de escala), a estratégia recomendada é evoluir em fases:

1. fortalecer modularidade e isolamento operacional dentro do monólito
2. só depois considerar microserviços, quando houver sinais claros de necessidade

## Fase 1 (Agora): Monólito Modular com Workers

### Objetivo

Aumentar organização, testabilidade e isolamento de falhas sem explodir complexidade operacional.

### Componentes

- `orchestrator`: agenda ciclos, dispara etapas e consolida métricas
- `collector_worker`: coleta e normaliza vagas por portal
- `matching_worker`: aplica regra determinística + scoring assistivo
- `review_worker`: prepara draft/preflight/submit respeitando gate humano
- `store`: SQLite único como fonte de verdade
- `queue`: fila local simples (SQLite ou NDJSON)

### Contratos de Evento (JSON versionado)

- `JobCollectedV1`
- `JobNormalizedV1`
- `JobScoredV1`
- `ApplicationActionRequestedV1`
- `ApplicationActionResultV1`

### Regras Técnicas

- domínio e transições de estado permanecem centralizados no core
- workers reutilizam módulo comum de regras (sem duplicação)
- idempotência por `external_key` + `run_id`
- retry com backoff por etapa
- DLQ local para falhas recorrentes

## Fase 2 (Depois, Opcional): Microserviços Reais

### Quando considerar

Só avançar se aparecerem gatilhos concretos:

- necessidade de escalar coleta separadamente
- múltiplos usuários/ambientes em paralelo
- volume/concorrrência além do confortável no processo único
- exigência de SLO com isolamento forte por domínio

### Serviços alvo

- `crawler-service`
- `matching-service`
- `application-service`
- `control-plane` (orquestração/estado)

### Comunicação

- eventos assíncronos (ex.: NATS/Rabbit/Kafka)
- contratos versionados e compatíveis por evolução
- banco por serviço apenas quando houver necessidade comprovada

## Plano de Migração (Incremental)

1. Introduzir fila local e execução por estágio sem quebrar a CLI atual.
2. Extrair coletor para processo separado (`collector_worker`).
3. Extrair matching para processo separado (`matching_worker`).
4. Medir por 2 semanas (estabilidade, throughput, ruído, manutenção).
5. Decidir sobre Fase 2 apenas com evidência operacional.

## Critérios de Sucesso

- reduzir acoplamento sem regressão no loop principal
- manter transições de estado explícitas e auditáveis
- melhorar observabilidade por etapa
- preservar operação local simples para uso diário
