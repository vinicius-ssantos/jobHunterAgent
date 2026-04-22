# Remove Hardcodes Residuais De Criterios

## Objetivo

Externalizar hardcodes residuais de criterios operacionais sem alterar gates de seguranca do produto.

## Escopo

- `job_hunter_agent/llm/application_priority.py`
- `job_hunter_agent/application/application_preparation.py`
- `job_hunter_agent/application/composition.py`
- `job_hunter_agent/core/settings.py`
- `.env.example`
- `README.md`

## Checklist

- [x] Mapear criterios residuais com maior impacto operacional
- [x] Externalizar thresholds de prioridade (`alta` e `media`) para configuracao
- [x] Externalizar modalidades preferenciais da priorizacao para configuracao
- [x] Manter fallback deterministico com defaults seguros e validar no startup
- [x] Ajustar testes de prioridade para comportamento configuravel
- [x] Documentar novo contrato operacional de configuracao
- [x] Validar suite completa de testes
