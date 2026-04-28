# Relatorio A-F Por Candidatura

## Objetivo

Definir o contrato funcional do relatorio A-F por candidatura antes de implementar runtime.

O relatorio deve enriquecer a revisao humana com uma avaliacao estruturada da vaga e da candidatura, sem alterar status, sem autorizar submit e sem substituir os gates operacionais existentes.

## Principios

- O relatorio e um artefato revisavel.
- O relatorio nao muda status da candidatura.
- O relatorio nao autoriza submit.
- O relatorio nao pula preflight.
- O relatorio deve seguir `docs/DATA_CONTRACT.md`.
- O relatorio deve separar fatos, inferencias e recomendacoes.
- O relatorio deve marcar incertezas e lacunas de informacao.
- Conteudo gerado por LLM deve ser tratado como sugestao.

## Entradas

Entradas esperadas para implementacao futura:

- `application_id`;
- candidatura carregada do SQLite;
- vaga associada;
- status e suporte da candidatura;
- perfil estruturado do candidato, quando configurado;
- taxonomia de skills, quando configurada;
- politicas operacionais, quando configuradas;
- rationale e score ja persistidos para a vaga;
- eventos recentes e diagnostico operacional, quando relevantes.

Entradas opcionais futuras:

- curriculo original do usuario;
- artefatos previos da candidatura;
- respostas sugeridas ou confirmadas;
- historico de entrevista/story bank.

## Saidas

Saida principal:

```text
artifacts/reports/application-<application_id>.md
```

Saida estruturada opcional futura:

```text
artifacts/reports/application-<application_id>.json
```

O caminho do artefato podera ser associado a candidatura em uma tabela futura de artefatos. Ate existir essa tabela, o nome do arquivo deve ser deterministico e documentado.

## Blocos Do Relatorio

### A. Resumo Da Vaga

Objetivo: resumir o papel de forma objetiva.

Conteudo esperado:

- empresa;
- titulo;
- localidade/modalidade;
- fonte;
- link;
- senioridade inferida, se houver sinal suficiente;
- resumo curto da oportunidade.

Regras:

- nao inventar senioridade;
- marcar inferencias como inferencias;
- preservar link original.

### B. Match Com O Perfil

Objetivo: explicar por que a vaga combina ou nao combina com o perfil.

Conteudo esperado:

- requisitos que batem com o perfil;
- requisitos ausentes ou incertos;
- skills fortes;
- possiveis gaps;
- score atual e rationale persistidos.

Regras:

- diferenciar dado confirmado de inferencia;
- nao afirmar experiencia que nao exista no perfil/curriculo;
- marcar `requires_human_review` quando faltar dado.

### C. Nivel, Estrategia E Posicionamento

Objetivo: sugerir posicionamento humano para candidatura.

Conteudo esperado:

- estrategia de candidatura;
- pontos a enfatizar;
- riscos de desalinhamento;
- recomendacao: `apply`, `review`, `hold` ou `skip`.

Regras:

- recomendacao nao altera status;
- recomendacao nao substitui revisao humana;
- recomendacao deve explicar trade-offs.

### D. Compensacao, Demanda E Sinais Operacionais

Objetivo: avaliar sinais praticos que afetam prioridade.

Conteudo esperado:

- salario informado ou ausente;
- modalidade;
- urgencia ou sinais de vaga ativa;
- suporte operacional do portal;
- possiveis bloqueios de candidatura.

Regras:

- nao inferir salario quando ausente;
- registrar quando dados sao desconhecidos;
- usar diagnostico operacional como contexto, nao como decisao final.

### E. Plano De Personalizacao

Objetivo: orientar artefatos futuros como CV, cover letter e respostas.

Conteudo esperado:

- palavras-chave relevantes;
- projetos/experiencias a destacar;
- bullets sugeridos em alto nivel;
- pontos para revisar manualmente;
- dados faltantes para gerar documentos.

Regras:

- nao gerar CV final neste relatorio;
- nao inventar metricas;
- marcar sugestoes como revisaveis;
- respeitar `docs/DATA_CONTRACT.md`.

### F. Plano De Entrevista

Objetivo: preparar a proxima etapa se a candidatura avancar.

Conteudo esperado:

- temas provaveis de entrevista;
- historias STAR+R candidatas;
- gaps de preparacao;
- perguntas que o candidato pode fazer.

Regras:

- nao inventar historias;
- marcar historias como candidatas, nao confirmadas;
- indicar lacunas de informacao.

## Comando CLI Futuro

Comando sugerido:

```bash
python main.py applications report --id <application_id>
```

Opcoes futuras:

```bash
python main.py applications report --id <application_id> --force
python main.py applications report --id <application_id> --json
python main.py applications report --id <application_id> --output artifacts/reports/custom.md
```

Comportamento esperado:

- validar que a candidatura existe;
- carregar vaga associada;
- gerar artefato Markdown;
- imprimir caminho do artefato;
- nao alterar status;
- nao executar preflight;
- nao executar submit.

## Estados Permitidos

O relatorio pode ser gerado para candidaturas em estados como:

- `draft`;
- `ready_for_review`;
- `confirmed`;
- `authorized_submit`;
- `submitted`;
- `error_submit`.

A geracao para estados de erro deve ser permitida, pois pode ajudar diagnostico e decisao humana.

## Falhas E Degradacao

Falhas esperadas:

- candidatura inexistente;
- vaga associada inexistente;
- perfil do candidato ausente;
- LLM indisponivel;
- diretorio de artefatos sem permissao;
- descricao de vaga insuficiente.

Comportamento recomendado:

- retornar erro claro para candidatura/vaga inexistente;
- gerar relatorio parcial quando LLM estiver indisponivel;
- marcar lacunas explicitamente;
- nao quebrar o fluxo principal de candidatura;
- nao apagar relatorio anterior sem `--force`.

## Formato Markdown Sugerido

```markdown
# Relatorio Da Candidatura <application_id>

## Metadados

- Candidatura: <id>
- Vaga: <job_id>
- Empresa: <company>
- Titulo: <title>
- Status: <status>
- Gerado em: <utc timestamp>

## A. Resumo Da Vaga

## B. Match Com O Perfil

## C. Nivel, Estrategia E Posicionamento

## D. Compensacao, Demanda E Sinais Operacionais

## E. Plano De Personalizacao

## F. Plano De Entrevista

## Incertezas E Revisao Humana
```

## Contrato JSON Opcional

Contrato futuro sugerido:

```json
{
  "application_id": 123,
  "job_id": 456,
  "generated_at": "2026-04-28T12:00:00+00:00",
  "recommendation": "review",
  "artifact_path": "artifacts/reports/application-123.md",
  "blocks": {
    "summary": {},
    "profile_match": {},
    "strategy": {},
    "operations": {},
    "personalization": {},
    "interview": {}
  },
  "warnings": [],
  "requires_human_review": true
}
```

## Regras De Seguranca

- LLM nao pode autorizar submit.
- LLM nao pode alterar status.
- LLM nao pode sobrescrever dados do usuario.
- LLM nao pode inventar experiencia, certificacao, senioridade ou metricas.
- O relatorio deve ser salvo como artefato novo ou sobrescrito apenas com `--force`.
- O relatorio deve ser seguro para revisao local, nao para envio automatico.

## Criterios De Aceite Para Implementacao Futura

- Gerar relatorio Markdown para candidatura existente.
- Falhar claramente para candidatura inexistente.
- Gerar conteudo parcial quando perfil/LLM estiver indisponivel.
- Nao alterar status da candidatura.
- Nao executar submit nem preflight.
- Salvar artefato em caminho deterministico.
- Imprimir caminho do artefato no CLI.
- Cobrir renderer/servico com testes unitarios.
- Cobrir dispatch/parser do comando com testes.

## Fora De Escopo Desta Especificacao

- implementar o comando agora;
- criar tabela de artefatos agora;
- gerar CV/PDF;
- gerar cover letter;
- preencher formulario;
- executar submit;
- criar dashboard/TUI.
