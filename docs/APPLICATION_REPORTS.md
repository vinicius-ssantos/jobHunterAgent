# Operacao De Relatorios A-F

## Objetivo

Este guia descreve como gerar, listar e validar relatorios A-F por candidatura usando comandos locais do Job Hunter Agent.

Use este documento quando precisar responder rapidamente:

- como gerar o relatorio Markdown de uma candidatura;
- onde o manifesto JSON sidecar e gravado;
- como usar caminhos customizados com `--output`;
- quando usar `--force` para sobrescrever arquivos;
- como listar relatorios ja gravados em disco;
- como validar consistencia entre `.md` e `.json`.

## Principios De Seguranca

- O fluxo de relatorios e read-only.
- A geracao de relatorio nao altera status da candidatura.
- A geracao de relatorio nao executa preflight.
- A geracao de relatorio nao executa submit.
- A geracao de relatorio nao usa LLM.
- O relatorio deve ser tratado como artefato operacional de leitura e auditoria, nao como autorizacao para envio real.

## Gerar Relatorio Padrao

Para gerar o relatorio A-F de uma candidatura:

```bash
python main.py applications report --id <application_id>
```

Arquivos gerados por padrao:

```text
artifacts/reports/application-<application_id>.md
artifacts/reports/application-<application_id>.json
```

O Markdown e o documento principal para leitura humana. O JSON e um manifesto sidecar usado para listagem, validacao e integracoes locais.

## Gerar Em Caminho Customizado

Use `--output` quando quiser controlar o caminho do Markdown:

```bash
python main.py applications report --id <application_id> --output custom/report.md
```

Arquivos gerados:

```text
custom/report.md
custom/report.json
```

A extensao `.json` e derivada do caminho informado em `--output`. Portanto, `custom/report.md` gera `custom/report.json` no mesmo diretorio.

## Politica De Sobrescrita

Por seguranca, o comando nao sobrescreve artefatos existentes por padrao.

Se o `.md` ou o `.json` de destino ja existir, a geracao deve falhar sem alterar os arquivos.

Para sobrescrever intencionalmente, use `--force`:

```bash
python main.py applications report --id <application_id> --force
```

Ou com caminho customizado:

```bash
python main.py applications report --id <application_id> --output custom/report.md --force
```

Use `--force` somente quando a sobrescrita fizer parte da operacao planejada, por exemplo para regenerar um relatorio apos atualizacao de dados da candidatura.

## Manifesto JSON

O manifesto JSON registra os metadados principais do artefato gerado.

Campos esperados:

- `application`: dados resumidos da candidatura;
- `job`: dados resumidos da vaga associada;
- `status`: status operacional da candidatura no momento da geracao;
- `support`: informacoes de suporte ao fluxo de candidatura;
- `report_path`: caminho do Markdown gerado;
- `manifest_path`: caminho do proprio manifesto JSON;
- `safety`: flags que documentam o comportamento read-only;
- `generated_at_utc`: timestamp UTC da geracao.

Flags esperadas em `safety`:

```json
{
  "read_only": true,
  "uses_llm": false,
  "runs_preflight": false,
  "runs_submit": false,
  "changes_status": false
}
```

Essas flags devem deixar claro que o relatorio nao substitui revisao humana, preflight, autorizacao ou submit.

## Listar Relatorios

Para listar os relatorios A-F gravados no diretorio padrao:

```bash
python main.py applications reports list
```

Limitar a quantidade de itens:

```bash
python main.py applications reports list --limit 20
```

Listar a partir de outro diretorio:

```bash
python main.py applications reports list --dir artifacts/reports
```

Comportamento esperado:

- lista relatorios em disco;
- usa o manifesto JSON quando disponivel;
- faz fallback para Markdown quando o manifesto nao existe;
- tolera JSON invalido sem interromper toda a listagem;
- ordena por modificacao mais recente;
- permanece read-only.

## Validar Relatorios

Para validar os artefatos no diretorio padrao:

```bash
python main.py applications reports validate
```

Validar outro diretorio:

```bash
python main.py applications reports validate --dir artifacts/reports
```

Executar validacao estrita:

```bash
python main.py applications reports validate --strict
```

A validacao cobre:

- Markdown sem manifesto JSON correspondente;
- manifesto JSON sem Markdown correspondente;
- JSON invalido;
- campos minimos ausentes;
- divergencias em `report_path`;
- divergencias em `manifest_path`;
- flags de `safety` ausentes ou incorretas.

## Warnings E Errors

A validacao pode reportar avisos ou erros.

Use a interpretacao operacional abaixo:

- warning: artefato ainda pode ser lido, mas ha degradacao de consistencia ou metadados incompletos;
- error: artefato esta inconsistente o bastante para falhar o fluxo de validacao.

Com `--strict`, warnings tambem devem ser tratados como falha operacional para uso em CI ou rotinas locais mais conservadoras.

## Fluxo Operacional Recomendado

### 1. Gerar O Relatorio

```bash
python main.py applications report --id <application_id>
```

Confirme que os dois arquivos foram criados:

```text
artifacts/reports/application-<application_id>.md
artifacts/reports/application-<application_id>.json
```

### 2. Listar Artefatos Recentes

```bash
python main.py applications reports list --limit 10
```

Use a listagem para confirmar que o relatorio aparece e aponta para os caminhos esperados.

### 3. Validar Consistencia

```bash
python main.py applications reports validate
```

Use `--strict` antes de merge, release ou rotina automatizada:

```bash
python main.py applications reports validate --strict
```

### 4. Prosseguir Com Fluxos De Candidatura Separadamente

O relatorio nao executa e nao substitui os comandos operacionais de candidatura.

Para diagnostico operacional:

```bash
python main.py applications diagnose --id <application_id>
```

Para preflight:

```bash
python main.py applications preflight --id <application_id> --dry-run
```

Para autorizacao e submit, siga o guia `docs/APPLICATION_OPERATIONS.md` e mantenha revisao humana explicita.

## Relacao Com Preflight, Authorize E Submit

Relatorios A-F sao artefatos de leitura.

Eles podem ajudar a revisar uma candidatura antes de decisoes humanas, mas nao mudam o ciclo de vida da candidatura.

Em particular, gerar, listar ou validar relatorios nao deve:

- criar candidatura;
- preparar candidatura;
- confirmar candidatura;
- autorizar submit;
- rodar preflight;
- rodar submit;
- alterar status;
- acionar LLM.

## Troubleshooting

### O Comando Falhou Porque O Arquivo Ja Existe

Use um caminho diferente ou sobrescreva conscientemente com `--force`:

```bash
python main.py applications report --id <application_id> --force
```

### O Markdown Existe Mas O JSON Nao

Rode a validacao para confirmar a inconsistencia:

```bash
python main.py applications reports validate
```

Depois regenere o relatorio com `--force`, se a substituicao for esperada.

### O JSON Existe Mas O Markdown Nao

Trate como artefato quebrado. A listagem pode conseguir mostrar metadados parciais, mas a validacao deve indicar a falha.

### O JSON Esta Invalido

A listagem deve tolerar o problema e continuar. A validacao deve reportar o erro para reparo do artefato.

### `--strict` Falhou Com Warnings

Esse comportamento e esperado: no modo estrito, warnings contam como falha operacional.

Use o modo padrao para auditoria exploratoria e `--strict` para gates locais mais conservadores.

## Criterios De Aceite Do Fluxo Documentado

Antes de considerar a operacao de relatorios A-F clara, deve ser possivel responder:

- qual comando gera o relatorio;
- quais arquivos sao gerados;
- como `--output` altera os caminhos;
- quando `--force` e necessario;
- quais campos principais existem no manifesto JSON;
- como listar relatorios existentes;
- como validar relatorios;
- o que muda com `--strict`;
- por que o fluxo e read-only e separado de preflight/submit.
