# Docker Local Workers

## Objetivo

Rodar os workers do projeto localmente com Docker Compose, ainda sem broker externo e sem separar repositorios.

Esta configuracao preserva o desenho incremental:

- eventos em NDJSON
- SQLite local em volume
- logs e estado de workers em volume
- browser state em volume
- Ollama rodando no host por padrao

## Preparacao

Crie os diretorios locais usados como volumes:

```bash
mkdir -p data logs .browseruse .artifacts
```

Crie o `.env` a partir do exemplo:

```bash
cp .env.example .env
```

Ajuste pelo menos:

```env
JOB_HUNTER_TELEGRAM_TOKEN=...
JOB_HUNTER_TELEGRAM_CHAT_ID=...
JOB_HUNTER_DATABASE_PATH=/app/data/jobs.db
JOB_HUNTER_BROWSER_USE_CONFIG_DIR=/app/.browseruse
JOB_HUNTER_LINKEDIN_STORAGE_STATE_PATH=/app/.browseruse/linkedin-storage-state.json
JOB_HUNTER_FAILURE_ARTIFACTS_DIR=/app/.artifacts/linkedin_failures
JOB_HUNTER_OLLAMA_URL=http://host.docker.internal:11434
```

Se usar matching estruturado dentro da imagem, garanta que `job_target.json` exista antes do build ou monte esse arquivo explicitamente em um override local.

## Build

```bash
docker compose build
```

## Listar Workers

```bash
docker compose run --rm matching-worker python main.py worker list
```

## Rodar Coleta Uma Vez

```bash
docker compose --profile workers run --rm collector-worker
```

Isso escreve eventos em:

```text
logs/worker-events.ndjson
```

## Rodar Matching Uma Vez

```bash
docker compose --profile workers run --rm matching-worker
```

Isso lê:

```text
logs/worker-events.ndjson
```

E escreve:

```text
logs/worker-scored-events.ndjson
logs/worker-match-state.json
```

## Rodar Scheduler Sem Telegram

```bash
docker compose --profile scheduler up scheduler
```

## Rodar Bot Telegram

```bash
docker compose --profile telegram up telegram-bot
```

## Rodar Auto Apply Manualmente

```bash
docker compose --profile application run --rm application-worker
```

O auto apply continua dependente das flags e gates operacionais configurados. Nao habilite sem revisar limites, janela horaria, denylist e estado das candidaturas.

## Sessao Do LinkedIn

O container usa:

```text
.browseruse/linkedin-storage-state.json
```

Monte ou gere esse arquivo antes de depender de automacao autenticada.

O bootstrap de sessao pode exigir execucao interativa/headful e talvez seja mais simples faze-lo no host inicialmente, reaproveitando o volume `.browseruse`.

## Volumes

| Host | Container | Uso |
| --- | --- | --- |
| `./data` | `/app/data` | SQLite |
| `./logs` | `/app/logs` | NDJSON, DLQ e state dos workers |
| `./.browseruse` | `/app/.browseruse` | storage state e perfis do browser |
| `./.artifacts` | `/app/.artifacts` | screenshots/HTML de falha |

## Ollama

Por padrao o Compose aponta para:

```text
http://host.docker.internal:11434
```

Isso espera que o Ollama esteja rodando no host.

## Limites Da Fase

- sem Redis/RabbitMQ/NATS
- sem Postgres
- sem Kubernetes
- sem split de repositorios
- sem migracao ampla de banco

O objetivo e validar execucao isolada dos workers com o menor numero possivel de novas pecas operacionais.
