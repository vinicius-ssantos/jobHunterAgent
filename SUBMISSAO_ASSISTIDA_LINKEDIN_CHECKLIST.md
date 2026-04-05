# Checklist Da Submissao Assistida No LinkedIn

## Objetivo

Esta branch existe para iniciar a automacao real de candidatura no LinkedIn de forma assistida e conservadora.

A primeira meta nao e enviar candidatura automaticamente, e sim:

- abrir a vaga real no LinkedIn
- detectar o CTA de candidatura na pagina
- classificar o fluxo encontrado
- registrar um preflight baseado na pagina real, nao apenas na URL

## Fases

### Fase 1 - Inspetor real do LinkedIn

Objetivo:
- abrir a vaga confirmada e inspecionar o fluxo de candidatura no navegador

Definicao de pronto:
- o preflight usa a pagina real do LinkedIn
- o detalhe retornado informa se encontrou `Easy Apply`, candidatura externa ou ausencia de CTA

### Fase 2 - Integracao com o preflight atual

Objetivo:
- encaixar o inspetor real no fluxo ja validado de `/candidaturas`

Definicao de pronto:
- candidaturas confirmadas do LinkedIn passam pelo inspetor real antes de receber o resultado do preflight

### Fase 3 - Validacao

Objetivo:
- garantir que a fase real nao quebre o fluxo assistido existente

Definicao de pronto:
- testes afetados verdes
- um run real de preflight do LinkedIn sem submissao

### Fase 4 - Mapeamento seguro do modal

Objetivo:
- quando houver `Easy Apply`, abrir o modal real e mapear sinais do fluxo sem enviar candidatura

Definicao de pronto:
- o inspetor distingue fluxo simples de fluxo multi-etapas
- o preflight registra sinais como passos adicionais, upload de CV e perguntas
- nenhum clique de envio real e executado

### Fase 5 - Dry-run de campos seguros

Objetivo:
- mapear quais campos do modal seriam preenchiveis com seguranca antes de qualquer submissao real

Definicao de pronto:
- o preflight registra campos basicos detectados no modal
- o detalhe do resultado diferencia contato, autorizacao e experiencia quando visiveis
- ainda sem clicar em enviar candidatura

### Fase 6 - Dry-run de preenchimento seguro

Objetivo:
- tentar preencher somente campos basicos e reversiveis quando houver dados locais explicitos

Definicao de pronto:
- o inspetor tenta preencher email, telefone e codigo do pais quando configurados
- o detalhe do preflight registra quais campos foram preenchidos com sucesso
- nenhum clique de envio real e executado

## Regras

- nao submeter candidatura real nesta fase
- nao clicar em enviar
- manter confirmacao humana forte
- degradar com seguranca quando o Playwright ou o LinkedIn falharem

## Checklist

- [x] Fase 1 concluida
- [x] Fase 2 concluida
- [x] Fase 3 concluida
- [x] Fase 4 concluida
- [x] Fase 5 concluida
- [x] Fase 6 concluida
- [x] README atualizado se a operacao mudar
- [x] AGENTS reavaliado; sem mudancas necessarias nesta fase

## Validacao final

- `pytest tests/test_app.py -q`
- `pytest tests/test_database.py -k "application_preflight" -q`
- `pytest tests/test_linkedin_application.py -q`
- preflight real executado sobre candidatura confirmada no banco com retorno `ready`
- preflight real reexecutado com abertura do modal e classificacao `manual_review` para fluxo multi-etapas
