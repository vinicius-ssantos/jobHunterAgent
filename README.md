# Job Hunter Agent

MVP local para coleta, triagem e revisao humana de vagas via Telegram.

## Fonte de verdade

O runtime ativo mora no pacote `job_hunter_agent/`.

- `job_hunter_agent/settings.py`
- `job_hunter_agent/domain.py`
- `job_hunter_agent/repository.py`
- `job_hunter_agent/collector.py`
- `job_hunter_agent/portal_collectors.py`
- `job_hunter_agent/scoring.py`
- `job_hunter_agent/linkedin.py`
- `job_hunter_agent/notifier.py`
- `job_hunter_agent/notifier_rendering.py`
- `job_hunter_agent/review_workflow.py`
- `job_hunter_agent/composition.py`
- `job_hunter_agent/job_identity.py`
- `job_hunter_agent/app.py`
- `main.py` apenas como entrypoint fino

O diretorio `files/` foi removido da arquitetura ativa e nao deve ser recriado.

## Refatoracao incremental

Os achados arquiteturais e a ordem planejada de melhoria incremental estao em:

- `ARCHITECTURE_REFACTOR_PLAN.md`

## Escopo da v1

- coletar vagas dos sites configurados
- avaliar aderencia ao perfil profissional com Ollama local
- persistir vagas relevantes em SQLite
- enviar vagas para revisao humana via Telegram
- registrar aprovacao ou rejeicao manual

Candidatura automatica esta fora do caminho critico desta versao.

Ja existe uma pre-fase de candidatura assistida preparada na arquitetura:

- contratos em `job_hunter_agent/applicant.py`
- persistencia separada de candidaturas em `job_applications`
- criacao de rascunho quando uma vaga e aprovada no Telegram
- classificacao conservadora de suporte: `auto_supported`, `manual_review` ou `unsupported`

Isso ainda nao dispara aplicacao automatica. Serve apenas para preparar a proxima fase sem contaminar o loop atual de coleta e revisao.

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
Um `.env` local inicial pode ser criado com placeholders seguros, mas o token e o chat id do Telegram precisam ser substituidos antes do primeiro teste real.

Variaveis principais:

- `JOB_HUNTER_TELEGRAM_TOKEN`
- `JOB_HUNTER_TELEGRAM_CHAT_ID`
- `JOB_HUNTER_PROFILE_TEXT`
- `JOB_HUNTER_COLLECTION_TIME`
- `JOB_HUNTER_DATABASE_PATH`
- `JOB_HUNTER_BROWSER_USE_CONFIG_DIR`
- `JOB_HUNTER_LINKEDIN_PERSISTENT_PROFILE_DIR`
- `JOB_HUNTER_LINKEDIN_STORAGE_STATE_PATH`
- `JOB_HUNTER_BROWSER_HEADLESS`
- `JOB_HUNTER_LINKEDIN_MAX_PAGES_PER_CYCLE`
- `JOB_HUNTER_LINKEDIN_MAX_PAGE_DEPTH`
- `JOB_HUNTER_REVIEW_POLLING_GRACE_SECONDS`
- `JOB_HUNTER_RELAXED_MATCHING_FOR_TESTING`
- `JOB_HUNTER_RELAXED_TESTING_PROFILE_HINT`
- `JOB_HUNTER_RELAXED_TESTING_REMOVE_EXCLUDE_KEYWORDS`
- `JOB_HUNTER_RELAXED_TESTING_MINIMUM_RELEVANCE`
- `JOB_HUNTER_LINKEDIN_FIELD_REPAIR_ENABLED`
- `JOB_HUNTER_APPLICATION_SUPPORT_LLM_ENABLED`
- `JOB_HUNTER_JOB_REQUIREMENTS_LLM_ENABLED`
- `JOB_HUNTER_REVIEW_RATIONALE_LLM_ENABLED`
- `JOB_HUNTER_APPLICATION_PRIORITY_LLM_ENABLED`
- `JOB_HUNTER_OLLAMA_MODEL`
- `JOB_HUNTER_OLLAMA_URL`

Modelo recomendado para este MVP e para a configuracao de hardware avaliada:

- `qwen2.5:7b`

Para depuracao inicial do fluxo real, recomenda-se:

- `JOB_HUNTER_BROWSER_HEADLESS=false`

Assim a janela do navegador fica visivel durante o teste.

Para gerar mais vagas novas durante testes de parsing, voce pode ativar temporariamente:

- `JOB_HUNTER_RELAXED_MATCHING_FOR_TESTING=true`

Esse modo remove `junior` dos termos excluidos para scoring e reduz a nota minima exigida, sem alterar o comportamento padrao quando desligado.
Os knobs desse modo tambem podem ser ajustados por ambiente:

- `JOB_HUNTER_RELAXED_TESTING_PROFILE_HINT`
- `JOB_HUNTER_RELAXED_TESTING_REMOVE_EXCLUDE_KEYWORDS`
- `JOB_HUNTER_RELAXED_TESTING_MINIMUM_RELEVANCE`

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

Os cards de `/candidaturas` tambem reaproveitam os sinais estruturados ja extraidos da vaga, exibindo um resumo curto com senioridade, stack, ingles e sinais de lideranca quando houver dados uteis.

O preflight de candidatura do LinkedIn agora pode usar a pagina real da vaga, e nao apenas a URL:

- para candidaturas `confirmed`, o botao `Validar fluxo` pode abrir a vaga no navegador automatizado
- o inspetor procura sinais como `Easy Apply`, candidatura externa ou ausencia de CTA
- nesta fase, o sistema ainda nao envia candidatura real; ele apenas inspeciona e registra o fluxo encontrado

A coleta do LinkedIn tambem pode paginar de forma conservadora quando necessario:

- `JOB_HUNTER_LINKEDIN_MAX_PAGES_PER_CYCLE=2`
- `JOB_HUNTER_LINKEDIN_MAX_PAGE_DEPTH=6`
- `JOB_HUNTER_LINKEDIN_SCROLL_STABILIZATION_PASSES=3`

O recomendado para a fase atual e manter essa janela pequena por ciclo.
Cada ciclo sempre comeca pela pagina `1`, desce a pagina ate o rodape enquanto tenta esgotar a lista interna de resultados e so depois avanca pela paginacao da propria interface do LinkedIn para a pagina seguinte.

Na pratica, com `JOB_HUNTER_LINKEDIN_MAX_PAGES_PER_CYCLE=2`, o comportamento esperado por ciclo e:

- abrir a busca padrao
- estabilizar a pagina `1` com scroll ate o rodape e da lista interna
- extrair os cards visiveis da pagina `1`
- clicar na pagina `2` pela UI
- estabilizar a pagina `2` com o mesmo processo
- extrair os cards visiveis da pagina `2`

`JOB_HUNTER_LINKEDIN_MAX_PAGE_DEPTH` continua como limite de seguranca para nao aprofundar demais a navegacao dentro de um unico ciclo.

Para estabilizar a coleta no LinkedIn, o projeto pode reutilizar uma sessao autenticada local.
O perfil persistente do LinkedIn fica, por padrao, em:

- `.browseruse/profiles/linkedin-bootstrap/`

O coletor prefere um `storage_state` exportado, por padrao em:

- `.browseruse/linkedin-storage-state.json`

Fluxo recomendado:

1. Rode `python main.py --bootstrap-linkedin-session`
2. Quando o Chromium abrir, confirme que a sessao do LinkedIn esta logada
3. Pressione Enter no terminal para exportar o `storage_state`
4. Nas proximas execucoes, o coletor usa `linkedin-storage-state.json` em vez de copiar o perfil bruto

4. Inicie o Ollama local.

Se quiser um setup hibrido, esta e a parte mais natural para rodar em Docker. O browser deve continuar local neste momento para simplificar a automacao e o debug.
O `browser-use` foi ajustado para usar uma pasta local do projeto, por padrao `.browseruse/`, evitando escrita em diretorios globais do usuario.

```bash
ollama pull qwen2.5:7b
ollama serve
```

## Execucao

Rodar um ciclo imediatamente:

```bash
python main.py --agora
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

Dry-run de limpeza controlada de jobs antigos poluidos:

```bash
python scripts/cleanup_legacy_jobs.py --before-id 15
```

Aplicar a limpeza somente em vagas antigas ainda `collected`:

```bash
python scripts/cleanup_legacy_jobs.py --before-id 15 --apply
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
  - `Preparar` move `draft -> ready_for_review`
  - `Confirmar` move `ready_for_review -> confirmed`
  - `Validar fluxo` executa um preflight manual em candidaturas `confirmed`
  - `Cancelar` move o rascunho para `cancelled`

## Observabilidade

- Cada ciclo de coleta gera logs por fonte.
- O SQLite registra vagas, logs de coleta e execucoes de coleta.
- Falhas por portal nao interrompem as demais fontes.

## Pre-fase de candidatura assistida

O projeto agora possui a base estrutural para uma fase futura de candidatura assistida, sem ativar submissao automatica ainda.

Estados de candidatura ficam separados dos estados de vaga:

- `draft`
- `ready_for_review`
- `confirmed`
- `submitted`
- `error_submit`
- `cancelled`

Esses estados vivem em uma tabela separada (`job_applications`) para evitar misturar revisao humana de vaga com tentativa de candidatura.

Cada rascunho de candidatura tambem recebe uma classificacao de suporte:

- `auto_supported`
- `manual_review`
- `unsupported`

No estado atual, essa classificacao e conservadora e serve para filtrar o que pode entrar numa futura automacao, sem ainda disparar submissao real.

Depois da confirmacao humana, a candidatura tambem pode passar por um `preflight` manual.
Esse preflight:

- nao envia candidatura
- valida se o fluxo esta num portal minimamente suportado
- registra sucesso mantendo `confirmed`
- ou registra bloqueio em `error_submit` quando o fluxo nao e suportado

## Como adicionar um novo adapter

1. Defina um `SiteConfig` novo em `Settings` ou no ambiente, com `name` e `search_url`.
2. Crie um adapter pequeno em `job_hunter_agent/portal_collectors.py` implementando o contrato `PortalCollectorAdapter`.
3. Faça o adapter:
   - responder `supports(site)`
   - construir o task em `build_task(...)`
   - converter o payload em `RawJob` em `normalize(...)`
4. Se o portal precisar de fluxo mais confiavel que o agent genérico, prefira um coletor determinístico separado, como o LinkedIn.
5. Registre o adapter na tupla `portal_adapters` de `BrowserUseSiteCollector` em `job_hunter_agent/portal_collectors.py`.
6. Adicione testes cobrindo:
   - `supports`
   - `normalize`
   - `RawJob` minimo valido
   - falha isolada do portal

Checklist mínimo do `RawJob`:

- `title`
- `company`
- `url`
- `source_site`

Os demais campos podem usar fallback textual controlado, mas nao devem ser inventados.

## Testes

```bash
pytest
```
