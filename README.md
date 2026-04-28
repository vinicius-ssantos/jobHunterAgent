# Job Hunter Agent

MVP local para coleta, triagem e revisao humana de vagas via Telegram.

## Fonte de verdade

O runtime ativo mora no pacote `job_hunter_agent/`.

- `job_hunter_agent/core/`
- `job_hunter_agent/application/`
- `job_hunter_agent/collectors/`
- `job_hunter_agent/infrastructure/`
- `job_hunter_agent/llm/`
- `main.py` apenas como entrypoint fino

O diretorio `files/` foi removido da arquitetura ativa e nao deve ser recriado.

## Documentacao

Guias operacionais atuais:

- `docs/DATA_CONTRACT.md`
- `docs/V1_HARDENING_CHECKLIST.md`
- `docs/APPLICATION_OPERATIONS.md`
- `docs/DOMAIN_EVENTS.md`
- `docs/SQLITE_SCHEMA_AND_UTC_CHECKLIST.md`
- `docs/SQLITE_LEGACY_TIMESTAMP_MIGRATION_PLAN.md`

Planos e checklists ativos:

- `docs/plans/POS_MVP_ESTRUTURA_E_REFATORACAO_CHECKLIST.md`
- `docs/plans/REMOVE_LEGACY_MATCHING_HARDCODES_CHECKLIST.md`
- `docs/plans/RUNTIME_STRUCTURED_MATCHING_SOURCE_CHECKLIST.md`
- `docs/plans/STRUCTURED_MATCHING_FALLBACK_EXIT_CRITERIA.md`
- `docs/plans/SQLITE_SCHEMA_AND_UTC_CHECKLIST.md` aponta para o checklist canonico em `docs/SQLITE_SCHEMA_AND_UTC_CHECKLIST.md`

Documentacao historica:

- `docs/archive/ARCHITECTURE_REFACTOR_PLAN.md`

## Escopo da v1

- coletar vagas dos sites configurados
- avaliar aderencia ao perfil profissional com Ollama local
- persistir vagas relevantes em SQLite
- enviar vagas para revisao humana via Telegram
- registrar aprovacao ou rejeicao manual
- apoiar fluxo de candidatura assistido por comandos, diagnostico operacional e gates humanos de revisao/autorizacao

Submit real sem revisao humana e autorizacao explicita continua fora do caminho critico desta versao.

## Setup

1. Instale as dependencias:

```bash
pip install -r requirements.txt
```

2. Configure o Playwright/Chromium localmente no projeto.

No Windows PowerShell:

```powershell
.\scripts\setup_playwright.ps1
$env:PLAYWRIGHT_BROWSERS_PATH=".playwright-browsers"
```

3. Configure o `.env` usando `.env.example` como base.

## Matching estruturado como caminho principal

O runtime agora prefere uma fonte estruturada de matching.

Variaveis principais desse caminho:

- `JOB_HUNTER_STRUCTURED_MATCHING_CONFIG_PATH`
- `JOB_HUNTER_STRUCTURED_MATCHING_FALLBACK_ENABLED`
- `JOB_HUNTER_SKILL_TAXONOMY_PATH`

Comportamento:

- se o arquivo estruturado existir, ele vira a fonte principal do matching
- se o arquivo nao existir e o fallback estiver habilitado, o runtime cai para o contrato legado
- se o arquivo nao existir e o fallback estiver desligado, o runtime falha cedo
- o fallback vem desligado por padrao (`JOB_HUNTER_STRUCTURED_MATCHING_FALLBACK_ENABLED=false`)
- o gate de precisao do LinkedIn usa `matching.linkedin_precision_gate` quando configurado; se a secao estiver ausente, usa `include_keywords` como sinal positivo generico

Exemplo versionado:

- `job_target.example.json`

Copia recomendada para uso local:

- `job_target.json`

## Compatibilidade legada

O caminho legado continua existindo apenas como compatibilidade marginal.

Campos legados de compatibilidade:

- `JOB_HUNTER_PROFILE_TEXT`
- `JOB_HUNTER_INCLUDE_KEYWORDS`
- `JOB_HUNTER_EXCLUDE_KEYWORDS`
- `JOB_HUNTER_ACCEPTED_WORK_MODES`
- `JOB_HUNTER_MINIMUM_SALARY_BRL`
- `JOB_HUNTER_MINIMUM_RELEVANCE`

Tratamento esperado:

- ele existe por compatibilidade
- ele exige configuracao explicita quando fallback legado estiver habilitado
- nao deve voltar a ser apresentado como centro da evolucao do matching
- codigo novo deve depender da fonte estruturada ou de contratos explicitos, nunca do shape inteiro de `Settings`

## Variaveis principais de runtime

- `JOB_HUNTER_TELEGRAM_TOKEN`
- `JOB_HUNTER_TELEGRAM_CHAT_ID`
- `JOB_HUNTER_APPLICATION_CONTACT_EMAIL`
- `JOB_HUNTER_APPLICATION_PHONE`
- `JOB_HUNTER_APPLICATION_PHONE_COUNTRY_CODE`
- `JOB_HUNTER_CANDIDATE_PROFILE_PATH`
- `JOB_HUNTER_SKILL_TAXONOMY_PATH`
- `JOB_HUNTER_LINKEDIN_COMPANY_POLICY_PATH`
- `JOB_HUNTER_OPERATIONAL_POLICY_PATH`
- `JOB_HUNTER_COLLECTION_TIME`
- `JOB_HUNTER_DATABASE_PATH`
- `JOB_HUNTER_BROWSER_USE_CONFIG_DIR`
- `JOB_HUNTER_LINKEDIN_PERSISTENT_PROFILE_DIR`
- `JOB_HUNTER_LINKEDIN_STORAGE_STATE_PATH`
- `JOB_HUNTER_BROWSER_HEADLESS`
- `JOB_HUNTER_LINKEDIN_MAX_PAGES_PER_CYCLE`
- `JOB_HUNTER_LINKEDIN_MAX_PAGE_DEPTH`
- `JOB_HUNTER_LINKEDIN_SCROLL_STABILIZATION_PASSES`
- `JOB_HUNTER_LINKEDIN_DUPLICATE_PAGES_STOP_THRESHOLD`
- `JOB_HUNTER_LINKEDIN_PRECISION_GATE_ENABLED`
- `JOB_HUNTER_REVIEW_POLLING_GRACE_SECONDS`
- `JOB_HUNTER_ADAPTIVE_POLLING_BACKOFF_ENABLED`
- `JOB_HUNTER_ADAPTIVE_POLLING_EMPTY_CYCLES_BEFORE_BACKOFF`
- `JOB_HUNTER_ADAPTIVE_POLLING_BACKOFF_MULTIPLIER`
- `JOB_HUNTER_ADAPTIVE_POLLING_MAX_INTERVAL_SECONDS`
- `JOB_HUNTER_LINKEDIN_FIELD_REPAIR_ENABLED`
- `JOB_HUNTER_APPLICATION_SUPPORT_LLM_ENABLED`
- `JOB_HUNTER_JOB_REQUIREMENTS_LLM_ENABLED`
- `JOB_HUNTER_REVIEW_RATIONALE_LLM_ENABLED`
- `JOB_HUNTER_APPLICATION_PRIORITY_LLM_ENABLED`
- `JOB_HUNTER_PRIORITY_HIGH_MIN_RELEVANCE`
- `JOB_HUNTER_PRIORITY_MEDIUM_MIN_RELEVANCE`
- `JOB_HUNTER_PRIORITY_PREFERRED_WORK_MODES`
- `JOB_HUNTER_OLLAMA_MODEL`
- `JOB_HUNTER_OLLAMA_URL`

## Toggles operacionais de teste

- `JOB_HUNTER_RELAXED_MATCHING_FOR_TESTING`
- `JOB_HUNTER_RELAXED_TESTING_PROFILE_HINT`
- `JOB_HUNTER_RELAXED_TESTING_REMOVE_EXCLUDE_KEYWORDS`
- `JOB_HUNTER_RELAXED_TESTING_MINIMUM_RELEVANCE`

## Execucao

Rodar um ciclo imediatamente:

```bash
python main.py --agora
```

No PowerShell:

```powershell
.\scripts\run_job_hunter.ps1 --agora
```

Rodar sem inicializar Telegram:

```bash
python main.py --agora --sem-telegram
```

Rodar ciclos finitos:

```bash
python main.py --ciclos 3
python main.py --ciclos 3 --intervalo-ciclos-segundos 60
```

Comportamento operacional em ciclos finitos:

- o runtime aplica backoff adaptativo quando ciclos consecutivos nao persistem vagas novas
- o coletor do LinkedIn encerra a paginacao antes quando encontra apenas duplicadas em sequencia

Bootstrap da sessao autenticada do LinkedIn:

```bash
python main.py --bootstrap-linkedin-session
```

## Observabilidade

- cada ciclo gera logs por fonte
- o SQLite registra vagas, logs de coleta e execucoes
- falhas por portal nao interrompem as demais fontes
- o runtime informa quando cai no fallback legado de matching

## Testes

```bash
pytest
```
