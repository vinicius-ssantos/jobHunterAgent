# Data Contract

## Objetivo

Definir quais arquivos e diretorios pertencem ao usuario, quais sao artefatos gerados localmente e quais fazem parte do sistema versionado.

Este contrato existe para evitar sobrescrita acidental de dados sensiveis e orientar futuras features de relatorios, CV, cover letter, respostas de formulario, pipeline manual e artefatos de candidatura.

## Principios

- Dados do usuario nao devem ser sobrescritos sem confirmacao explicita.
- Artefatos gerados devem ser versionaveis por caminho ou registro, sem apagar versoes anteriores por padrao.
- Arquivos do sistema podem evoluir via git, PR e testes.
- Dados sensiveis locais nao devem ser commitados.
- Falha ao gerar artefatos nao deve corromper o banco SQLite nem arquivos do usuario.
- Outputs de LLM sao sugestoes revisaveis, nao fonte de verdade operacional.

## Camada Do Usuario

Arquivos e diretorios nesta camada pertencem ao usuario ou ao ambiente local. Eles podem conter dados pessoais, credenciais, sessoes autenticadas, perfil profissional ou historico operacional.

Exemplos:

- `.env`
- `job_target.json`
- curriculo original do usuario
- perfil estruturado do candidato
- arquivos locais apontados por `JOB_HUNTER_CANDIDATE_PROFILE_PATH`
- arquivos locais apontados por `JOB_HUNTER_SKILL_TAXONOMY_PATH`
- arquivos locais apontados por `JOB_HUNTER_LINKEDIN_COMPANY_POLICY_PATH`
- arquivos locais apontados por `JOB_HUNTER_OPERATIONAL_POLICY_PATH`
- banco SQLite local, por exemplo `jobs.db`
- storage state do LinkedIn
- perfil persistente do browser
- logs locais que possam conter URLs, empresas, dados de candidatura ou informacoes pessoais

Regras:

- nao sobrescrever sem confirmacao explicita;
- nao recriar com defaults silenciosos se ja existir;
- nao commitar conteudo real;
- preferir exemplos versionados sem dados reais;
- criar backup antes de qualquer migracao destrutiva ou conversao de dados.

## Artefatos Gerados

Artefatos sao outputs produzidos pelo sistema para revisao humana ou diagnostico. Eles podem ser regenerados, mas ainda podem conter dados pessoais e decisao operacional.

Diretorios sugeridos para features futuras:

```text
artifacts/
  reports/
  cv/
  cover_letters/
  answers/
  interview/
  extraction/
```

Tipos esperados:

- relatorios de avaliacao de vaga/candidatura;
- CVs adaptados por vaga;
- cover letters;
- respostas sugeridas para formularios;
- planos de entrevista;
- snapshots de extracao de JD;
- logs ou diagnosticos de preflight/submit.

Regras:

- nao enviar automaticamente sem revisao humana;
- nao apagar versoes anteriores por padrao;
- registrar caminho e tipo quando o artefato for associado a candidatura;
- marcar artefatos gerados por LLM como sugestoes;
- evitar incluir segredos ou tokens;
- permitir regeneracao controlada com `--force` apenas quando existir comportamento claro.

## Camada Do Sistema

Arquivos versionados que fazem parte do produto e podem evoluir por PR:

- `job_hunter_agent/`
- `main.py`
- `scripts/`
- `tests/`
- `docs/`
- `.env.example`
- `job_target.example.json`
- `requirements.txt`
- configuracoes de CI/Docker

Regras:

- mudancas devem passar por PR;
- exemplos nao devem conter dados reais;
- templates devem ser genericos e revisaveis;
- alteracoes de runtime devem incluir testes quando aplicavel.

## Exemplos Versionados

Arquivos de exemplo devem ser seguros para commit e conter dados ficticios ou placeholders.

Exemplos:

- `.env.example`
- `job_target.example.json`
- templates futuros de relatorio, CV ou cover letter

Regras:

- nunca incluir credenciais reais;
- nunca incluir dados pessoais reais;
- documentar quais campos o usuario deve preencher localmente.

## Banco SQLite Local

O banco SQLite e dado operacional local e deve ser tratado como camada do usuario.

Regras:

- nao apagar automaticamente;
- nao converter dados antigos em massa sem backup;
- migracoes devem ser idempotentes;
- novas migracoes devem registrar versao em `schema_migrations`;
- comandos de diagnostico devem ser preferidos antes de qualquer reparo manual.

Antes de qualquer intervencao manual:

```bash
cp jobs.db jobs.db.backup-$(date -u +%Y%m%dT%H%M%SZ)
```

## Sessoes E Credenciais

Arquivos de sessao autenticada e credenciais sao sensiveis.

Exemplos:

- `.env`
- storage state do LinkedIn
- perfil persistente do browser
- tokens de Telegram
- URLs privadas ou parametros autenticados

Regras:

- nao commitar;
- nao imprimir em logs sem mascaramento;
- nao copiar para artefatos gerados;
- nao sobrescrever sem confirmacao.

## Regras Para Futuras Features

### Relatorios De Candidatura

- podem ler dados de vaga, candidatura e perfil;
- devem gerar artefato revisavel;
- nao devem alterar status da candidatura automaticamente;
- devem diferenciar fatos, inferencias e recomendacoes.

### CV E Cover Letter

- nunca sobrescrever o curriculo original;
- sempre gerar novo artefato por candidatura;
- marcar conteudo como revisavel;
- nao inventar experiencia, senioridade, certificacao ou metricas;
- exigir revisao humana antes de uso em submit.

### Pipeline Manual

- itens inseridos manualmente devem ser tratados como dados do usuario;
- erros devem ser registrados sem apagar entrada original;
- processamento deve ser idempotente quando possivel;
- deduplicacao nao deve excluir dados sem registro.

### LLM

- respostas do LLM sao auxiliares;
- LLM nao autoriza submit;
- LLM nao pula preflight;
- LLM nao deve sobrescrever dados confirmados do usuario;
- campos incertos devem ser marcados para revisao humana.

## Criterio Para Novas Mudancas

Antes de implementar feature que leia, escreva ou gere arquivos locais, responda:

- o dado pertence ao usuario, ao sistema ou e artefato gerado?
- o arquivo pode conter dado sensivel?
- existe risco de sobrescrita?
- existe backup ou versionamento local?
- o README ou a documentacao operacional precisam ser atualizados?
- o comportamento e seguro em execucao repetida?
