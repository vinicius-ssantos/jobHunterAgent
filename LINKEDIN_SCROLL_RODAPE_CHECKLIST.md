# Checklist De Scroll Ate O Rodape No LinkedIn

## Objetivo

Esta branch existe para mudar a coleta do LinkedIn para uma estrategia mais agressiva dentro de cada pagina:

- descer a pagina ate o rodape
- esgotar a lista interna de vagas
- so depois avancar para a proxima pagina da UI

## Regras

- manter a paginacao da UI do LinkedIn como mecanismo de troca de pagina
- evitar voltar a depender de `start` na URL como estrategia principal
- preservar logs claros de observabilidade
- validar a coleta real apos a mudanca

## Fases

### Fase 1 - Scroll ate o rodape

Objetivo:
- fazer o coletor descer a pagina ate o fim real antes da extracao final dos cards

Definicao de pronto:
- o log mostra que o rodape foi alcancado
- a coleta continua funcional

### Fase 2 - Observabilidade do scroll

Objetivo:
- deixar claro no log quantos cards havia antes/depois e quantas passagens foram feitas

Definicao de pronto:
- o terminal permite verificar se o scroll realmente aconteceu

### Fase 3 - Validacao real

Objetivo:
- confirmar que o runtime continua estavel e que a estrategia nova nao quebrou a coleta

Definicao de pronto:
- testes relevantes verdes
- run real sem erro

## Checklist

- [x] Fase 1 concluida
- [x] Fase 2 concluida
- [x] Fase 3 concluida
- [x] README atualizado se a operacao mudar
- [ ] AGENTS atualizado se as regras mudarem
