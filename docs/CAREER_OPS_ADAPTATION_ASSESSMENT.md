# Avaliacao de Adaptacoes do Career-Ops para o Job Hunter Agent

## Objetivo

Este documento compara o projeto `jobHunterAgent` com o projeto `career-ops` e avalia quais ideias, funcoes e features do `career-ops` fazem sentido adaptar para o `jobHunterAgent`.

A analise parte da premissa de que os dois projetos pertencem ao mesmo dominio funcional — busca, triagem e apoio a candidaturas de emprego — mas possuem naturezas diferentes:

- `jobHunterAgent` e uma aplicacao local-first com runtime persistente, SQLite, coleta automatica, revisao humana por CLI/Telegram e fluxo controlado de candidatura.
- `career-ops` e um sistema operacional de carreira orientado a agentes, documentos, prompts, artefatos de candidatura, avaliacao rica de ofertas, geracao de CV/PDF e tracking em arquivos.

A recomendacao geral e aproveitar o `career-ops` como referencia de produto, workflow e templates, sem acoplar diretamente sua implementacao ao runtime do `jobHunterAgent`.

---

## Fontes analisadas

### `jobHunterAgent`

Arquivos e areas relevantes:

- `README.md`
- `AGENTS.md`
- `docs/ARQUITETURA_DO_PROJETO.md`
- `docs/APPLICATION_OPERATIONS.md`
- `job_hunter_agent/core/matching.py`
- `job_hunter_agent/core/matching_prompt.py`
- `job_hunter_agent/core/candidate_profile.py`
- `job_hunter_agent/application/app.py`
- `job_hunter_agent/application/application_preparation.py`
- `job_hunter_agent/application/application_submission.py`
- `job_hunter_agent/application/auto_easy_apply.py`
- `job_hunter_agent/application/application_queries.py`
- `requirements.txt`

### `career-ops`

Arquivos e areas relevantes:

- `README.md`
- `AGENTS.md`
- `DATA_CONTRACT.md`
- `modes/_shared.md`
- `modes/oferta.md`
- `modes/pdf.md`
- `modes/auto-pipeline.md`
- `modes/pipeline.md`
- `modes/scan.md`
- `modes/batch.md`
- `modes/tracker.md`
- `extract-jd.mjs`
- `scan-portals.mjs`
- `generate-pdf.mjs`
- `package.json`

---

## Sumario executivo

Sim, o `jobHunterAgent` se beneficiaria de features do `career-ops`, especialmente nas etapas posteriores a triagem da vaga.

O `jobHunterAgent` ja possui uma base operacional mais forte para:

- coleta e normalizacao de vagas;
- scoring assistido por LLM local;
- persistencia em SQLite;
- revisao humana;
- transicoes de candidatura;
- preflight;
- submit controlado;
- eventos de dominio;
- diagnostico operacional.

O `career-ops`, por outro lado, e mais forte em:

- avaliacao detalhada de uma oferta;
- geracao de relatorios ricos;
- adaptacao de CV por vaga;
- geracao de PDF ATS-friendly;
- plano de candidatura;
- plano de entrevista;
- tracking orientado a artefatos;
- pipeline manual de URLs/JDs;
- processamento em lote;
- separacao entre camada do sistema e camada do usuario.

A melhor estrategia nao e substituir partes centrais do `jobHunterAgent`, mas sim adaptar funcionalidades do `career-ops` como novos servicos dentro da arquitetura Python existente.

---

## Diferenca de natureza entre os projetos

### `jobHunterAgent`: runtime operacional

O `jobHunterAgent` e uma aplicacao que roda ciclos, coleta vagas, aplica filtros, persiste dados e executa operacoes de candidatura com estado.

Seu fluxo principal declarado e:

```text
coletar -> normalizar -> ranquear -> persistir -> notificar -> revisar
```

Seu fluxo de candidatura segue uma maquina de estados segura:

```text
draft -> ready_for_review -> confirmed -> authorized_submit -> submitted
```

Essa escolha e adequada para automacao local com risco operacional, especialmente porque o projeto trata candidatura real como uma acao de alto impacto.

Pontos fortes do `jobHunterAgent`:

- fonte de verdade transacional em SQLite;
- contratos de dominio mais explicitos;
- separacao entre `core`, `application`, `collectors`, `infrastructure` e `llm`;
- gates humanos antes de acoes criticas;
- CLI e Telegram como interfaces de revisao;
- preflight e submit separados;
- bloqueios conservadores;
- logs, eventos e diagnostico operacional;
- uso de LLM como apoio, nao como fonte unica de verdade.

### `career-ops`: sistema operacional de candidatura

O `career-ops` organiza a busca por emprego como um pipeline assistido por agente.

Seu foco esta menos em runtime persistente e mais em artefatos e workflows:

- avaliar uma oferta de forma profunda;
- gerar relatorio Markdown;
- adaptar CV para uma vaga;
- gerar PDF ATS;
- atualizar tracker;
- preparar respostas para formulario;
- preparar historias STAR+R para entrevista;
- rodar scans e batches.

Pontos fortes do `career-ops`:

- experiencia de usuario mais rica apos encontrar uma vaga;
- prompts e modos bem definidos;
- geracao de documentos finais;
- orientacao a decision-making humano;
- forte foco em qualidade da candidatura;
- separacao clara entre dados do usuario e arquivos do sistema;
- fluxo completo de URL/JD ate relatorio/PDF/tracker.

---

## Comparacao por area funcional

| Area | `jobHunterAgent` | `career-ops` | Avaliacao |
|---|---|---|---|
| Descoberta de vagas | Coletores e LinkedIn integrados ao runtime | Scanner configuravel via `portals.yml`, APIs e Playwright | O `jobHunterAgent` deve manter seus coletores, mas pode aproveitar heuristicas de liveness e ingestao manual. |
| Matching/scoring | Scoring 1-10, prefiltro, matching estruturado, Ollama local | Score 1-5 com avaliacao rica em blocos | Vale adaptar o relatorio A-F como camada posterior ao scoring. |
| Persistencia | SQLite como fonte de verdade | Markdown, TSV e arquivos locais | Manter SQLite. Nao substituir por tracker Markdown. |
| Revisao humana | CLI e Telegram | Human-in-the-loop via agente e arquivos | O `jobHunterAgent` ja tem melhor base para revisao operacional. |
| Candidatura | Draft, preflight, autorizacao e submit controlado | Gera plano, respostas e materiais; nao submete automaticamente | Combinar: `career-ops` prepara material, `jobHunterAgent` controla estado e submit. |
| Geracao de CV/PDF | Nao aparece como feature central | Pipeline ATS com HTML/PDF via Playwright | Alto valor para adaptar. |
| Relatorios | Diagnostico operacional e eventos | Relatorios ricos por oferta | Alto valor para adaptar. |
| Entrevista | Nao aparece como feature central | Story Bank e STAR+R | Valor medio/alto para candidaturas aprovadas. |
| Pipeline manual | Nao aparece como fluxo principal | `data/pipeline.md` para URLs/JDs | Valor alto, mas deve ser implementado em SQLite/CLI. |
| Batch | Ciclos finitos e coleta | Batch de ofertas com resumabilidade | Valor medio. Adaptar apenas avaliacao/preparacao, nao submit. |
| Dashboard | CLI/Telegram | Dashboard TUI em Go | Valor medio, depois dos artefatos. |
| Contrato de dados | Settings e SQLite | Data Contract user/system | Valor alto como convencao de produto. |

---

## Features do `career-ops` recomendadas para adaptacao

## 1. Relatorio detalhado de avaliacao da vaga

### Feature no `career-ops`

O modo `oferta` define uma avaliacao completa em blocos:

- A: resumo do papel;
- B: match com CV;
- C: nivel e estrategia;
- D: compensacao e demanda;
- E: plano de personalizacao;
- F: plano de entrevistas;
- G: draft de respostas, quando a vaga tem score alto.

### Lacuna no `jobHunterAgent`

O `jobHunterAgent` ja tem scoring e rationale curta, mas a decisao humana se beneficiaria de um relatorio mais explicativo.

Atualmente, o scoring e suficiente para filtrar, mas nao necessariamente para responder:

- por que essa vaga vale aplicar;
- quais requisitos batem com o perfil;
- quais gaps existem;
- qual narrativa usar;
- quais pontos destacar no CV;
- quais perguntas de entrevista preparar.

### Adaptacao recomendada

Criar um servico em Python:

```text
job_hunter_agent/application/application_evaluation_report.py
```

Responsabilidades:

- receber uma vaga aprovada ou candidatura draft;
- ler perfil estruturado do candidato;
- ler curriculo/base de experiencias, se configurado;
- gerar relatorio Markdown e, opcionalmente, JSON estruturado;
- persistir referencia do relatorio na candidatura ou em tabela de artefatos.

### Possivel contrato de saida

```json
{
  "application_id": 123,
  "job_id": 456,
  "company": "Acme",
  "role": "Senior Backend Engineer",
  "score": 8,
  "recommendation": "apply",
  "archetype": "backend/platform",
  "report_path": "artifacts/reports/application-123.md",
  "blocks": {
    "summary": "...",
    "cv_match": [],
    "gaps": [],
    "strategy": "...",
    "interview_plan": []
  }
}
```

### Prioridade

Alta.

### Risco

Baixo a medio, desde que o relatorio seja apenas artefato informativo e nao altere gates de candidatura.

### Criterios de aceite

- O comando gera relatorio para uma vaga aprovada.
- O relatorio nao altera status automaticamente.
- Falha na geracao do relatorio nao quebra candidatura.
- O relatorio fica rastreavel por `job_id` ou `application_id`.
- O conteudo diferencia fatos da vaga, inferencias e recomendacoes.

---

## 2. Geracao de CV ATS por vaga

### Feature no `career-ops`

O modo `pdf` define um pipeline para gerar CV adaptado a cada JD:

- extrair keywords da vaga;
- detectar idioma;
- escolher formato `letter` ou `a4`;
- adaptar Professional Summary;
- selecionar projetos relevantes;
- reordenar bullets;
- montar grade de competencias;
- gerar HTML;
- renderizar PDF com Playwright;
- normalizar caracteres para ATS.

### Lacuna no `jobHunterAgent`

O `jobHunterAgent` apoia candidatura, mas nao parece ter uma camada forte de geracao de documentos personalizados.

Isso limita o valor apos a aprovacao da vaga: o sistema decide que a vaga e boa, mas nao necessariamente entrega o pacote de candidatura.

### Adaptacao recomendada

Criar:

```text
job_hunter_agent/application/application_document_generation.py
job_hunter_agent/core/document_templates.py
job_hunter_agent/infrastructure/pdf_renderer.py
```

Ou, em uma primeira etapa, usar geracao Markdown/HTML simples antes de PDF.

### Decisao tecnica

O `jobHunterAgent` ja usa Python e Playwright. Existem duas opcoes:

1. Portar a geracao para Python com Playwright.
2. Manter um script Node isolado inspirado em `generate-pdf.mjs`.

A opcao 1 e mais coerente arquiteturalmente.

### Cuidados essenciais

- Nao inventar experiencias ou skills.
- Nunca sobrescrever o CV original do usuario.
- Gerar sempre um artefato novo por vaga/candidatura.
- Marcar claramente que o CV foi gerado para revisao humana.
- Nao enviar automaticamente sem confirmacao.

### Prioridade

Alta.

### Risco

Medio, porque documentos de candidatura impactam reputacao do candidato. Deve ser tratado como artefato revisavel.

### Criterios de aceite

- A partir de uma candidatura draft, gerar um HTML ou PDF.
- O PDF deve ser salvo em `artifacts/cv/` ou diretorio equivalente.
- O caminho do arquivo deve ser associado a candidatura.
- O usuario deve conseguir revisar o arquivo antes de qualquer submit.
- O gerador deve registrar warnings quando nao houver dados suficientes.

---

## 3. Cover letter e respostas de formulario

### Feature no `career-ops`

O `career-ops` gera respostas para perguntas de candidatura quando a vaga tem score alto. Tambem recomenda incluir cover letter quando o formulario permite.

### Lacuna no `jobHunterAgent`

O `jobHunterAgent` possui fluxo de candidatura e suporte a perguntas conhecidas do candidato, mas pode se beneficiar de um gerador de respostas contextualizadas por vaga.

### Adaptacao recomendada

Adicionar artefatos opcionais:

```text
artifacts/answers/application-123.md
artifacts/cover_letters/application-123.md
artifacts/cover_letters/application-123.pdf
```

Criar servico:

```text
job_hunter_agent/application/application_answer_generation.py
```

### Regras recomendadas

- Usar somente informacoes confirmadas no perfil/curriculo.
- Separar resposta sugerida de resposta confirmada.
- Nunca preencher campo sensivel sem revisao.
- Telefone e dados pessoais devem obedecer settings existentes.
- Toda resposta deve poder ser editada antes do envio.

### Prioridade

Media/alta.

### Risco

Medio.

### Criterios de aceite

- Gerar respostas sugeridas para perguntas detectadas em preflight.
- Marcar perguntas sem informacao suficiente como `requires_human_input`.
- Persistir as sugestoes como artefato associado a candidatura.
- Nao mudar status da candidatura automaticamente.

---

## 4. Pipeline manual de URLs e JDs

### Feature no `career-ops`

O modo `pipeline` permite acumular URLs ou JDs locais em `data/pipeline.md` e processar depois.

### Lacuna no `jobHunterAgent`

A descoberta automatica nao cobre todos os casos. Muitas vagas interessantes aparecem por:

- LinkedIn salvo manualmente;
- recomendacao de conhecidos;
- email de recruiter;
- postagem em comunidade;
- arquivo local com JD copiado;
- paginas com login ou conteudo bloqueado.

### Adaptacao recomendada

Implementar uma fila de ingestao manual em SQLite.

Comandos sugeridos:

```bash
python main.py pipeline add --url "https://..."
python main.py pipeline add --jd-file jds/acme-role.md
python main.py pipeline list
python main.py pipeline process --limit 10
python main.py pipeline retry-failed
```

### Modelo de dados sugerido

Tabela `job_pipeline_items`:

| Campo | Tipo | Observacao |
|---|---|---|
| `id` | integer | PK |
| `source_type` | text | `url`, `local_file`, `raw_text` |
| `source_value` | text | URL, path ou hash |
| `company_hint` | text | opcional |
| `role_hint` | text | opcional |
| `status` | text | `pending`, `processing`, `processed`, `failed`, `skipped` |
| `job_id` | integer | FK opcional para vaga criada |
| `error` | text | ultimo erro |
| `created_at` | text | UTC |
| `updated_at` | text | UTC |

### Prioridade

Alta.

### Risco

Baixo/medio.

### Criterios de aceite

- Inserir uma URL manualmente.
- Processar URL em vaga normalizada.
- Deduplicar contra vagas existentes.
- Registrar erro sem abortar a fila inteira.
- Permitir reprocessamento controlado.

---

## 5. Extracao de JD e verificacao de vaga ativa

### Feature no `career-ops`

O script `extract-jd.mjs` usa Playwright para:

- abrir a URL;
- extrair texto principal;
- detectar sinais de vaga expirada;
- detectar sinais de apply;
- inferir empresa;
- salvar Markdown.

### Lacuna no `jobHunterAgent`

Os coletores do `jobHunterAgent` podem se beneficiar de uma camada reutilizavel de extracao/verificacao, especialmente para URLs manuais e fallback de portais.

### Adaptacao recomendada

Criar:

```text
job_hunter_agent/collectors/job_description_extractor.py
job_hunter_agent/collectors/job_liveness.py
```

Responsabilidades:

- extrair titulo, empresa, descricao e URL final;
- classificar `active`, `expired`, `uncertain`;
- retornar motivo da classificacao;
- padronizar heuristicas de vagas encerradas;
- gerar artifact de debugging quando falhar.

### Prioridade

Media/alta.

### Risco

Medio, porque heuristicas podem gerar falso positivo/negativo.

### Criterios de aceite

- URL ativa gera `RawJob` ou DTO equivalente.
- URL expirada nao entra como vaga relevante.
- Resultado incerto pode ser enviado para revisao humana.
- Falha de extracao nao interrompe outras vagas.

---

## 6. Data Contract: camada do usuario vs camada do sistema

### Feature no `career-ops`

O `DATA_CONTRACT.md` separa arquivos do usuario, que nunca devem ser sobrescritos, de arquivos do sistema, que podem evoluir.

### Lacuna no `jobHunterAgent`

O `jobHunterAgent` ja tem settings e SQLite, mas uma documentacao formal de dados do usuario ajudaria a evitar regressao futura.

### Adaptacao recomendada

Criar um documento proprio:

```text
docs/DATA_CONTRACT.md
```

Sugestao de classificacao:

#### Camada do usuario

- `.env`
- `job_target.json`
- arquivo de perfil do candidato
- curriculo original
- banco SQLite local
- artifacts gerados
- storage state do LinkedIn
- perfil persistente de browser
- logs locais sensiveis

#### Camada do sistema

- codigo em `job_hunter_agent/`
- templates versionados
- docs operacionais
- testes
- scripts
- `.env.example`
- exemplos como `job_target.example.json`

### Prioridade

Alta.

### Risco

Baixo.

### Criterios de aceite

- Documento lista arquivos que nunca devem ser sobrescritos.
- Documento orienta futuras migracoes.
- README referencia o contrato.
- Mudancas futuras em dados pessoais devem respeitar o contrato.

---

## 7. Story Bank e plano de entrevistas

### Feature no `career-ops`

O modo `oferta` gera historias STAR+R mapeadas aos requisitos da vaga e acumula um banco reutilizavel de historias.

### Lacuna no `jobHunterAgent`

O fluxo atual parece mais focado em candidatura do que preparacao para entrevista.

### Adaptacao recomendada

Criar artefatos:

```text
artifacts/interview/application-123.md
candidate/story_bank.json
```

Servico:

```text
job_hunter_agent/application/interview_preparation.py
```

### Regras recomendadas

- Diferenciar historia confirmada de historia sugerida.
- Nunca inventar metricas.
- Permitir que o usuario aprove ou edite historias.
- Reutilizar experiencias confirmadas do perfil do candidato.

### Prioridade

Media.

### Risco

Medio, por risco de alucinacao se nao houver dados suficientes.

### Criterios de aceite

- Gerar plano de entrevista para candidatura aprovada.
- Marcar gaps de informacao.
- Salvar em artefato revisavel.
- Nao alterar status de candidatura.

---

## 8. Batch de avaliacao/preparacao

### Feature no `career-ops`

O modo `batch` processa varias ofertas com estado, retries, logs e outputs independentes.

### Lacuna no `jobHunterAgent`

O `jobHunterAgent` ja roda ciclos, mas pode se beneficiar de batch manual para URLs/JDs acumulados.

### Adaptacao recomendada

Adicionar batch apenas para etapas seguras:

- extracao de JD;
- normalizacao;
- scoring;
- relatorio;
- geracao de artefatos.

Nao usar batch para:

- preflight real em massa;
- autorizacao;
- submit;
- alteracao automatica de status critico.

### Prioridade

Media.

### Risco

Medio.

### Criterios de aceite

- Processar N itens pendentes sem abortar no primeiro erro.
- Registrar sucesso/falha por item.
- Nao executar submit.
- Ter limite de concorrencia configuravel.

---

## 9. Dashboard/TUI

### Feature no `career-ops`

O `career-ops` possui um dashboard terminal para visualizar e filtrar pipeline.

### Lacuna no `jobHunterAgent`

O `jobHunterAgent` possui CLI e Telegram, mas uma TUI poderia melhorar a operacao local.

### Adaptacao recomendada

Postergar ate que relatorios e artefatos estejam consolidados.

Uma TUI futura poderia mostrar:

- vagas coletadas;
- fila de revisao;
- candidaturas por status;
- relatorios disponiveis;
- PDFs gerados;
- ultimos eventos de dominio;
- falhas de preflight/submit;
- proximas acoes recomendadas.

### Prioridade

Baixa/media.

### Risco

Baixo, desde que seja read-only inicialmente.

---

## Features que nao devem ser adaptadas diretamente

## 1. Tracker Markdown como fonte principal

O `career-ops` usa `data/applications.md` como tracker. Isso e util para workflows com agentes e arquivos, mas o `jobHunterAgent` ja tem SQLite.

Recomendacao:

- nao substituir SQLite;
- se necessario, criar export Markdown/CSV a partir do SQLite;
- manter SQLite como fonte operacional.

## 2. Submissao automatica ampla

O `career-ops` reforca que o usuario decide e submete. O `jobHunterAgent` ja possui fluxo de submit controlado.

Recomendacao:

- nao ampliar auto-submit com base nas ideias do `career-ops`;
- manter `authorized_submit` como requisito;
- manter preflight obrigatorio;
- manter limites, denylist e circuit breakers.

## 3. Dependencia direta dos scripts Node

O `career-ops` e Node/Go/Markdown. O `jobHunterAgent` e Python/SQLite.

Recomendacao:

- evitar dependencias diretas em `.mjs` no runtime principal;
- portar ideias para Python quando fizer sentido;
- aceitar subprocessos externos apenas como etapa transitoria ou experimental.

## 4. Prompts como unica regra de negocio

O `career-ops` usa modos Markdown como logica operacional para agentes. No `jobHunterAgent`, regras criticas devem continuar em codigo, policies e contratos.

Recomendacao:

- prompts podem gerar relatorios e artefatos;
- prompts nao devem controlar transicoes criticas;
- prompts nao devem autorizar submit;
- prompts nao devem sobrescrever dados do usuario.

---

## Roadmap recomendado

## Fase 1 — Documentacao e contratos

Objetivo: preparar terreno sem alterar runtime.

Tarefas:

1. Criar `docs/DATA_CONTRACT.md`.
2. Documentar diretorios de artefatos.
3. Definir convencao de nomes para relatorios, CVs, cover letters e respostas.
4. Atualizar README com visao de artefatos futuros.

Risco: baixo.

## Fase 2 — Relatorio A-F por candidatura

Objetivo: enriquecer decisao humana.

Tarefas:

1. Criar `ApplicationEvaluationReportService`.
2. Criar prompt/template de relatorio.
3. Gerar Markdown em `artifacts/reports/`.
4. Adicionar comando CLI:

```bash
python main.py applications report --id <application_id>
```

5. Associar o caminho do relatorio a candidatura.
6. Adicionar testes unitarios para casos sem curriculo, sem descricao e sem LLM.

Risco: baixo/medio.

## Fase 3 — Pipeline manual de URLs/JDs

Objetivo: permitir entrada manual no fluxo.

Tarefas:

1. Criar tabela `job_pipeline_items`.
2. Criar comandos `pipeline add/list/process`.
3. Usar extrator de JD para URLs.
4. Deduplicar contra vagas existentes.
5. Converter item processado em vaga normalizada.

Risco: medio.

## Fase 4 — Extrator de JD e liveness

Objetivo: melhorar qualidade de entrada.

Tarefas:

1. Portar heuristicas do `extract-jd.mjs` para Python.
2. Detectar `active`, `expired`, `uncertain`.
3. Criar testes com HTML fixtures.
4. Integrar ao pipeline manual.
5. Opcionalmente integrar aos coletores existentes.

Risco: medio.

## Fase 5 — Geracao de CV/cover letter

Objetivo: transformar candidatura aprovada em pacote revisavel.

Tarefas:

1. Definir fonte de verdade do CV original.
2. Criar templates HTML versionados.
3. Criar gerador de HTML.
4. Criar renderer PDF com Playwright.
5. Criar comando:

```bash
python main.py applications documents --id <application_id>
```

6. Registrar artefatos gerados.
7. Exigir revisao humana antes de usar em submit.

Risco: medio/alto.

## Fase 6 — Story Bank e entrevista

Objetivo: apoiar pos-candidatura.

Tarefas:

1. Criar formato de `story_bank`.
2. Criar gerador de plano STAR+R por candidatura.
3. Permitir aprovar/editar historias.
4. Associar plano a candidatura.

Risco: medio.

## Fase 7 — TUI/Dashboard

Objetivo: melhorar operacao local.

Tarefas:

1. Comecar read-only.
2. Ler SQLite.
3. Mostrar status e proximas acoes.
4. Abrir relatorios/artefatos.
5. Somente depois avaliar acoes mutaveis.

Risco: baixo/medio.

---

## Arquitetura proposta para artefatos

Diretorios sugeridos:

```text
artifacts/
  reports/
    application-123.md
  cv/
    application-123.html
    application-123.pdf
  cover_letters/
    application-123.md
    application-123.pdf
  answers/
    application-123.md
  interview/
    application-123.md
  extraction/
    pipeline-item-456.md
```

Tabela opcional:

```text
application_artifacts
```

Campos sugeridos:

| Campo | Tipo | Observacao |
|---|---|---|
| `id` | integer | PK |
| `application_id` | integer | FK |
| `job_id` | integer | FK opcional |
| `artifact_type` | text | `report`, `cv_pdf`, `cover_letter`, `answers`, `interview_plan`, `extraction` |
| `path` | text | caminho local |
| `status` | text | `generated`, `failed`, `superseded` |
| `metadata_json` | text | dados auxiliares |
| `created_at` | text | UTC |

Vantagens:

- preserva SQLite como fonte de verdade operacional;
- evita parsear nomes de arquivos;
- permite historico de artefatos;
- facilita diagnostico;
- permite regenerar sem perder versoes anteriores.

---

## Comandos CLI sugeridos

```bash
# Relatorios
python main.py applications report --id <application_id>
python main.py applications report --id <application_id> --force

# Documentos
python main.py applications documents --id <application_id>
python main.py applications cv --id <application_id>
python main.py applications cover-letter --id <application_id>

# Respostas
python main.py applications answers --id <application_id>

# Entrevista
python main.py applications interview-plan --id <application_id>

# Pipeline manual
python main.py pipeline add --url "https://..."
python main.py pipeline add --jd-file "jds/acme-role.md"
python main.py pipeline list
python main.py pipeline process --limit 5
python main.py pipeline retry-failed

# Artefatos
python main.py applications artifacts --id <application_id>
```

---

## Regras de seguranca recomendadas

1. Relatorios nao mudam status de candidatura.
2. CVs e cover letters sao sempre artefatos revisaveis.
3. Nenhum documento gerado e enviado automaticamente.
4. Geracao de respostas deve marcar incertezas.
5. LLM nao pode autorizar submit.
6. LLM nao pode pular preflight.
7. LLM nao pode preencher experiencia inexistente.
8. Arquivos do usuario nunca devem ser sobrescritos.
9. Falha em artefato nao deve quebrar fluxo principal.
10. Batch nunca deve executar submit real.

---

## Priorizacao final

| Prioridade | Adaptacao | Motivo |
|---|---|---|
| P0 | `docs/DATA_CONTRACT.md` | Baixo risco e previne problemas futuros com dados do usuario. |
| P0 | Relatorio A-F | Alto valor para revisao humana e baixo risco operacional. |
| P1 | Pipeline manual de URLs/JDs | Aumenta cobertura de vagas e integra entradas externas. |
| P1 | Extrator/liveness de JD | Melhora qualidade de entrada e reduz vagas expiradas. |
| P1 | CV/PDF ATS por vaga | Alto valor para candidatura, mas exige cuidado com dados pessoais. |
| P2 | Cover letter e respostas | Complementa pacote de candidatura. |
| P2 | Story Bank/entrevista | Valor pos-candidatura, depende de base de experiencias confiavel. |
| P3 | Batch | Util depois do pipeline manual estar estavel. |
| P3 | TUI/Dashboard | Melhoria de operacao, nao essencial ao core. |

---

## Conclusao

O `career-ops` nao deve ser visto como substituto do `jobHunterAgent`. Ele deve ser visto como um catalogo de capacidades de alto valor para a fase de candidatura assistida.

A direcao recomendada e:

1. manter o `jobHunterAgent` como runtime principal;
2. preservar SQLite, estados oficiais, preflight, autorizacao e gates humanos;
3. adaptar do `career-ops` os workflows de avaliacao, documentos, pipeline manual e preparacao;
4. implementar essas capacidades como servicos Python integrados a arquitetura atual;
5. tratar todo output gerado por LLM como artefato revisavel, nao como decisao operacional.

Com isso, o `jobHunterAgent` evolui de um agente de coleta, triagem e candidatura assistida para um sistema completo de operacao de carreira, mantendo a seguranca operacional que ja existe no projeto.
