# Legacy Matching Residual Map

## Objetivo

Mapear os pontos que ainda carregam residuos do matching legado nesta branch.

## Pontos Ainda Residuais

### `job_hunter_agent/core/settings.py`

Mantem o bloco de compatibilidade legado:

- `profile_text`
- `include_keywords`
- `exclude_keywords`
- `accepted_work_modes`
- `minimum_salary_brl`
- `minimum_relevance`

Estado atual:

- encapsulado em `build_legacy_matching_config()`
- ainda necessario enquanto o runtime principal nao consumir fonte estruturada propria

### `job_hunter_agent/core/matching.py`

Mantem o shape legado de `MatchingCriteria`.

Estado atual:

- a ponte `LegacyMatchingConfig -> MatchingCriteria` ja esta encapsulada
- o shape ainda representa o contrato antigo de scoring/prefiltro

### `job_hunter_agent/core/matching_prompt.py`

Mantem o prompt legado de scoring.

Estado atual:

- helper explicitado
- reduzido o hardcode inline no scorer
- ainda baseado no contrato legado atual

### `job_hunter_agent/collectors/collector.py`

Mantem o prefiltro baseado em `MatchingCriteria`.

Estado atual:

- razoes deterministicas ja centralizadas em helper proprio
- ainda depende do shape legado de criteria

### `job_hunter_agent/llm/scoring.py`

Mantem o scorer assistivo consumindo `MatchingCriteria`.

Estado atual:

- prompt legado extraido para helper
- fallbacks padronizados
- ainda acoplado ao contrato legado atual

## Leitura Correta Do Estado Atual

- o legado deixou de ficar espalhado de forma ad-hoc
- ele ainda existe, mas agora esta mais encapsulado
- o proximo passo estrutural so fecha de vez quando o runtime principal passar a depender de uma fonte de verdade estruturada, reduzindo o contrato legado para compatibilidade marginal
