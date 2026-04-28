# V1 Hardening Checklist

## Objetivo

Consolidar a v1 do Job Hunter Agent como MVP local operavel, com runtime claro, revisao humana obrigatoria antes de acoes criticas e checklist de validacao reproduzivel.

Este checklist e a referencia operacional para a issue #64.

## Fonte De Verdade Do Runtime

- [x] Runtime ativo esta em `job_hunter_agent/`.
- [x] `main.py` funciona como entrypoint fino.
- [x] `files/` nao deve ser recriado como arquitetura ativa.
- [x] README aponta para os guias operacionais atuais.
- [x] Dados locais e artefatos seguem `docs/DATA_CONTRACT.md`.

## Fluxo Operacional Minimo Da V1

Fluxo principal:

```text
coletar -> normalizar -> ranquear -> persistir -> notificar -> revisar
```

Fluxo assistido de candidatura:

```text
aprovar vaga -> criar candidatura -> preparar -> confirmar -> preflight -> autorizar -> submit controlado
```

Estados criticos de candidatura:

```text
draft -> ready_for_review -> confirmed -> authorized_submit -> submitted
```

Estados de bloqueio/erro devem permanecer diagnosticaveis via:

```bash
python main.py applications diagnose --id <application_id>
```

## Validacao Local Basica

### Setup

```bash
pip install -r requirements.txt
```

PowerShell/Windows:

```powershell
.\scripts\setup_playwright.ps1
$env:PLAYWRIGHT_BROWSERS_PATH=".playwright-browsers"
```

### Testes

```bash
pytest
```

### Execucao Sem Telegram

```bash
python main.py --agora --sem-telegram
```

### Ciclos Finitos

```bash
python main.py --ciclos 3 --intervalo-ciclos-segundos 60
```

### Status Geral

```bash
python main.py status
```

## Checklist De Review Humana

Antes de qualquer candidatura real:

- [ ] A vaga foi revisada por humano.
- [ ] A vaga foi aprovada intencionalmente.
- [ ] A candidatura existe como `draft` ou avancou por estados esperados.
- [ ] `applications diagnose` foi consultado quando houve duvida.
- [ ] Preflight foi executado antes de submit real.
- [ ] A candidatura foi autorizada explicitamente antes de submit real.
- [ ] O operador sabe qual portal e suporte operacional estao envolvidos.

Comandos de referencia:

```bash
python main.py jobs list --status collected
python main.py jobs approve --id <job_id>
python main.py applications create --job-id <job_id>
python main.py applications prepare --id <application_id>
python main.py applications confirm --id <application_id>
python main.py applications preflight --id <application_id> --dry-run
python main.py applications authorize --id <application_id>
python main.py applications submit --id <application_id> --dry-run
python main.py applications diagnose --id <application_id>
```

## Gates De Safety Da V1

- [x] Submit real sem revisao humana fica fora do caminho critico.
- [x] Submit real exige autorizacao explicita.
- [x] Mesmo com `JOB_HUNTER_AUTO_EASY_APPLY_ENABLED=true`, submit real so deve considerar candidaturas em `authorized_submit`.
- [x] Candidaturas `confirmed` ainda exigem autorizacao humana antes de submissao.
- [x] `--dry-run` deve ser preferido para validacao operacional.
- [x] Bloqueios como `preflight_not_ready`, `portal_not_supported`, `readiness_incomplete`, `submit_unavailable`, `applicant_error` e `error_submit` nao devem ser ignorados.
- [x] LLM nao autoriza submit, nao pula preflight e nao substitui revisao humana.

## Observabilidade Minima

- [x] SQLite e fonte principal para vaga, candidatura, status e historico operacional.
- [x] Domain-events podem ser habilitados como trilha complementar.
- [x] Diagnostico por candidatura agrega estado, vaga, eventos recentes e proxima acao recomendada.
- [x] README documenta execucao, setup e principais variaveis.

Comandos uteis:

```bash
python main.py status
python main.py applications diagnose --id <application_id>
python main.py domain-events list --correlation-id application:<application_id> --limit 20
```

## Itens Fora Do Caminho Critico Da V1

Os itens abaixo ficam estacionados fora do MVP local atual:

- broker externo;
- Postgres como substituto do SQLite;
- submit automatico sem revisao/autorizacao humana;
- automacao agressiva em plataformas de vagas;
- batch de submit real;
- dashboard/TUI mutavel;
- CV/PDF ou cover letter enviados automaticamente;
- conversao em massa de timestamps SQLite legados.

Esses itens podem ser planejados, mas nao devem ser tratados como requisito para considerar a v1 operavel.

## Checklist De Pronto Da V1

A v1 pode ser considerada operacionalmente pronta quando:

- [ ] `pytest` passa em ambiente local ou CI.
- [ ] Docker/Compose valida quando aplicavel.
- [ ] `python main.py --agora --sem-telegram` executa sem erro bloqueante.
- [ ] `python main.py status` mostra estado geral.
- [ ] Uma vaga pode ser revisada/aprovada de forma rastreavel.
- [ ] Uma candidatura pode ser diagnosticada por `applications diagnose`.
- [ ] Preflight pode ser executado em `--dry-run`.
- [ ] Nenhum caminho documentado permite submit real sem autorizacao humana.

## Proximas Issues Relacionadas

- #65 Matching estruturado: normalizar scoring e explicabilidade.
- #66 Telegram human review: reforcar gates antes de candidatura.
- #67 SQLite persistence: auditar schema e estados criticos.
- #68 Docs e checklists: atualizar operacao local e limites da v1.
- #69 Tests/CI: criar validacao minima para fluxos criticos.
- #70 Legacy cleanup: remover ambiguidade entre runtime atual e codigo legado.
- #71 Post-MVP safety boundaries: documentar itens estacionados.
