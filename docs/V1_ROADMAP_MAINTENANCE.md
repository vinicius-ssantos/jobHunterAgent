# V1 Roadmap Maintenance Guide

## Objetivo

Definir uma rotina simples para manter a documentacao operacional, checklists e limites da v1 alinhados ao estado real do projeto.

Este guia complementa:

- `docs/V1_HARDENING_CHECKLIST.md`;
- `docs/POST_MVP_SAFETY_BOUNDARIES.md`;
- `docs/APPLICATION_OPERATIONS.md`;
- `docs/DATA_CONTRACT.md`.

## Rotina Recomendada

Ao iniciar uma nova frente:

1. Verificar issues abertas do track correspondente.
2. Confirmar se a frente toca runtime, docs, schema, CLI ou safety.
3. Criar PR pequeno com escopo unico.
4. Usar `Refs #issue` quando a frente for parcial.
5. Usar `Closes #issue` somente quando todos os criterios de aceite forem atendidos.
6. Aguardar CI e Docker antes de mergear.
7. Atualizar README ou checklist apenas quando o comportamento documentado mudar.

## Ordem De Prioridade Da V1

Priorizar nesta ordem:

1. safety e gates humanos;
2. reproducibilidade local;
3. observabilidade e diagnostico;
4. persistencia e auditoria;
5. matching e explicabilidade;
6. melhorias de ergonomia;
7. features post-MVP.

## Quando Atualizar O README

Atualize o README quando houver:

- novo guia operacional em `docs/`;
- novo comando de usuario final;
- mudanca de setup;
- mudanca em variaveis principais de runtime;
- mudanca em limites de safety;
- mudanca no escopo declarado da v1.

Evite atualizar README quando:

- a mudanca for apenas detalhe interno;
- o documento novo for experimental;
- a frente ainda estiver em especificacao sem impacto para operador.

## Quando Atualizar Checklists

Atualize checklists quando houver:

- mudanca em criterio de pronto;
- nova validacao manual relevante;
- fechamento real de uma frente;
- decisao explicita de estacionar algo fora do MVP;
- nova dependencia operacional.

Nao marque item como concluido se:

- so existe especificacao, mas nao implementacao;
- CI/Docker ainda nao passaram;
- o comportamento nao foi validado;
- a mudanca ainda depende de PR aberto.

## Politica De Issues E PRs

### Issues

Uma issue deve ter:

- objetivo claro;
- escopo;
- fora de escopo quando houver risco de expansao;
- criterios de aceite;
- labels coerentes.

### PRs

Um PR deve:

- tocar poucos arquivos;
- ter descricao com resumo e testes;
- referenciar issue;
- evitar misturar runtime, docs e schema sem necessidade;
- esperar CI/Docker antes de merge.

## Uso De `Refs` E `Closes`

Use `Refs #N` quando:

- o PR e incremental;
- a issue ainda tera outro PR;
- o checklist ainda nao esta completo;
- falta validacao ou documentacao complementar.

Use `Closes #N` quando:

- todos os criterios de aceite foram cumpridos;
- o PR deixa a frente em estado final;
- nao ha follow-up obrigatorio para a mesma issue.

## Regras De Safety Para Roadmap

Toda proposta que envolva candidatura real deve responder:

- existe revisao humana?
- existe autorizacao explicita?
- existe `--dry-run` quando aplicavel?
- existe diagnostico para falha?
- existe registro persistido?
- a acao pode ser revertida ou bloqueada com seguranca?

Se a resposta for negativa para algum ponto critico, a proposta deve permanecer no post-MVP ou virar especificacao antes de runtime.

## Trilha De Documentos Operacionais

Documentos atuais de referencia:

- `docs/V1_HARDENING_CHECKLIST.md`: pronto operacional minimo da v1.
- `docs/POST_MVP_SAFETY_BOUNDARIES.md`: itens estacionados por safety.
- `docs/APPLICATION_OPERATIONS.md`: operacao e troubleshooting de candidaturas.
- `docs/DOMAIN_EVENTS.md`: auditoria complementar por eventos.
- `docs/DATA_CONTRACT.md`: dados do usuario, artefatos e sistema.
- `docs/SQLITE_SCHEMA_AND_UTC_CHECKLIST.md`: schema SQLite e UTC.

## Checklist De Manutencao Antes De Fechar Uma Issue

Antes de fechar uma issue:

- [ ] criterios de aceite foram atendidos;
- [ ] PR relacionado passou em CI;
- [ ] Docker passou quando aplicavel;
- [ ] README foi atualizado se necessario;
- [ ] checklists foram atualizados se necessario;
- [ ] itens fora de escopo ficaram documentados;
- [ ] nao ha PR aberto dependente para o mesmo criterio.
