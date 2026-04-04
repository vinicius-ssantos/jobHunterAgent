# Job Hunter Agent

MVP local para coleta, triagem e revisao humana de vagas via Telegram.

## Fonte de verdade

O runtime ativo mora no pacote `job_hunter_agent/`.

- `job_hunter_agent/settings.py`
- `job_hunter_agent/domain.py`
- `job_hunter_agent/repository.py`
- `job_hunter_agent/collector.py`
- `job_hunter_agent/notifier.py`
- `job_hunter_agent/app.py`
- `main.py` apenas como entrypoint fino

O diretorio `files/` foi removido da arquitetura ativa e nao deve ser recriado.

## Escopo da v1

- coletar vagas dos sites configurados
- avaliar aderencia ao perfil profissional com Ollama local
- persistir vagas relevantes em SQLite
- enviar vagas para revisao humana via Telegram
- registrar aprovacao ou rejeicao manual

Candidatura automatica esta fora do caminho critico desta versao.

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
- `JOB_HUNTER_REVIEW_POLLING_GRACE_SECONDS`
- `JOB_HUNTER_RELAXED_MATCHING_FOR_TESTING`
- `JOB_HUNTER_RELAXED_TESTING_PROFILE_HINT`
- `JOB_HUNTER_RELAXED_TESTING_REMOVE_EXCLUDE_KEYWORDS`
- `JOB_HUNTER_RELAXED_TESTING_MINIMUM_RELEVANCE`
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

## Observabilidade

- Cada ciclo de coleta gera logs por fonte.
- O SQLite registra vagas, logs de coleta e execucoes de coleta.
- Falhas por portal nao interrompem as demais fontes.

## Testes

```bash
pytest
```
