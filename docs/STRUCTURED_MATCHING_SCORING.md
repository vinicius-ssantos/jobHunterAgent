# Structured Matching Scoring

## Objetivo

Documentar o contrato atual de matching estruturado da v1: dimensoes deterministicas, papel do LLM, persistencia do score e criterios minimos de regressao.

Este documento atende a issue #65 e complementa:

- `docs/V1_HARDENING_CHECKLIST.md`;
- `docs/V1_CRITICAL_VALIDATION_MATRIX.md`;
- `docs/SQLITE_CRITICAL_STATE_AUDIT.md`;
- `docs/LEGACY_CLEANUP_MAP.md`.

## Resumo Do Fluxo

O matching da v1 usa duas camadas:

```text
prefilters deterministicos -> scoring LLM conservador -> persistencia SQLite
```

A primeira camada rejeita vagas com sinais objetivos incompatíveis. A segunda camada pede ao LLM uma nota de 1 a 10 e uma rationale curta quando a vaga passa pelos filtros.

## Entradas

### Perfil Runtime

Contrato principal:

```text
RuntimeMatchingProfile
```

Campos relevantes:

- `candidate_summary`;
- `include_keywords`;
- `exclude_keywords`;
- `accepted_work_modes`;
- `minimum_salary_brl`;
- `minimum_relevance`;
- `target_seniorities`;
- `allow_unknown_seniority`;
- `linkedin_precision_gate`.

Fonte preferencial:

```text
StructuredMatchingSource
```

Compatibilidade:

- `MatchingCriteria` legado ainda pode ser convertido para `RuntimeMatchingProfile`;
- codigo novo deve preferir `RuntimeMatchingProfile` e fonte estruturada.

### Vaga

Contrato de entrada:

```text
RawJob
```

Campos relevantes:

- `title`;
- `company`;
- `location`;
- `work_mode`;
- `salary_text`;
- `url`;
- `source_site`;
- `summary`;
- `description`.

## Dimensoes Deterministicas

### 1. Validade Minima

Antes de qualquer scoring, a vaga precisa ter:

- titulo;
- empresa;
- URL;
- fonte.

Se falhar, a vaga e descartada sem LLM.

### 2. Precision Gate Do LinkedIn

Aplicado apenas para fonte LinkedIn quando habilitado.

Dimensoes:

- `required_terms`: todos devem aparecer;
- `any_terms`: pelo menos um deve aparecer quando configurado;
- `blocked_terms`: qualquer termo bloqueia.

Rationales internas esperadas:

- `precision_gate_texto_indisponivel`;
- `precision_gate_termo_bloqueado`;
- `precision_gate_stack_fora_do_alvo`;
- `precision_gate_perfil_fora_do_alvo`.

### 3. Candidatura Externa Provavel

Para LinkedIn, sinais de candidatura fora do LinkedIn bloqueiam a vaga antes do LLM.

Rationale interna:

```text
candidatura_externa_provavel
```

### 4. Termos Excluidos

Se `exclude_keywords` aparecerem no texto combinado, a vaga e rejeitada antes do LLM.

Token persistivel/legivel:

```text
termos_excluidos
```

### 5. Senioridade

Se `target_seniorities` estiver configurado, o texto da vaga e avaliado por senioridade inferida.

Resultados relevantes:

- senioridade dentro do alvo: continua;
- senioridade fora do alvo: rejeita;
- senioridade nao informada: aceita ou rejeita conforme `allow_unknown_seniority`.

Tokens persistiveis/legiveis:

```text
senioridade_fora_do_alvo
senioridade_nao_informada
```

### 6. Modalidade

`work_mode` e comparado contra `accepted_work_modes`.

Regras:

- vazio ou `nao informado` e aceito;
- se nao houver modalidades aceitas configuradas, qualquer modalidade passa;
- caso contrario, o texto normalizado deve conter uma das modalidades aceitas.

Token persistivel/legivel:

```text
modalidade_incompativel
```

### 7. Salario Minimo

Quando `salary_text` permite extrair piso salarial, ele deve ser maior ou igual a `minimum_salary_brl`.

Regras:

- salario ausente passa;
- salario abaixo do minimo rejeita;
- parsing usa o primeiro valor numerico encontrado.

Token persistivel/legivel:

```text
salario_abaixo
```

## Papel Do LLM

O LLM so roda depois dos filtros deterministicos.

Entrada:

- perfil runtime;
- regras e keywords;
- vaga normalizada.

Saida esperada:

```json
{
  "relevance": 7,
  "rationale": "stack_alinhada; modalidade_compativel"
}
```

Regras:

- `relevance` e normalizado para o intervalo 1..10;
- resposta sem JSON valido vira score baixo e rejeitado;
- `accepted` depende de `minimum_relevance`;
- rationale deve ser curta e ancorada em sinais objetivos.

## Tokens Recomendados Para Rationale

Tokens esperados:

```text
stack_alinhada
stack_parcial
senioridade_compativel
senioridade_duvidosa
senioridade_fora_do_alvo
senioridade_nao_informada
modalidade_compativel
modalidade_incompativel
salario_abaixo
localizacao_duvidosa
sinais_insuficientes
termos_excluidos
```

O objetivo dos tokens e permitir comparacao, debugging e regressao sem depender de texto livre longo.

## Persistencia

Vagas aceitas sao persistidas em `jobs`.

Campos principais:

- `jobs.relevance`: score final do matching;
- `jobs.rationale`: justificativa curta;
- `jobs.external_key`: chave auxiliar de deduplicacao;
- `jobs.status`: estado de revisao humana.

Vagas descartadas por score ou regra sao registradas em `seen_jobs` com motivo:

```text
discarded_rule:<reason>
discarded_score:<relevance>
```

## Ordem De Decisao

Ordem atual:

1. validade minima;
2. deduplicacao por `jobs`/`seen_jobs`;
3. precision gate LinkedIn;
4. candidatura externa provavel;
5. termos excluidos;
6. senioridade;
7. modalidade;
8. salario minimo;
9. LLM scoring;
10. persistencia se aceito.

## Testes De Regressao

Coberturas atuais relevantes:

- `tests/test_runtime_matching.py` cobre prefilters deterministicos e tokens de rationale;
- `tests/test_matching_prompt.py` cobre prompt e guidance de rationale;
- `tests/test_job_collector.py` cobre pipeline, persistencia de jobs aceitos, descartes, precision gate e edge cases de parsing;
- `tests/test_runtime_matching.py` deve continuar recebendo casos pequenos sempre que nova dimensao deterministica for adicionada.

## Criterios Para Novas Dimensoes

Toda nova dimensao de matching deve definir:

- nome da dimensao;
- origem do dado;
- regra deterministica, se houver;
- impacto no score;
- token de rationale;
- persistencia esperada;
- teste unitario minimo;
- comportamento quando o dado estiver ausente.

## Fora De Escopo Da V1

- explicar score com pesos numericos completos;
- criar tabela separada de scoring dimensions;
- treinar ou calibrar modelo externo;
- ranking estatistico por historico real de candidatura;
- substituir revisao humana por score automatico;
- usar LLM para autorizar submit.

## Criterios De Aceite Da Issue #65

- [x] Score e explicacao sao persistidos em `jobs.relevance` e `jobs.rationale`.
- [x] Dimensoes deterministicas de score estao documentadas.
- [x] Sinal deterministico e sinal LLM estao separados.
- [x] Motivos de descarte antes do LLM ficam rastreaveis em `seen_jobs.reason`.
- [x] Casos minimos de ranking, threshold, prefilters e edge cases estao cobertos pela suite.
