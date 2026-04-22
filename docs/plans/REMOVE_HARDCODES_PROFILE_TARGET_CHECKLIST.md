# Remove Hardcodes De Perfil E Vaga

## Objetivo

Eliminar hardcodes ligados a definicao de perfil do candidato e vaga alvo no runtime principal, mantendo compatibilidade controlada e fail-fast explicito.

## Escopo

- `job_hunter_agent/core/settings.py`
- `job_hunter_agent/core/legacy_matching_config.py`
- `job_hunter_agent/core/structured_matching_config.py`
- `README.md`
- testes afetados por defaults legados

## Checklist

- [x] Mapear hardcodes ativos de perfil/vaga e pontos de fallback
- [x] Remover defaults legados de perfil/matching em `Settings`
- [x] Desligar fallback legado por padrao (`structured_matching_fallback_enabled=false`)
- [x] Remover query hardcoded de vaga alvo na `search_url` default
- [x] Garantir erro explicito quando fallback legado estiver habilitado sem configuracao minima
- [x] Ajustar testes para o novo comportamento sem hardcode
- [x] Atualizar documentacao operacional (`README`) com novo contrato
- [x] Validar testes relevantes da area alterada

## Proxima Onda (Remanescentes)

- [x] Externalizar aliases de skills hoje fixos em `core/candidate_profile.py`
- [x] Externalizar listas de stack primaria/secundaria hoje fixas em `llm/job_requirements.py`
- [x] Remover lista fixa de stacks no prompt de `llm/candidate_profile_extractor.py`
