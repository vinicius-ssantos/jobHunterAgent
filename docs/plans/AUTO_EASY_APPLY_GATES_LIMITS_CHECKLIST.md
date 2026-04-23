# Auto Easy Apply - Gates e Limites

## Objetivo

Permitir envio assistido em lote com segurancas explicitas para evitar submissao fora de perfil e reduzir risco operacional.

## Checklist

- [x] Criar branch de trabalho `feature/auto-easy-apply-gates-limits`.
- [x] Definir checklist versionada da feature.
- [x] Adicionar configuracoes validadas de auto apply em `Settings`.
- [x] Implementar servico de `auto_easy_apply` com gates iniciais obrigatorios.
- [x] Implementar limites operacionais por ciclo e por dia.
- [x] Implementar cooldown entre submits e circuit breaker por erros consecutivos.
- [x] Expor comando CLI `applications auto-apply`.
- [x] Integrar `auto-apply` no ciclo principal quando `auto_easy_apply_enabled=true`.
- [x] Cobrir fluxo com testes unitarios.
- [x] Executar suite de testes impactada.
- [x] Endurecer gates avancados (detecao explicita de easy apply no detalhe, denylist configuravel, janela horaria e stop por bloqueios repetidos).
