# Easy Apply Gargalos Checklist

## Objetivo

Reduzir desperdício operacional no funil de candidatura Easy Apply com foco em:

- filtrar vagas provavelmente externas antes da pipeline de candidatura
- aumentar cobertura de respostas automáticas para perguntas recorrentes
- medir conversão por etapa para priorizar melhorias por dados

## Execução

- [x] Filtrar vagas LinkedIn com forte sinal de candidatura externa na pré-triagem (`candidatura_externa_provavel`)
- [x] Introduzir base de respostas conhecidas no `candidate_profile.json` (`known_answers` + `fragments`)
- [x] Aplicar matching semântico simples (normalização + similaridade por tokens) para mapear perguntas do modal
- [x] Preencher respostas conhecidas no modal para campos obrigatórios (`input/textarea/select`)
- [x] Expor métricas de conversão por etapa no resumo da execução
- [x] Adicionar queries avançadas do LinkedIn com filtros (experiência/modalidade/easy apply/recência) e rotação por ciclo
- [x] Cobrir as mudanças com testes automatizados e validar suíte completa

## Resultado

Suíte validada localmente: `423 passed`.
