# Telegram Human Review Gates

## Objetivo

Documentar como o fluxo Telegram atua como camada explicita de revisao e autorizacao humana antes de qualquer candidatura real.

Este documento atende a issue #66 e complementa:

- `docs/APPLICATION_OPERATIONS.md`;
- `docs/V1_HARDENING_CHECKLIST.md`;
- `docs/POST_MVP_SAFETY_BOUNDARIES.md`;
- `docs/SQLITE_CRITICAL_STATE_AUDIT.md`.

## Principios

- Telegram e interface de revisao humana, nao mecanismo de submit automatico irrestrito.
- Aprovar uma vaga nao envia candidatura.
- Confirmar uma candidatura nao envia candidatura.
- Submit real exige status `authorized_submit`.
- Estados e decisoes devem ficar persistidos em SQLite.
- Falha de callback deve responder de forma segura e nao avancar estado.

## Fluxo De Revisao De Vagas

Mensagem de vaga enviada para revisao deve expor contexto suficiente para decisao humana:

- titulo;
- empresa;
- localidade/modalidade;
- fonte/link;
- score/relevance;
- rationale de matching quando disponivel.

Acoes atuais:

```text
approve:<job_id> -> aprovar vaga
reject:<job_id>  -> ignorar/rejeitar vaga
```

Persistencia esperada:

- `jobs.status` muda para `approved` ou `rejected`;
- `job_status_events` registra transicao ou reafirmacao;
- `detail` registra texto operacional da decisao.

Garantias:

- aprovar vaga apenas marca a vaga como aprovada;
- rejeitar vaga apenas marca a vaga como rejeitada;
- nenhuma acao de vaga executa submit real.

## Fluxo De Candidaturas Via Telegram

A fila de candidaturas pode ser consultada por:

```text
/candidaturas
```

Estados normalmente exibidos:

```text
draft, ready_for_review, confirmed, authorized_submit
```

Acoes de candidatura:

```text
app_prepare:<application_id>   -> draft -> ready_for_review
app_confirm:<application_id>   -> ready_for_review -> confirmed
app_authorize:<application_id> -> confirmed/error_submit -> authorized_submit
app_preflight:<application_id> -> solicita preflight quando permitido
app_submit:<application_id>    -> solicita submit real quando permitido
app_cancel:<application_id>    -> cancela estados ativos permitidos
```

## Matriz De Gates

| Acao | Estado minimo | Resultado | Submit real? |
| --- | --- | --- | --- |
| Aprovar vaga | `collected` | `jobs.status=approved` | Nao |
| Rejeitar vaga | `collected` | `jobs.status=rejected` | Nao |
| Preparar candidatura | `draft` | `ready_for_review` | Nao |
| Confirmar candidatura | `ready_for_review` | `confirmed` | Nao |
| Rodar preflight | `confirmed` ou `error_submit` | executa callback de preflight | Nao |
| Autorizar candidatura | `confirmed` ou `error_submit` | `authorized_submit` | Nao |
| Solicitar submit | `authorized_submit` | executa callback de submit | Sim, se callback estiver disponivel |
| Cancelar candidatura | `draft`, `ready_for_review`, `confirmed`, `authorized_submit` | `cancelled` | Nao |

## Regras De Bloqueio

### Preflight

Permitido quando:

- candidatura esta `confirmed`; ou
- candidatura esta `error_submit` e precisa de nova verificacao.

Bloqueado quando:

- candidatura ja esta `authorized_submit`;
- candidatura esta `cancelled`;
- candidatura ainda nao foi confirmada.

### Submit Real

Permitido apenas quando:

- candidatura esta `authorized_submit`;
- callback de submit esta configurado na execucao atual.

Bloqueado quando:

- candidatura esta `draft`;
- candidatura esta `ready_for_review`;
- candidatura esta `confirmed`;
- candidatura esta `submitted`;
- candidatura esta `error_submit`;
- candidatura esta `cancelled`;
- callback de submit esta indisponivel.

## Persistencia E Auditoria

Toda decisao que muda estado deve registrar:

- estado atual na tabela principal;
- evento SQLite com `from_status`, `to_status` e `detail`;
- domain-event complementar quando a frente de eventos estiver habilitada e integrada ao fluxo correspondente.

Fontes principais:

- `jobs`;
- `job_status_events`;
- `job_applications`;
- `job_application_events`.

Comandos de auditoria:

```bash
python main.py status
python main.py applications diagnose --id <application_id>
python main.py domain-events list --correlation-id application:<application_id> --limit 20
```

## Fallback Seguro

Se uma callback do Telegram falhar:

- o teclado da mensagem deve ser limpo quando aplicavel;
- o usuario deve receber mensagem de falha;
- nenhum estado deve ser avancado silenciosamente;
- o operador deve usar CLI para diagnosticar.

Mensagem esperada em falha generica:

```text
Falha ao processar a acao solicitada.
```

Comando recomendado:

```bash
python main.py applications diagnose --id <application_id>
```

## Criterios De Aceite Da Issue #66

- [x] Decisao humana de vaga e candidatura esta documentada.
- [x] Separacao entre aprovar vaga, confirmar candidatura, autorizar envio e executar submit esta documentada.
- [x] Persistencia esperada em SQLite esta documentada.
- [x] Fallback seguro para erro de callback esta documentado.
- [x] Documento deixa claro que candidatura real sem confirmacao/autorizacao explicita permanece bloqueada.

## Gaps E Melhorias Futuras

Nao bloqueiam a v1:

- adicionar testes especificos para mensagens/botoes Telegram se a suite ainda nao cobrir todos os estados;
- enriquecer cards Telegram com resumo de diagnostico antes de autorizar submit;
- registrar uma nota operacional especifica quando callback de submit estiver indisponivel;
- adicionar comando Telegram dedicado para diagnostico por candidatura.

Qualquer melhoria futura deve preservar o gate `authorized_submit` antes de submit real.
