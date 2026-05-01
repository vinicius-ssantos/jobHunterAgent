# Relatorio Operacional Local

## Objetivo

O comando `python main.py operations report` gera um resumo operacional local e read-only do Job Hunter Agent.

Use este relatorio para entender rapidamente:

- o snapshot atual de vagas e candidaturas;
- o que aconteceu na janela operacional recente;
- eventos recentes de candidaturas;
- ciclos de coleta registrados;
- logs de coleta por fonte e nivel;
- warnings e erros recentes de coleta.

O comando `python main.py operations next-actions` complementa o relatorio com uma lista curta de proximas acoes sugeridas, tambem read-only.

## Principios De Seguranca

Os comandos operacionais descritos neste guia sao somente leitura.

Eles nao devem:

- alterar status de vagas;
- alterar status de candidaturas;
- rodar coleta;
- rodar preflight;
- rodar submit;
- enviar mensagens via Telegram;
- usar LLM;
- autorizar candidatura;
- substituir revisao humana.

Eles existem para observabilidade local, auditoria leve e apoio a decisao humana.

## Comandos

### Janela Padrao

```bash
python main.py operations report
```

Sem parametros, o comando usa uma janela recente padrao de 1 dia.

### Janela Por Quantidade De Dias

```bash
python main.py operations report --days 7
```

Use `--days` para ampliar ou reduzir a janela considerada no resumo de eventos e coleta.

Exemplos:

```bash
python main.py operations report --days 1
python main.py operations report --days 3
python main.py operations report --days 7
```

### Janela A Partir De Uma Data

```bash
python main.py operations report --date 2026-05-01
```

Use `--date YYYY-MM-DD` para iniciar a janela em uma data especifica.

A data informada e interpretada como inicio do dia em UTC.

### Proximas Acoes Operacionais

```bash
python main.py operations next-actions
```

Use este comando quando quiser uma lista curta de candidaturas que podem exigir atencao humana ou proxima acao operacional.

O comando apenas sugere comandos conservadores. Ele nao executa nenhum dos comandos sugeridos.

## Estrutura Da Saida Do `operations report`

A saida e textual, pensada para terminal e logs locais.

### `janela_desde`

Indica o timestamp inicial usado para filtrar eventos e dados de coleta.

Exemplo:

```text
janela_desde=2026-05-01T00:00:00+00:00
```

### `snapshot_atual`

Mostra o estado atual persistido no SQLite no momento da execucao.

Essa secao nao depende apenas da janela; ela resume o estado atual conhecido.

Inclui contagens de vagas por status, como:

- `total`;
- `collected`;
- `approved`;
- `rejected`;
- `error_collect`.

Inclui contagens de candidaturas por status, como:

- `draft`;
- `ready_for_review`;
- `confirmed`;
- `authorized_submit`;
- `submitted`;
- `error_submit`;
- `cancelled`.

### `operacao_atual`

Quando houver dados operacionais classificados, essa secao resume motivos ou categorias importantes detectadas nas candidaturas atuais.

Exemplos possiveis:

- candidaturas prontas para envio;
- candidaturas externas;
- bloqueios por perguntas adicionais;
- casos de similar jobs ou redirects.

### `resumo_da_janela`

Resume eventos de candidatura dentro da janela.

Inclui indicadores como:

- `preflights_concluidos`;
- `submits_concluidos`;
- bloqueios por tipo;
- conversoes entre etapas.

Essa secao e baseada em eventos recentes persistidos, nao em execucao nova de preflight ou submit.

### `eventos_recentes`

Lista os eventos de candidatura mais recentes dentro da janela.

Cada linha costuma mostrar:

- timestamp;
- tipo do evento;
- transicao de status, quando houver;
- detalhe operacional.

Use essa secao para auditoria rapida antes de inspecionar uma candidatura especifica com:

```bash
python main.py applications diagnose --id <application_id>
```

### `coleta`

Resume ciclos de coleta registrados em `collection_runs` dentro da janela.

Campos esperados:

- `ciclos`;
- `ciclos_success`;
- `ciclos_error`;
- `ciclos_interrupted`;
- `ciclos_running`;
- `jobs_seen`;
- `jobs_saved`;
- `errors`.

Essa secao nao dispara nova coleta. Ela apenas le dados persistidos.

### `coleta_por_fonte`

Resume logs de coleta agrupados por fonte ou portal, quando houver dados em `collection_logs`.

Exemplo de fontes possiveis:

- `LinkedIn`;
- outros coletores configurados no runtime.

### `logs_por_nivel`

Resume logs de coleta agrupados por nivel.

Exemplos:

- `info`;
- `warning`;
- `warn`;
- `error`.

### `logs_recentes_warning_error`

Lista warnings e erros recentes de coleta dentro da janela.

Use essa secao para identificar rapidamente falhas de portal, problemas de navegacao ou coleta parcial.

## Estrutura Da Saida Do `operations next-actions`

A saida e textual e ordenada por prioridade conservadora.

Quando houver itens, a primeira linha informa a quantidade total:

```text
Proximas acoes operacionais: 3
```

Cada item mostra:

- `application_id`;
- `job_id`;
- `status` atual;
- titulo da vaga;
- empresa;
- motivo operacional resumido;
- acao sugerida;
- comando recomendado.

Exemplo ilustrativo:

```text
- application_id=42 | job_id=101 | status=confirmed
  vaga=Backend Java | empresa=ACME
  motivo=pronto_para_envio
  acao=avaliar autorizacao humana explicita apos preflight
  comando=python main.py applications preflight --id 42 --dry-run
```

Se nao houver candidaturas em estados acompanhados, o comando retorna:

```text
Nenhuma proxima acao operacional encontrada.
```

## Ordem De Prioridade Do `next-actions`

A ordem e deterministica e conservadora:

1. `error_submit`: investigar erro antes de nova tentativa;
2. `authorized_submit`: validar dry-run antes de submit real;
3. `confirmed`: rodar preflight em dry-run antes de qualquer acao;
4. `ready_for_review`: revisar manualmente antes de confirmar;
5. `draft`: preparar candidatura para revisao humana.

Candidaturas ja `submitted` ou `cancelled` nao aparecem como proximas acoes.

## Interpretacao Operacional

### Quando `jobs_seen` E Alto Mas `jobs_saved` E Baixo

Pode indicar:

- muitas duplicadas;
- filtro de matching restritivo;
- baixa aderencia das vagas coletadas;
- portal retornando vagas ja conhecidas.

### Quando `ciclos_error` Ou `errors` Aumentam

Investigue:

```bash
python main.py operations report --days 7
python main.py health
```

Depois revise os logs recentes e artefatos, quando aplicavel:

```bash
python main.py applications artifacts --limit 5
```

### Quando Ha Muitos Bloqueios De Preflight Ou Submit

Use diagnostico por candidatura:

```bash
python main.py applications diagnose --id <application_id>
```

O relatorio operacional mostra o agregado. O diagnostico por candidatura explica o caso individual.

### Quando `next-actions` Sugere Um Comando

Leia a sugestao como uma proxima verificacao, nao como autorizacao automatica.

Por exemplo, uma sugestao de `submit --dry-run` nao significa que o submit real deve ser executado. Ela apenas indica que a candidatura esta em um estado onde uma validacao controlada pode ser o proximo passo.

## Relacao Com Outros Comandos

### `status`

```bash
python main.py status
```

Mostra um resumo atual mais curto.

Use `operations report` quando precisar de janela, eventos e dados de coleta.

### `health`

```bash
python main.py health
```

Mostra checks locais de configuracao e ambiente.

Use `health` para sanidade operacional e `operations report` para historico recente.

### `operations next-actions`

```bash
python main.py operations next-actions
```

Mostra a fila operacional sugerida no momento atual.

Use depois de `operations report` quando quiser transformar o diagnostico agregado em uma lista curta de candidaturas para revisar.

### `applications diagnose`

```bash
python main.py applications diagnose --id <application_id>
```

Use para aprofundar uma candidatura especifica que apareceu no relatorio operacional ou no `next-actions`.

### `applications report`

```bash
python main.py applications report --id <application_id>
```

Gera relatorio A-F por candidatura.

Use `operations report` para visao agregada, `operations next-actions` para priorizacao operacional e `applications report` para uma candidatura individual.

## Limites Conhecidos

- O relatorio depende dos dados persistidos localmente no SQLite.
- Se nao houver `collection_runs` ou `collection_logs`, a secao de coleta pode aparecer vazia ou zerada.
- O snapshot atual representa o estado no momento da execucao, nao necessariamente apenas a janela.
- O resumo da janela depende de timestamps gravados nos eventos.
- O `next-actions` depende dos status atuais persistidos das candidaturas.
- O `next-actions` nao executa os comandos recomendados.
- Os comandos nao corrigem dados inconsistentes; eles apenas os mostram.

## Fluxo Recomendado

Para uma revisao diaria simples:

```bash
python main.py operations report
python main.py operations next-actions
```

Para uma revisao semanal:

```bash
python main.py operations report --days 7
python main.py operations next-actions
```

Quando houver erro ou bloqueio relevante:

```bash
python main.py applications diagnose --id <application_id>
python main.py health
```

Quando uma candidatura individual precisar de relatorio completo:

```bash
python main.py applications report --id <application_id>
```

## Criterios De Aceite Do Uso Operacional

Antes de tratar o relatorio como suficiente para uma revisao local, deve ser possivel responder:

- qual janela foi usada;
- quantas vagas e candidaturas existem no snapshot atual;
- se houve preflight ou submit na janela;
- se houve bloqueios recentes;
- quantos ciclos de coleta foram registrados;
- quantas vagas foram vistas e salvas;
- quais fontes geraram logs;
- se houve warnings ou erros recentes de coleta;
- qual candidatura precisa de diagnostico individual;
- qual proxima acao sugerida deve ser revisada primeiro.
