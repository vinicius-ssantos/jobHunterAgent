# Operacao De Candidaturas

## Objetivo

Este guia descreve como validar, diagnosticar e recuperar candidaturas de forma segura usando os comandos locais do Job Hunter Agent.

Use este documento quando precisar responder rapidamente:

- qual e o estado atual da candidatura;
- por que ela esta pronta, bloqueada ou em erro;
- qual foi a ultima transicao relevante;
- qual proxima acao segura executar.

## Principios De Seguranca

- Nao execute submit real sem autorizacao explicita.
- Use `--dry-run` quando quiser validar prontidao sem tocar o portal.
- Nao ignore bloqueios operacionais: eles existem para evitar envio incorreto.
- Use `domain-events` como trilha de auditoria complementar, nao como fonte unica de verdade.
- SQLite continua sendo a fonte principal para candidatura, vaga e status.

## Diagnostico Rapido

Para obter uma visao agregada de uma candidatura:

```bash
python main.py applications diagnose --id <application_id>
```

A saida deve reunir:

- dados principais da candidatura;
- vaga relacionada;
- status atual;
- nivel de suporte;
- ultimos detalhes de preflight, submit e erro;
- eventos SQLite recentes;
- domain-events recentes por `correlation_id=application:<application_id>` quando habilitados;
- proxima acao recomendada.

Se `domain-events` estiver desabilitado, o diagnostico deve continuar funcionando e informar que a secao esta indisponivel ou desabilitada.

## Habilitar Auditoria Por Domain Events

Para acompanhar transicoes reais com eventos estruturados:

```bash
export JOB_HUNTER_DOMAIN_EVENTS_ENABLED=true
export JOB_HUNTER_DOMAIN_EVENTS_PATH=./logs/domain-events.ndjson
```

Inspecione eventos por candidatura:

```bash
python main.py domain-events list --correlation-id application:<application_id> --limit 20
```

Use JSON quando quiser integrar com scripts locais:

```bash
python main.py domain-events list --correlation-id application:<application_id> --json
```

## Checklist End-To-End Manual

### 1. Aprovar Vaga

```bash
python main.py jobs list --status collected
python main.py jobs approve --id <job_id>
python main.py jobs show --id <job_id>
```

Confirme:

- a vaga existe;
- o status virou `approved`;
- a decisao foi intencional.

Com `domain-events` habilitado, procure:

```bash
python main.py domain-events list --event-type JobReviewedV1 --limit 20
```

### 2. Criar Draft De Candidatura

```bash
python main.py applications create --job-id <job_id>
python main.py applications list --status draft
```

Confirme:

- existe uma candidatura para a vaga;
- o status inicial e `draft`;
- o `support_level` faz sentido para o portal/vaga.

Com `domain-events` habilitado, procure:

```bash
python main.py domain-events list --event-type ApplicationDraftCreatedV1 --limit 20
```

### 3. Preparar Para Revisao

```bash
python main.py applications prepare --id <application_id>
python main.py applications diagnose --id <application_id>
```

Confirme:

- status esperado: `ready_for_review`;
- campos de suporte e notas estao claros;
- a proxima acao recomendada envolve confirmacao ou cancelamento apos revisao humana.

### 4. Confirmar Apos Revisao Humana

```bash
python main.py applications confirm --id <application_id>
python main.py applications diagnose --id <application_id>
```

Confirme:

- status esperado: `confirmed`;
- ainda nao houve submit real;
- a candidatura esta pronta para preflight ou precisa de ajuste manual.

### 5. Rodar Preflight

Comece com dry-run quando estiver validando:

```bash
python main.py applications preflight --id <application_id> --dry-run
```

Depois rode o preflight real quando apropriado:

```bash
python main.py applications preflight --id <application_id>
python main.py applications diagnose --id <application_id>
```

Confirme:

- `last_preflight_detail` descreve o resultado;
- o status continua coerente;
- se houver bloqueio, ele esta visivel no diagnostico.

Com `domain-events` habilitado:

```bash
python main.py domain-events list --event-type ApplicationPreflightCompletedV1 --correlation-id application:<application_id> --limit 20
```

### 6. Autorizar Envio Real

Somente autorize depois da revisao humana e do preflight adequado:

```bash
python main.py applications authorize --id <application_id>
python main.py applications diagnose --id <application_id>
```

Confirme:

- status esperado: `authorized_submit`;
- a autorizacao foi intencional;
- a proxima acao recomendada e submit controlado ou dry-run.

Com `domain-events` habilitado:

```bash
python main.py domain-events list --event-type ApplicationAuthorizedV1 --correlation-id application:<application_id> --limit 20
```

### 7. Validar Submit Sem Envio Real

Antes de enviar, rode dry-run:

```bash
python main.py applications submit --id <application_id> --dry-run
python main.py applications diagnose --id <application_id>
```

Confirme:

- nenhuma submissao real foi feita;
- qualquer bloqueio operacional esta explicado;
- o estado segue seguro.

### 8. Executar Submit Real

Execute apenas se a candidatura estiver autorizada e a revisao humana permitir:

```bash
python main.py applications submit --id <application_id>
python main.py applications diagnose --id <application_id>
```

Resultado esperado:

- `submitted`, se o envio foi concluido; ou
- `error_submit`, se houve erro/bloqueio controlado.

Com `domain-events` habilitado:

```bash
python main.py domain-events list --correlation-id application:<application_id> --limit 20
```

Procure um destes eventos:

- `ApplicationSubmittedV1`;
- `ApplicationBlockedV1`.

## Troubleshooting De Estados E Bloqueios

### `preflight_not_ready`

Significa que o submit nao encontrou uma candidatura pronta para envio.

Acoes:

```bash
python main.py applications diagnose --id <application_id>
python main.py applications preflight --id <application_id> --dry-run
```

Verifique `last_preflight_detail`, status atual e eventos recentes. Nao force submit sem entender o bloqueio.

### `portal_not_supported`

O portal ou fluxo da vaga nao e suportado pelo submit automatico atual.

Acoes:

- trate como revisao manual;
- mantenha a candidatura sem submit automatico;
- registre nota operacional se necessario.

```bash
python main.py applications diagnose --id <application_id>
```

### `readiness_incomplete`

A candidatura ainda nao tem todos os dados ou condicoes para prosseguir.

Acoes:

- revisar vaga, suporte e campos da candidatura;
- rodar preflight novamente em dry-run apos ajuste;
- confirmar que `last_preflight_detail` mudou de forma coerente.

### `submit_unavailable`

O mecanismo de submit ou o portal pode estar indisponivel no momento.

Acoes:

- verificar se e falha temporaria;
- revisar artifacts/logs quando existirem;
- repetir somente depois de diagnosticar.

```bash
python main.py applications artifacts --limit 5
python main.py applications diagnose --id <application_id>
```

### `applicant_error`

Indica problema relacionado aos dados do candidato, formulario ou entrada exigida.

Acoes:

- revisar o detalhe do erro;
- corrigir dados do candidato ou campos faltantes;
- rodar preflight em dry-run antes de nova tentativa.

### `error_submit`

Estado de erro apos tentativa de submit real ou bloqueio controlado.

Acoes:

```bash
python main.py applications diagnose --id <application_id>
python main.py applications artifacts --limit 5
python main.py domain-events list --correlation-id application:<application_id> --limit 20
```

Verifique:

- `last_error`;
- `last_submit_detail`;
- eventos SQLite recentes;
- `ApplicationBlockedV1` e seu `reason`;
- se `retryable=True` aparece nos domain-events.

Nao retente automaticamente sem entender o motivo.

## Leituras Recomendadas

- `docs/DOMAIN_EVENTS.md` para detalhes dos eventos de dominio e filtros.
- `python main.py applications diagnose --id <application_id>` para a visao operacional consolidada.
- `python main.py status` para resumo geral de vagas e candidaturas.

## Criterio De Pronto Operacional

Antes de considerar uma candidatura operacionalmente clara, deve ser possivel responder:

- qual e o status atual;
- qual vaga ela representa;
- se o portal e suportado;
- qual foi o ultimo preflight;
- se houve submit real;
- se existe erro ou bloqueio;
- qual e a proxima acao segura.
