# Legacy Cleanup Map

## Objetivo

Reduzir ambiguidade entre runtime ativo, documentacao historica, planos ativos e codigo legado/experimental.

Este documento atende a issue #70 e e intencionalmente documental: nao remove codigo, nao altera runtime e nao muda imports.

## Fonte De Verdade Atual

O runtime ativo da v1 mora em:

```text
job_hunter_agent/
main.py
```

Pacotes centrais:

```text
job_hunter_agent/core/
job_hunter_agent/application/
job_hunter_agent/collectors/
job_hunter_agent/infrastructure/
job_hunter_agent/llm/
```

`main.py` deve continuar como entrypoint fino.

## Regra Principal

Codigo novo deve depender de contratos atuais em `job_hunter_agent/` e dos documentos operacionais atuais em `docs/`.

Nao usar documentacao historica como fonte de verdade de runtime.

## Classificacao De Documentos

### Guias Operacionais Atuais

Estes documentos representam o estado atual ou decisoes operacionais da v1:

- `docs/DATA_CONTRACT.md`
- `docs/V1_HARDENING_CHECKLIST.md`
- `docs/POST_MVP_SAFETY_BOUNDARIES.md`
- `docs/V1_ROADMAP_MAINTENANCE.md`
- `docs/V1_CRITICAL_VALIDATION_MATRIX.md`
- `docs/APPLICATION_OPERATIONS.md`
- `docs/TELEGRAM_HUMAN_REVIEW_GATES.md`
- `docs/DOMAIN_EVENTS.md`
- `docs/SQLITE_CRITICAL_STATE_AUDIT.md`
- `docs/SQLITE_SCHEMA_AND_UTC_CHECKLIST.md`
- `docs/SQLITE_LEGACY_TIMESTAMP_MIGRATION_PLAN.md`
- `docs/APPLICATION_EVALUATION_REPORT.md`
- `docs/CAREER_OPS_ADAPTATION_ASSESSMENT.md`

Tratamento:

- podem ser citados em novas issues;
- podem orientar implementacao;
- devem ser mantidos alinhados ao README.

### Planos E Checklists Ativos

Estes documentos ainda funcionam como backlog ou criterios de evolucao:

- `docs/plans/POS_MVP_ESTRUTURA_E_REFATORACAO_CHECKLIST.md`
- `docs/plans/REMOVE_LEGACY_MATCHING_HARDCODES_CHECKLIST.md`
- `docs/plans/RUNTIME_STRUCTURED_MATCHING_SOURCE_CHECKLIST.md`
- `docs/plans/STRUCTURED_MATCHING_FALLBACK_EXIT_CRITERIA.md`
- `docs/plans/SQLITE_SCHEMA_AND_UTC_CHECKLIST.md`

Tratamento:

- manter enquanto tiverem itens nao encerrados;
- quando virarem historicos, mover ou referenciar em `docs/archive/`;
- nao duplicar checklist canonico quando ja existir documento atual equivalente.

### Documentacao Historica

Documentos historicos devem ser preservados como contexto, nao como fonte atual:

- `docs/archive/ARCHITECTURE_REFACTOR_PLAN.md`

Tratamento:

- nao usar como criterio de runtime atual;
- nao atualizar para parecer estado atual;
- se necessario, adicionar aviso de contexto historico no topo.

## Arquitetura Legada

O diretorio `files/` nao faz parte da arquitetura ativa e nao deve ser recriado.

Se uma referencia antiga mencionar `files/` como runtime, ela deve ser tratada como legado/historico.

## Compatibilidade Legada De Matching

O caminho legado de matching ainda existe como compatibilidade marginal.

Variaveis legadas:

```text
JOB_HUNTER_PROFILE_TEXT
JOB_HUNTER_INCLUDE_KEYWORDS
JOB_HUNTER_EXCLUDE_KEYWORDS
JOB_HUNTER_ACCEPTED_WORK_MODES
JOB_HUNTER_MINIMUM_SALARY_BRL
JOB_HUNTER_MINIMUM_RELEVANCE
```

Tratamento:

- nao remover sem checklist especifico;
- nao usar como centro de novas features;
- codigo novo deve preferir fonte estruturada e contratos explicitos;
- fallback legado deve continuar exigindo configuracao explicita quando habilitado.

Documentos relacionados:

- `docs/plans/REMOVE_LEGACY_MATCHING_HARDCODES_CHECKLIST.md`
- `docs/plans/RUNTIME_STRUCTURED_MATCHING_SOURCE_CHECKLIST.md`
- `docs/plans/STRUCTURED_MATCHING_FALLBACK_EXIT_CRITERIA.md`

## Criterios Para Remocao Futura

Antes de remover codigo, arquivo ou plano legado:

- [ ] existe teste cobrindo o comportamento atual;
- [ ] README nao aponta mais para o item como ativo;
- [ ] nenhum import ativo depende do modulo;
- [ ] nenhuma configuracao documentada depende do item;
- [ ] existe plano de rollback simples;
- [ ] a remocao nao apaga dados do usuario;
- [ ] a remocao nao recria `files/` nem move runtime ativo para fora de `job_hunter_agent/`.

## Criterios Para Marcar Como Deprecated

Um item pode ser marcado como deprecated quando:

- ainda pode ser usado por compatibilidade;
- nao deve receber novas features;
- existe alternativa atual documentada;
- remocao imediata teria risco desnecessario.

Formato recomendado:

```text
Deprecated: mantido apenas por compatibilidade. Codigo novo deve usar <alternativa>.
```

## Criterios Para Arquivar Documento

Um documento pode ir para `docs/archive/` quando:

- descreve decisao passada;
- nao e mais criterio de aceite;
- nao deve orientar implementacao nova;
- existe documento atual substituto.

Ao arquivar:

- manter link de substituicao quando houver;
- evitar editar conteudo historico para parecer atual;
- atualizar README se o documento era listado como ativo.

## Mapa De Risco

| Area | Risco | Acao segura |
| --- | --- | --- |
| Runtime | Remover modulo ainda importado | Buscar imports e rodar `pytest` |
| Matching | Quebrar fallback legado usado localmente | Seguir checklists de matching antes de remover |
| Docs | Duplicar fonte de verdade | Manter README como indice de docs atuais |
| Dados locais | Apagar arquivo do usuario | Seguir `docs/DATA_CONTRACT.md` |
| CLI | Remover comando usado em operacao | Validar parser/dispatch e docs |
| SQLite | Migrar sem backup | Seguir auditoria SQLite e plano UTC |

## Ordem Recomendada De Cleanup

1. Documentar mapas e criterios de remocao.
2. Marcar documentos historicos explicitamente como historicos.
3. Consolidar checklists duplicados.
4. Auditar imports antes de remover codigo.
5. Remover apenas itens sem import, sem referencia ativa e com testes passando.

## Comandos Uteis

Buscar referencias locais:

```bash
grep -R "files/" -n .
grep -R "deprecated\|legacy\|legado" -n job_hunter_agent docs tests
```

Rodar validacao minima:

```bash
pytest
```

Validar caminhos criticos antes de cleanup maior:

```bash
pytest tests/test_runtime.py tests/test_app_bootstrap.py tests/test_composition_injection.py
```

## Criterios De Aceite Da Issue #70

- [x] Runtime ativo esta explicitamente identificado.
- [x] Documentos atuais, planos ativos e historicos estao classificados.
- [x] Compatibilidade legada de matching esta documentada como marginal.
- [x] Criterios para remocao, deprecacao e arquivamento estao definidos.
- [x] Nenhuma remocao arriscada foi feita nesta etapa.
