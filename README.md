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

Documentacao ativa:

- `docs/plans/POS_MVP_ESTRUTURA_E_REFATORACAO_CHECKLIST.md`
- `docs/plans/REMOVE_LEGACY_MATCHING_HARDCODES_CHECKLIST.md`

Documentacao historica:

- `docs/archive/ARCHITECTURE_REFACTOR_PLAN.md`

## Escopo da v1

- coletar vagas dos sites configurados
- avaliar aderencia ao perfil profissional com Ollama local
- persistir vagas relevantes em SQLite
- enviar vagas para revisao humana via Telegram
- registrar aprovacao ou rejeicao manual

Candidatura automatica continua fora do caminho critico desta versao.

O projeto ja possui um fluxo de candidatura assistida operacional, separado do loop principal de coleta e revisao:

- contratos em `job_hunter_agent/application/applicant.py`
- persistencia separada de candidaturas em `job_applications`
- criacao de rascunho quando uma vaga e aprovada no Telegram
- classificacao conservadora de suporte: `auto_supported`, `manual_review` ou `unsupported`

Esse fluxo nao faz parte do loop automatico principal. Ele existe como trilha assistida e explicitamente autorizada pelo usuario.

Para o primeiro teste real controlado, o projeto fica reduzido por padrao a `1 portal`:

- `LinkedIn`

Depois que o fluxo estiver estavel, Gupy e Indeed podem ser reativados como expansao controlada.

## Setup

1. Instale as dependencias:

```bash
pip install -r requirements.txt
```

2. Configure o Playwright/Chromium localmente no projeto.

Recomendado para este MVP:

- aplicacao Python local
- Playwright/Chromium local
- Ollama local ou em Docker

No Windows PowerShell:

```powershell
.\scripts\setup_playwright.ps1
```

Isso instala o Chromium na pasta local `.playwright-browsers/`, que esta ignorada no Git.
Ao executar o projeto na mesma sessao, mantenha a variavel abaixo definida:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH=".playwright-browsers"
```

Se preferir fazer manualmente:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH=".playwright-browsers"
python -m playwright install chromium
```

3. Configure os valores obrigatorios.

O projeto le configuracao de `.env` e variaveis de ambiente via `pydantic-settings`.
Use `.env.example` como base para o seu `.env`.

Para reduzir atrito no uso diario, a recomendacao agora e:

- manter os valores `JOB_HUNTER_*` no `.env`
- usar os wrappers PowerShell em `scripts/` para rodar o projeto com um comando curto

Os wrappers ja:

- entram na raiz do projeto
- preferem o Python da `.venv`
- configuram `PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers` quando necessario
- adicionam o binario local do Ollama ao `PATH` quando ele existir no caminho padrao

### Variaveis principais de runtime

- `JOB_HUNTER_TELEGRAM_TOKEN`
- `JOB_HUNTER_TELEGRAM_CHAT_ID`
- `JOB_HUNTER_APPLICATION_CONTACT_EMAIL`
- `JOB_HUNTER_APPLICATION_PHONE`
- `JOB_HUNTER_APPLICATION_PHONE_COUNTRY_CODE`
- `JOB_HUNTER_CANDIDATE_PROFILE_PATH`
- `JOB_HUNTER_COLLECTION_TIME`
- `JOB_HUNTER_DATABASE_PATH`
- `JOB_HUNTER_BROWSER_USE_CONFIG_DIR`
- `JOB_HUNTER_LINKEDIN_PERSISTENT_PROFILE_DIR`
- `JOB_HUNTER_LINKEDIN_STORAGE_STATE_PATH`
- `JOB_HUNTER_BROWSER_HEADLESS`
- `JOB_HUNTER_LINKEDIN_MAX_PAGES_PER_CYCLE`
- `JOB_HUNTER_LINKEDIN_MAX_PAGE_DEPTH`
- `JOB_HUNTER_REVIEW_POLLING_GRACE_SECONDS`
- `JOB_HUNTER_LINKEDIN_FIELD_REPAIR_ENABLED`
- `JOB_HUNTER_APPLICATION_SUPPORT_LLM_ENABLED`
- `JOB_HUNTER_JOB_REQUIREMENTS_LLM_ENABLED`
- `JOB_HUNTER_REVIEW_RATIONALE_LLM_ENABLED`
- `JOB_HUNTER_APPLICATION_PRIORITY_LLM_ENABLED`
- `JOB_HUNTER_OLLAMA_MODEL`
- `JOB_HUNTER_OLLAMA_URL`

### Matching legado de compatibilidade

Neste momento, o runtime ainda depende de um contrato legado de matching encapsulado, derivado de `Settings`.
Nao amplie esse caminho em codigo novo.

Campo legado principal:

- `JOB_HUNTER_PROFILE_TEXT`

Tratamento esperado:

- ele existe por compatibilidade
- nao deve voltar a ser apresentado como fonte estrategica de evolucao do matching
- codigo novo deve depender de contratos explicitos, nao do shape inteiro de `Settings`

### Toggles operacionais de teste

- `JOB_HUNTER_RELAXED_MATCHING_FOR_TESTING`
- `JOB_HUNTER_RELAXED_TESTING_PROFILE_HINT`
- `JOB_HUNTER_RELAXED_TESTING_REMOVE_EXCLUDE_KEYWORDS`
- `JOB_HUNTER_RELAXED_TESTING_MINIMUM_RELEVANCE`

Modelo recomendado para este MVP e para a configuracao de hardware avaliada:

- `qwen2.5:7b`

Para depuracao inicial do fluxo real, recomenda-se:

- `JOB_HUNTER_BROWSER_HEADLESS=false`

Assim a janela do navegador fica visivel durante o teste.

Para gerar mais vagas novas durante testes de parsing, voce pode ativar temporariamente:

- `JOB_HUNTER_RELAXED_MATCHING_FOR_TESTING=true`

Esse modo remove `junior` dos termos excluidos para scoring e reduz a nota minima exigida, sem alterar o comportamento padrao quando desligado.

Tambem existe um fallback opcional de reparo local de campos do LinkedIn:

- `JOB_HUNTER_LINKEDIN_FIELD_REPAIR_ENABLED=true`

Ele so atua em casos residuais e suspeitos, depois da extracao deterministica e da tentativa de enriquecimento pela pagina de detalhe.

Tambem existe um assessor opcional de suporte de candidatura com LLM local:

- `JOB_HUNTER_APPLICATION_SUPPORT_LLM_ENABLED=true`

Ele enriquece a classificacao de aplicabilidade da candidatura durante a criacao de rascunhos, mas mantem o fallback deterministico atual quando estiver desabilitado ou quando o modelo falhar.

Tambem existe um extractor opcional de requisitos estruturados:

- `JOB_HUNTER_JOB_REQUIREMENTS_LLM_ENABLED=true`

Ele deriva sinais operacionais da vaga, como senioridade, stack principal/secundaria, ingles e sinais de lideranca, anexando isso aos rascunhos de candidatura como nota estruturada. Se o modelo falhar, o sistema cai para uma heuristica local deterministica.

Tambem existe um formatter opcional de rationale para revisao humana:

- `JOB_HUNTER_REVIEW_RATIONALE_LLM_ENABLED=true`

Ele reestrutura o motivo da vaga em pontos a favor, pontos contra e risco principal na hora de montar o card do Telegram. Se o modelo falhar ou estiver desligado, o texto original continua sendo usado.

Tambem existe um assessor opcional de prioridade operacional para candidaturas:

- `JOB_HUNTER_APPLICATION_PRIORITY_LLM_ENABLED=true`

Ele sugere uma prioridade assistiva (`alta`, `media`, `baixa`) para ordenar a fila de rascunhos e candidaturas em andamento. Se o modelo falhar ou estiver desligado, o sistema usa uma heuristica local conservadora.

## Execucao

Rodar um ciclo imediatamente:

```bash
python main.py --agora
```

No PowerShell, o atalho equivalente fica:

```powershell
.\scripts\run_job_hunter.ps1 --agora
```

Quando o Telegram estiver habilitado, `--agora` mantém o polling ativo por uma janela curta apos o envio dos cards para permitir cliques em `Aprovar` e `Ignorar`.
Esse tempo e controlado por `JOB_HUNTER_REVIEW_POLLING_GRACE_SECONDS`.

Rodar um ciclo imediatamente sem inicializar Telegram:

```bash
python main.py --agora --sem-telegram
```

Rodar um numero finito de ciclos imediatamente, sem cair no agendamento diario:

```bash
python main.py --ciclos 3
```

Se quiser manter um intervalo entre esses ciclos:

```bash
python main.py --ciclos 3 --intervalo-ciclos-segundos 60
```

Exportar a sessao autenticada do LinkedIn para `storage_state`:

```bash
python main.py --bootstrap-linkedin-session
```

Listar candidaturas pelo terminal:

```bash
python main.py applications list
python main.py applications list --status confirmed
```

Criar um rascunho de candidatura a partir de uma vaga aprovada:

```bash
python main.py applications create --job-id 17
```

Inspecionar uma candidatura especifica:

```bash
python main.py applications show --id 2
```

Rodar o fluxo operacional sem `python -c`:

```bash
python main.py status
python main.py jobs show --id 17
python main.py jobs approve --id 17
python main.py applications create --job-id 17
python main.py applications prepare --id 2
python main.py applications confirm --id 2
python main.py applications preflight --id 2
python main.py applications authorize --id 2
python main.py applications submit --id 2
python main.py applications artifacts --limit 5
python main.py candidate-profile suggest
```

Atalhos PowerShell para o fluxo de candidatura:

```powershell
.\scripts\authorize_application.ps1 8
.\scripts\preflight_application.ps1 8
.\scripts\submit_application.ps1 8
```

Atalho PowerShell para gerar sugestoes do perfil do candidato:

```powershell
.\scripts\suggest_candidate_profile.ps1
```

Rodar em modo agendado com polling do Telegram:

```bash
python main.py
```

## Comandos do bot

- `/status` mostra os contadores atuais
- `/pendentes` lista vagas aguardando revisao
- `/recentes` mostra as ultimas vagas registradas
- `/candidaturas` mostra rascunhos e candidaturas em andamento

## Observabilidade

- Cada ciclo de coleta gera logs por fonte.
- O SQLite registra vagas, logs de coleta e execucoes de coleta.
- Falhas por portal nao interrompem as demais fontes.

## Testes

```bash
pytest
```

## Regressao Operacional Rapida

Para rodar a suite curta de regressao operacional:

```powershell
./scripts/run_operational_regression.ps1
```
