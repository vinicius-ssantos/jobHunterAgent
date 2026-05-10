# Admin API Local

## Objetivo

A Admin API local expõe uma interface HTTP para o futuro cockpit administrativo do Job Hunter Agent.

Nesta primeira fatia, a API é local/admin e read-only. Ela deve facilitar inspeção operacional de vagas, candidaturas, eventos e relatórios sem substituir a CLI, o Telegram ou os gates humanos do fluxo de candidatura.

Arquitetura esperada para o cockpit:

```text
React + Vite + TypeScript
  -> FastAPI Admin API
  -> servicos existentes do Job Hunter Agent
  -> SQLite local
```

## Escopo atual

A API atual expõe apenas consultas seguras sobre o estado local do agente.

Ela permite:

- verificar saúde/configuração básica da aplicação;
- consultar resumo operacional;
- listar e detalhar vagas;
- listar e detalhar candidaturas;
- consultar eventos de candidatura;
- consultar próximas ações operacionais sugeridas;
- consultar relatório operacional de coleta.

Ela não executa ações de alto impacto.

## Instalação

Na raiz do repositório:

```bash
pip install -r requirements.txt
```

As dependências da Admin API fazem parte do `requirements.txt`, incluindo FastAPI, Uvicorn e HTTPX.

## Configuração do banco local

A API usa o mesmo mecanismo de settings do runtime do Job Hunter Agent.

Para apontar a API para um banco SQLite específico, configure:

```bash
JOB_HUNTER_DATABASE_PATH=jobs.db
```

Exemplo em shell compatível com Bash:

```bash
JOB_HUNTER_DATABASE_PATH=jobs.db uvicorn job_hunter_agent.api.main:app --reload
```

Exemplo em Windows PowerShell:

```powershell
$env:JOB_HUNTER_DATABASE_PATH = "jobs.db"
uvicorn job_hunter_agent.api.main:app --reload
```

O banco SQLite é dado local do usuário. Não commite bancos reais, logs sensíveis, arquivos `.env`, storage state do LinkedIn ou perfis persistentes de browser.

## Execução local

Suba a API com:

```bash
uvicorn job_hunter_agent.api.main:app --reload
```

A documentação interativa gerada pelo OpenAPI fica em:

```text
http://localhost:8000/docs
```

A especificação OpenAPI em JSON fica em:

```text
http://localhost:8000/openapi.json
```

## Endpoints disponíveis

### Saúde e status

- `GET /api/health`
  - valida a saúde básica da aplicação local e dependências configuradas;
- `GET /api/status`
  - retorna resumo agregado de vagas e candidaturas persistidas no SQLite.

### Vagas

- `GET /api/jobs`
  - lista vagas;
  - aceita filtro opcional `status`;
  - `status=all` ou ausência de `status` retorna os estados principais disponíveis;
- `GET /api/jobs/{job_id}`
  - detalha uma vaga;
  - inclui candidatura associada, quando existir;
  - inclui eventos recentes da vaga.

Estados de vaga aceitos pelo domínio:

- `collected`
- `approved`
- `rejected`
- `error_collect`

### Candidaturas

- `GET /api/applications`
  - lista candidaturas;
  - aceita filtro opcional `status`;
  - `status=all` ou ausência de `status` retorna os estados principais disponíveis;
- `GET /api/applications/{application_id}`
  - detalha uma candidatura;
  - inclui eventos recentes da candidatura;
- `GET /api/applications/{application_id}/events`
  - lista eventos de uma candidatura;
  - aceita `limit` entre 1 e 100.

Estados de candidatura aceitos pelo domínio:

- `draft`
- `ready_for_review`
- `confirmed`
- `authorized_submit`
- `submitted`
- `error_submit`
- `cancelled`

### Operação

- `GET /api/operations/next-actions`
  - retorna próximas ações sugeridas para inspeção operacional;
  - aceita `limit` entre 1 e 100;
  - não executa nenhuma ação;
- `GET /api/operations/report`
  - retorna resumo operacional de coleta;
  - aceita `days` entre 1 e 365.

## Relação com CLI, Telegram e cockpit

A CLI continua sendo a interface operacional principal para comandos locais, revisão, transições de estado, preflight, autorização e submit real.

O Telegram continua sendo uma interface opcional de revisão assíncrona, usada para notificar vagas e receber callbacks humanos rastreáveis.

A Admin API é a borda HTTP local que permitirá ao frontend do cockpit consultar o estado operacional do agente. O frontend deve consumir somente essa API. Ele não deve chamar diretamente Playwright, MCP, Browser Use, shell, LinkedIn, Telegram, Ollama ou serviços internos.

## Limites de segurança

A fatia inicial da Admin API é deliberadamente limitada.

Ela não:

- executa Playwright;
- chama MCP;
- chama Browser Use;
- abre LinkedIn;
- chama Telegram;
- chama Ollama;
- executa preflight real;
- executa submit real;
- altera status de vagas ou candidaturas;
- substitui revisão humana;
- substitui autorização humana explícita antes de qualquer candidatura real.

Mesmo em futuras expansões, qualquer ação de alto impacto deve preservar os gates humanos documentados no projeto. Submit real continua dependendo de autorização explícita e estado compatível, nunca apenas de uma chamada do frontend.

## Decisão sobre preflight real e submit real

Preflight real e submit real ficam fora do MVP inicial da Admin API.

A API não deve expor rotas HTTP para acionar preflight real ou submit real enquanto não houver política dedicada, revisão humana explícita e proteções próprias no backend. Isso significa que o cockpit local não deve renderizar botão de submit real nem tentar chamar serviços internos diretamente para contornar a API.

Qualquer endpoint futuro que execute submit real deve exigir, no mínimo:

- candidatura no estado `authorized_submit`;
- confirmação humana explícita no momento da ação;
- readiness check antes da execução;
- auditoria persistida da decisão e do resultado;
- bloqueio seguro para captcha, login inesperado, prompts de credencial, paywall, consent screen ou qualquer prompt inesperado;
- modo dry-run ou preview quando aplicável.

Até que esses critérios sejam implementados e aprovados, tentativas de `POST` para rotas como `/api/applications/{application_id}/preflight` ou `/api/applications/{application_id}/submit` devem permanecer inexistentes e retornar 404.

## Exposição de rede

Execute a API como serviço local/admin.

Não exponha a API publicamente sem autenticação, autorização, revisão de CORS, proteção contra CSRF quando aplicável, logging seguro e hardening operacional.

Para uso local, prefira o bind padrão do Uvicorn em `127.0.0.1`.

## Exemplos rápidos

Verificar saúde:

```bash
curl http://localhost:8000/api/health
```

Consultar status:

```bash
curl http://localhost:8000/api/status
```

Listar vagas coletadas:

```bash
curl "http://localhost:8000/api/jobs?status=collected"
```

Listar candidaturas prontas para revisão:

```bash
curl "http://localhost:8000/api/applications?status=ready_for_review"
```

Consultar próximas ações:

```bash
curl "http://localhost:8000/api/operations/next-actions?limit=10"
```

Consultar relatório operacional dos últimos 7 dias:

```bash
curl "http://localhost:8000/api/operations/report?days=7"
```

## Validação local

Para validar a documentação contra o runtime atual, rode:

```bash
pytest
```

Os testes da Admin API ficam em:

```text
tests/test_admin_api.py
```

