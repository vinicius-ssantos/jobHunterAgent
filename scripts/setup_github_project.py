#!/usr/bin/env python3
"""
Idempotent GitHub Projects V2 setup for jobHunterAgent.

Creates/updates:
- user-owned GitHub Project V2
- project single-select fields and options
- repository labels
- initial roadmap issues
- project items and project item field values
- project views via REST when supported

Requires a token with enough permission in PROJECT_PAT / GITHUB_TOKEN:
- Classic PAT: project + repo for a user-owned project/repository.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


API_VERSION = "2022-11-28"
GRAPHQL_URL = "https://api.github.com/graphql"
REST_URL = "https://api.github.com"

OWNER = os.environ.get("OWNER", "vinicius-ssantos")
REPO_NAME = os.environ.get("REPO_NAME", "jobHunterAgent")
PROJECT_TITLE = os.environ.get("PROJECT_TITLE", "Job Hunter Agent — Roadmap Operacional")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() in {"1", "true", "yes", "y"}
CREATE_ISSUES = os.environ.get("CREATE_ISSUES", "true").lower() in {"1", "true", "yes", "y"}
CREATE_VIEWS = os.environ.get("CREATE_VIEWS", "true").lower() in {"1", "true", "yes", "y"}

TOKEN = os.environ.get("PROJECT_PAT") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

PROJECT_DESCRIPTION = (
    "Roadmap operacional do Job Hunter Agent: hardening de v1, matching estruturado, "
    "validações humanas/Telegram, persistência SQLite, documentação, testes/CI e limpeza de legado."
)

STATUS_OPTIONS = [
    ("Inbox / Triage", "GRAY", "Ideias, bugs e dívida técnica ainda não classificados."),
    ("Backlog", "BLUE", "Trabalho aceito, mas ainda não priorizado para execução imediata."),
    ("Ready", "YELLOW", "Pronto para começar: escopo claro e dependências conhecidas."),
    ("In Progress", "ORANGE", "Em desenvolvimento."),
    ("Review / PR", "PURPLE", "Aguardando revisão, feedback ou merge."),
    ("Manual Validation", "PINK", "Precisa validação local, Telegram, SQLite, LinkedIn ou Ollama."),
    ("Done", "GREEN", "Concluído."),
    ("Parked / Not now", "RED", "Fora do momento ou explicitamente não prioritário."),
]

FIELDS = {
    "Status": STATUS_OPTIONS,
    "Area": [
        ("matching", "BLUE", "Matching de vagas, scoring e ranking."),
        ("collectors", "PURPLE", "Coleta de vagas e integrações de origem."),
        ("telegram-review", "GREEN", "Fluxo de revisão humana via Telegram."),
        ("applications", "ORANGE", "Fluxo assistido de candidatura."),
        ("sqlite", "YELLOW", "Persistência, histórico e estado local."),
        ("docs", "GRAY", "Documentação e checklists operacionais."),
        ("tests-ci", "PINK", "Testes, lint e CI."),
        ("architecture", "RED", "Arquitetura, limites e decisões estruturais."),
    ],
    "Priority": [
        ("P0", "RED", "Bloqueador ou risco crítico."),
        ("P1", "ORANGE", "Alta prioridade para v1."),
        ("P2", "YELLOW", "Importante, mas não bloqueante."),
        ("P3", "GRAY", "Nice-to-have ou pós-MVP."),
    ],
    "Type": [
        ("bug", "RED", "Correção de comportamento incorreto."),
        ("feature", "GREEN", "Nova capacidade do produto."),
        ("refactor", "PURPLE", "Mudança interna sem alterar contrato esperado."),
        ("docs", "BLUE", "Documentação, checklist ou guia."),
        ("test", "YELLOW", "Cobertura, lint ou pipeline de validação."),
        ("ops", "ORANGE", "Operação, release, automação ou manutenção."),
        ("debt", "GRAY", "Dívida técnica ou limpeza."),
    ],
    "Risk": [
        ("safety", "RED", "Risco de ação sensível, automação indevida ou ausência de revisão humana."),
        ("scraping", "ORANGE", "Risco de coleta, termos de uso, bloqueio ou rate limit."),
        ("data", "YELLOW", "Risco de dados locais, privacidade, duplicidade ou integridade."),
        ("llm", "PURPLE", "Risco de qualidade/controle de LLM."),
        ("legacy", "GRAY", "Risco ligado a código legado."),
        ("low", "GREEN", "Baixo risco."),
    ],
    "Size": [
        ("S", "GREEN", "Pequeno."),
        ("M", "YELLOW", "Médio."),
        ("L", "ORANGE", "Grande."),
    ],
    "Release track": [
        ("v1-hardening", "RED", "Fechamento e endurecimento operacional da v1."),
        ("structured-matching", "BLUE", "Matching estruturado e métricas de ranking."),
        ("legacy-cleanup", "GRAY", "Limpeza de código legado e redução de ambiguidade."),
        ("post-mvp", "PURPLE", "Itens fora do MVP atual."),
    ],
}

LABELS = {
    "type:bug": ("D73A4A", "Correção de bug."),
    "type:feature": ("0E8A16", "Nova funcionalidade."),
    "type:refactor": ("A371F7", "Refatoração interna."),
    "type:docs": ("0075CA", "Documentação."),
    "type:test": ("FBCA04", "Testes ou CI."),
    "type:ops": ("F9D0C4", "Operação e automação."),
    "type:debt": ("CCCCCC", "Dívida técnica."),
    "area:matching": ("1D76DB", "Matching de vagas."),
    "area:collectors": ("5319E7", "Coletores e fontes."),
    "area:telegram-review": ("0E8A16", "Revisão humana via Telegram."),
    "area:applications": ("C5DEF5", "Fluxo de candidatura."),
    "area:sqlite": ("FBCA04", "Persistência SQLite."),
    "area:docs": ("BFD4F2", "Docs e checklists."),
    "area:tests-ci": ("FAD8C7", "Testes e CI."),
    "area:architecture": ("D73A4A", "Arquitetura."),
    "priority:P0": ("B60205", "Prioridade crítica."),
    "priority:P1": ("D93F0B", "Alta prioridade."),
    "priority:P2": ("FBCA04", "Prioridade média."),
    "priority:P3": ("C2E0C6", "Baixa prioridade."),
    "risk:safety": ("B60205", "Risco de safety/human-gate."),
    "risk:scraping": ("D93F0B", "Risco de scraping/termos/rate-limit."),
    "risk:data": ("FBCA04", "Risco de dados."),
    "risk:llm": ("A371F7", "Risco de LLM."),
    "risk:legacy": ("CCCCCC", "Risco legado."),
    "track:v1-hardening": ("B60205", "Release track v1 hardening."),
    "track:structured-matching": ("1D76DB", "Release track structured matching."),
    "track:legacy-cleanup": ("CCCCCC", "Release track legacy cleanup."),
    "track:post-mvp": ("A371F7", "Release track post-MVP."),
}

ISSUES = [
    {
        "title": "Hardening v1: consolidar fluxo operacional mínimo",
        "labels": ["type:ops", "area:architecture", "priority:P0", "risk:safety", "track:v1-hardening"],
        "fields": {"Status": "Ready", "Area": "architecture", "Priority": "P0", "Type": "ops", "Risk": "safety", "Size": "M", "Release track": "v1-hardening"},
        "body": """## Objetivo

Consolidar a v1 do Job Hunter Agent como MVP local operável, com runtime claro, limites explícitos e checklist de validação.

## Escopo

- Confirmar fluxo local em `job_hunter_agent/`.
- Garantir que revisão/autorização humana continue obrigatória antes de qualquer candidatura real.
- Registrar comandos de execução e validação.
- Mapear itens que ficam fora do caminho crítico da v1.

## Critérios de aceite

- Checklist de v1 atualizado.
- Nenhum caminho de submit automático sem validação humana.
- Fluxo local reproduzível documentado.
""",
    },
    {
        "title": "Matching estruturado: normalizar scoring e explicabilidade",
        "labels": ["type:feature", "area:matching", "priority:P1", "risk:llm", "track:structured-matching"],
        "fields": {"Status": "Backlog", "Area": "matching", "Priority": "P1", "Type": "feature", "Risk": "llm", "Size": "L", "Release track": "structured-matching"},
        "body": """## Objetivo

Melhorar o matching de vagas com critérios estruturados, score rastreável e justificativa legível para revisão humana.

## Escopo

- Definir dimensões de score.
- Separar sinal determinístico de sinal LLM.
- Registrar explicação do match.
- Preparar base para comparação e regressão.

## Critérios de aceite

- Score e explicação persistidos.
- Critérios documentados.
- Casos de teste mínimos cobrindo ranking e edge cases.
""",
    },
    {
        "title": "Telegram human review: reforçar gates antes de candidatura",
        "labels": ["type:feature", "area:telegram-review", "priority:P0", "risk:safety", "track:v1-hardening"],
        "fields": {"Status": "Ready", "Area": "telegram-review", "Priority": "P0", "Type": "feature", "Risk": "safety", "Size": "M", "Release track": "v1-hardening"},
        "body": """## Objetivo

Garantir que o fluxo Telegram opere como camada explícita de revisão e autorização humana.

## Escopo

- Mensagens claras com contexto da vaga.
- Ações separadas para aprovar, rejeitar e revisar.
- Registro de decisão humana.
- Nenhuma candidatura real sem confirmação explícita.

## Critérios de aceite

- Decisão humana persistida.
- Logs/auditoria disponíveis.
- Fallback seguro em caso de erro ou timeout.
""",
    },
    {
        "title": "SQLite persistence: auditar schema e estados críticos",
        "labels": ["type:refactor", "area:sqlite", "priority:P1", "risk:data", "track:v1-hardening"],
        "fields": {"Status": "Backlog", "Area": "sqlite", "Priority": "P1", "Type": "refactor", "Risk": "data", "Size": "M", "Release track": "v1-hardening"},
        "body": """## Objetivo

Validar se o SQLite registra os estados necessários para deduplicação, histórico, auditoria e revisão humana.

## Escopo

- Revisar schema atual.
- Mapear campos obrigatórios para vagas, matches e decisões.
- Evitar duplicidade de vagas/candidaturas.
- Documentar migrações ou ajustes necessários.

## Critérios de aceite

- Estados críticos persistidos.
- Estratégia de deduplicação definida.
- Migração documentada quando aplicável.
""",
    },
    {
        "title": "Docs e checklists: atualizar operação local e limites da v1",
        "labels": ["type:docs", "area:docs", "priority:P1", "risk:low", "track:v1-hardening"],
        "fields": {"Status": "Ready", "Area": "docs", "Priority": "P1", "Type": "docs", "Risk": "low", "Size": "S", "Release track": "v1-hardening"},
        "body": """## Objetivo

Manter documentação operacional alinhada ao estado real do MVP.

## Escopo

- Comandos de setup e execução local.
- Checklist de validação manual.
- Limites explícitos: broker externo e submit automático fora do caminho crítico.
- Guia rápido para manutenção do roadmap.

## Critérios de aceite

- README/checklists atualizados.
- Fluxo de validação claro.
- Limites de safety documentados.
""",
    },
    {
        "title": "Tests/CI: criar validação mínima para fluxos críticos",
        "labels": ["type:test", "area:tests-ci", "priority:P1", "risk:low", "track:v1-hardening"],
        "fields": {"Status": "Backlog", "Area": "tests-ci", "Priority": "P1", "Type": "test", "Risk": "low", "Size": "M", "Release track": "v1-hardening"},
        "body": """## Objetivo

Adicionar validação mínima para evitar regressões nos fluxos críticos do MVP.

## Escopo

- Testes de matching e persistência.
- Testes de gates de revisão humana.
- Lint/format quando aplicável.
- Workflow CI simples.

## Critérios de aceite

- CI executa em PR.
- Testes mínimos passam.
- Falhas críticas bloqueiam merge.
""",
    },
    {
        "title": "Legacy cleanup: remover ambiguidade entre runtime atual e código legado",
        "labels": ["type:debt", "area:architecture", "priority:P2", "risk:legacy", "track:legacy-cleanup"],
        "fields": {"Status": "Backlog", "Area": "architecture", "Priority": "P2", "Type": "debt", "Risk": "legacy", "Size": "L", "Release track": "legacy-cleanup"},
        "body": """## Objetivo

Reduzir confusão entre runtime ativo, código legado e experimentos antigos.

## Escopo

- Identificar módulos legados.
- Marcar código deprecated ou remover quando seguro.
- Atualizar imports/documentação.
- Garantir que runtime ativo continue claro.

## Critérios de aceite

- Estrutura do repo mais clara.
- Código legado isolado, removido ou documentado.
- Documentação aponta para o runtime correto.
""",
    },
    {
        "title": "Post-MVP safety boundaries: documentar itens estacionados",
        "labels": ["type:docs", "area:architecture", "priority:P3", "risk:safety", "track:post-mvp"],
        "fields": {"Status": "Parked / Not now", "Area": "architecture", "Priority": "P3", "Type": "docs", "Risk": "safety", "Size": "S", "Release track": "post-mvp"},
        "body": """## Objetivo

Documentar explicitamente o que fica fora do MVP atual para evitar expansão de escopo insegura.

## Fora do caminho crítico agora

- Broker externo.
- Submit automático sem revisão/autorização humana.
- Automação agressiva em plataformas de vagas.
- Fluxos sem rastreabilidade de decisão.

## Critérios de aceite

- Itens estacionados marcados no Project.
- Riscos e motivo da decisão documentados.
""",
    },
]


class GitHubError(RuntimeError):
    pass


def log(message: str) -> None:
    print(message, flush=True)


def require_token() -> str:
    if not TOKEN:
        raise SystemExit("Missing PROJECT_PAT / GH_TOKEN / GITHUB_TOKEN. Add repository secret PROJECT_PAT before running.")
    return TOKEN


def headers() -> Dict[str, str]:
    token = require_token()
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "jobHunterAgent-project-setup",
    }


def request_json(method: str, url: str, payload: Optional[dict] = None, allow_404: bool = False) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method, headers=headers())
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        if allow_404 and exc.code == 404:
            return None
        detail = exc.read().decode("utf-8", errors="replace")
        raise GitHubError(f"{method} {url} failed: HTTP {exc.code}: {detail}") from exc


def graphql(query: str, variables: Optional[dict] = None) -> Any:
    response = request_json("POST", GRAPHQL_URL, {"query": query, "variables": variables or {}})
    if response.get("errors"):
        raise GitHubError(json.dumps(response["errors"], indent=2, ensure_ascii=False))
    return response["data"]


def rest(path: str, method: str = "GET", payload: Optional[dict] = None, allow_404: bool = False) -> Any:
    path = path if path.startswith("/") else f"/{path}"
    return request_json(method, f"{REST_URL}{path}", payload, allow_404=allow_404)


def rest_paginated(path: str) -> List[Any]:
    results: List[Any] = []
    page = 1
    separator = "&" if "?" in path else "?"
    while True:
        data = rest(f"{path}{separator}per_page=100&page={page}")
        if not isinstance(data, list) or not data:
            break
        results.extend(data)
        if len(data) < 100:
            break
        page += 1
    return results


def mutation_create_project(owner_id: str, repo_id: str) -> Dict[str, Any]:
    if DRY_RUN:
        log(f"[dry-run] Would create Project V2: {PROJECT_TITLE}")
        raise SystemExit("Dry run stopped before project creation. Re-run with dry_run=false to create resources.")

    data = graphql(
        """
        mutation($ownerId: ID!, $repoId: ID!, $title: String!) {
          createProjectV2(input: {ownerId: $ownerId, repositoryId: $repoId, title: $title}) {
            projectV2 { id number title url }
          }
        }
        """,
        {"ownerId": owner_id, "repoId": repo_id, "title": PROJECT_TITLE},
    )
    return data["createProjectV2"]["projectV2"]


def get_owner_repo_and_projects() -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    data = graphql(
        """
        query($owner: String!, $repo: String!) {
          user(login: $owner) {
            id
            databaseId
            login
            projectsV2(first: 100) {
              nodes { id number title url }
            }
          }
          repository(owner: $owner, name: $repo) {
            id
            nameWithOwner
            url
          }
        }
        """,
        {"owner": OWNER, "repo": REPO_NAME},
    )
    if not data.get("user"):
        raise SystemExit(f"Owner user not found: {OWNER}")
    if not data.get("repository"):
        raise SystemExit(f"Repository not found: {OWNER}/{REPO_NAME}")
    return data["user"], data["repository"], data["user"]["projectsV2"]["nodes"]


def get_or_create_project(owner: Dict[str, Any], repo: Dict[str, Any], projects: List[Dict[str, Any]]) -> Dict[str, Any]:
    for project in projects:
        if project["title"] == PROJECT_TITLE:
            log(f"Project already exists: #{project['number']} {project['url']}")
            return project

    log(f"Project not found. Creating: {PROJECT_TITLE}")
    project = mutation_create_project(owner["id"], repo["id"])
    log(f"Created project: #{project['number']} {project['url']}")
    return project


def update_project_description(project_id: str) -> None:
    if DRY_RUN:
        log("[dry-run] Would update project description/readme.")
        return
    graphql(
        """
        mutation($projectId: ID!, $shortDescription: String!, $readme: String!) {
          updateProjectV2(input: {
            projectId: $projectId,
            shortDescription: $shortDescription,
            readme: $readme
          }) {
            projectV2 { id title }
          }
        }
        """,
        {
            "projectId": project_id,
            "shortDescription": "Roadmap operacional do Job Hunter Agent.",
            "readme": PROJECT_DESCRIPTION,
        },
    )
    log("Updated project description/readme.")


def get_project_fields(project_id: str) -> Dict[str, Dict[str, Any]]:
    data = graphql(
        """
        query($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              fields(first: 100) {
                nodes {
                  __typename
                  ... on ProjectV2Field {
                    id
                    name
                    dataType
                  }
                  ... on ProjectV2SingleSelectField {
                    id
                    name
                    dataType
                    options { id name }
                  }
                }
              }
            }
          }
        }
        """,
        {"projectId": project_id},
    )
    nodes = data["node"]["fields"]["nodes"]
    return {field["name"]: field for field in nodes if field}


def option_inputs(options: List[Tuple[str, str, str]]) -> List[Dict[str, str]]:
    return [{"name": name, "color": color, "description": description} for name, color, description in options]


def upsert_field(project_id: str, name: str, options: List[Tuple[str, str, str]]) -> Dict[str, Any]:
    fields = get_project_fields(project_id)
    existing = fields.get(name)
    variables = {"options": option_inputs(options)}

    if existing:
        if existing["__typename"] != "ProjectV2SingleSelectField":
            log(f"Field '{name}' exists but is {existing['__typename']}; leaving unchanged.")
            return existing
        log(f"Updating field options: {name}")
        if not DRY_RUN:
            graphql(
                """
                mutation($fieldId: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
                  updateProjectV2Field(input: {fieldId: $fieldId, singleSelectOptions: $options}) {
                    projectV2Field {
                      ... on ProjectV2SingleSelectField {
                        id
                        name
                        options { id name }
                      }
                    }
                  }
                }
                """,
                {"fieldId": existing["id"], **variables},
            )
        return get_project_fields(project_id).get(name, existing)

    log(f"Creating field: {name}")
    if DRY_RUN:
        return {"id": f"dry-run-{name}", "name": name, "__typename": "ProjectV2SingleSelectField", "options": []}

    graphql(
        """
        mutation($projectId: ID!, $name: String!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
          createProjectV2Field(input: {
            projectId: $projectId,
            name: $name,
            dataType: SINGLE_SELECT,
            singleSelectOptions: $options
          }) {
            projectV2Field {
              ... on ProjectV2SingleSelectField {
                id
                name
                options { id name }
              }
            }
          }
        }
        """,
        {"projectId": project_id, "name": name, **variables},
    )
    return get_project_fields(project_id)[name]


def upsert_labels() -> None:
    for label, (color, description) in LABELS.items():
        existing = rest(f"/repos/{OWNER}/{REPO_NAME}/labels/{urllib.parse.quote(label, safe='')}", allow_404=True)
        if existing:
            log(f"Updating label: {label}")
            if not DRY_RUN:
                rest(
                    f"/repos/{OWNER}/{REPO_NAME}/labels/{urllib.parse.quote(label, safe='')}",
                    method="PATCH",
                    payload={"new_name": label, "color": color, "description": description},
                )
        else:
            log(f"Creating label: {label}")
            if not DRY_RUN:
                rest(
                    f"/repos/{OWNER}/{REPO_NAME}/labels",
                    method="POST",
                    payload={"name": label, "color": color, "description": description},
                )


def find_existing_issue(title: str) -> Optional[Dict[str, Any]]:
    issues = rest_paginated(f"/repos/{OWNER}/{REPO_NAME}/issues?state=all")
    for issue in issues:
        if issue.get("title") == title and "pull_request" not in issue:
            return issue
    return None


def upsert_issue(defn: Dict[str, Any]) -> Dict[str, Any]:
    existing = find_existing_issue(defn["title"])
    payload = {
        "title": defn["title"],
        "body": defn["body"],
        "labels": defn["labels"],
    }

    if existing:
        log(f"Updating issue: #{existing['number']} {defn['title']}")
        if not DRY_RUN:
            updated = rest(
                f"/repos/{OWNER}/{REPO_NAME}/issues/{existing['number']}",
                method="PATCH",
                payload={**payload, "state": "open"},
            )
            return updated
        return existing

    log(f"Creating issue: {defn['title']}")
    if DRY_RUN:
        return {
            "number": 0,
            "title": defn["title"],
            "node_id": "dry-run",
            "html_url": "dry-run",
        }
    return rest(f"/repos/{OWNER}/{REPO_NAME}/issues", method="POST", payload=payload)


def get_project_items(project_id: str) -> List[Dict[str, Any]]:
    data = graphql(
        """
        query($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100) {
                nodes {
                  id
                  content {
                    __typename
                    ... on Issue { id number title url }
                    ... on PullRequest { id number title url }
                  }
                }
              }
            }
          }
        }
        """,
        {"projectId": project_id},
    )
    return data["node"]["items"]["nodes"]


def add_issue_to_project(project_id: str, issue: Dict[str, Any]) -> str:
    node_id = issue.get("node_id")
    if not node_id:
        raise GitHubError(f"Issue lacks node_id: {issue}")

    for item in get_project_items(project_id):
        content = item.get("content")
        if content and content.get("id") == node_id:
            log(f"Issue already in project: #{issue['number']} {issue['title']}")
            return item["id"]

    log(f"Adding issue to project: #{issue['number']} {issue['title']}")
    if DRY_RUN:
        return "dry-run-item"
    data = graphql(
        """
        mutation($projectId: ID!, $contentId: ID!) {
          addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
            item { id }
          }
        }
        """,
        {"projectId": project_id, "contentId": node_id},
    )
    return data["addProjectV2ItemById"]["item"]["id"]


def option_id(field: Dict[str, Any], value: str) -> Optional[str]:
    for opt in field.get("options", []):
        if opt["name"] == value:
            return opt["id"]
    return None


def set_item_field(project_id: str, item_id: str, field: Dict[str, Any], value: str) -> None:
    opt_id = option_id(field, value)
    if not opt_id:
        log(f"Skipping field '{field['name']}' value '{value}' because option was not found.")
        return

    log(f"Setting {field['name']} = {value}")
    if DRY_RUN:
        return
    graphql(
        """
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
          updateProjectV2ItemFieldValue(input: {
            projectId: $projectId,
            itemId: $itemId,
            fieldId: $fieldId,
            value: { singleSelectOptionId: $optionId }
          }) {
            projectV2Item { id }
          }
        }
        """,
        {
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": field["id"],
            "optionId": opt_id,
        },
    )


def upsert_views(owner: Dict[str, Any], project: Dict[str, Any]) -> None:
    if not CREATE_VIEWS:
        log("Skipping view creation because CREATE_VIEWS=false.")
        return

    owner_id = owner["databaseId"]
    project_number = project["number"]
    path = f"/users/{owner_id}/projectsV2/{project_number}/views"

    try:
        existing_raw = rest(path)
        existing_views = existing_raw.get("value") or existing_raw.get("views") or existing_raw.get("items") or []
    except Exception as exc:
        log(f"Could not list project views; skipping view creation. Reason: {exc}")
        return

    existing_names = {view.get("name") for view in existing_views if isinstance(view, dict)}
    desired = [
        {"name": "Board operacional", "layout": "board", "filter": ""},
        {"name": "Backlog por prioridade", "layout": "table", "filter": "-status:Done"},
        {"name": "Roadmap técnico", "layout": "roadmap", "filter": "is:open"},
        {"name": "Safety / Human gates", "layout": "table", "filter": "risk:safety"},
        {"name": "Docs & checklist", "layout": "table", "filter": "type:docs"},
    ]

    for view in desired:
        if view["name"] in existing_names:
            log(f"View already exists: {view['name']}")
            continue
        log(f"Creating view: {view['name']}")
        if DRY_RUN:
            continue
        try:
            rest(path, method="POST", payload=view)
        except Exception as exc:
            log(f"Could not create view '{view['name']}'; continuing. Reason: {exc}")


def main() -> None:
    require_token()
    log(f"Owner/repo: {OWNER}/{REPO_NAME}")
    log(f"Project title: {PROJECT_TITLE}")
    log(f"Dry run: {DRY_RUN}")

    owner, repo, projects = get_owner_repo_and_projects()
    project = get_or_create_project(owner, repo, projects)
    update_project_description(project["id"])

    for field_name, options in FIELDS.items():
        upsert_field(project["id"], field_name, options)

    fields = get_project_fields(project["id"])
    upsert_labels()

    if CREATE_ISSUES:
        for issue_def in ISSUES:
            issue = upsert_issue(issue_def)
            item_id = add_issue_to_project(project["id"], issue)
            for field_name, value in issue_def["fields"].items():
                field = fields.get(field_name)
                if field:
                    set_item_field(project["id"], item_id, field, value)
                else:
                    log(f"Skipping missing field: {field_name}")
    else:
        log("Skipping issue creation because CREATE_ISSUES=false.")

    upsert_views(owner, project)

    log("Project automation finished.")
    log(project.get("url", ""))


if __name__ == "__main__":
    try:
        main()
    except GitHubError as exc:
        log(f"GitHub API error: {exc}")
        sys.exit(1)
