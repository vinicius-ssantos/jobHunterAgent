# Plano De Refatoracao Arquitetural

## Objetivo

Esta branch existe para melhorar a estrutura do projeto de forma incremental, sem quebrar o loop principal:

- collect
- score
- persist
- notify
- review

O foco aqui nao e adicionar features novas. O foco e reduzir acoplamento, clarificar responsabilidades e melhorar aderencia a SOLID e clean code.

## Estado Atual

O projeto esta funcional e validado em runtime, mas ainda ha pontos de concentracao de responsabilidade que merecem refino.

Achados principais:

1. `job_hunter_agent/app.py`
- O composition root esta pesado demais.
- O modulo ainda monta muitas dependencias concretas diretamente.
- Ha lambdas e wiring duplicado na montagem do coletor do LinkedIn.

2. `job_hunter_agent/notifier.py`
- O modulo mistura:
  - integracao Telegram
  - renderizacao de mensagens
  - logica de transicao de estado
  - callback orchestration
- O fluxo funciona, mas o modulo tem mais de uma razao para mudar.

3. `job_hunter_agent/collector.py`
- O arquivo ainda atua como fachada de compatibilidade e reexporta simbolos de modulos ja extraidos.
- Isso reduz clareza arquitetural e mantem um acoplamento residual desnecessario.

4. `job_hunter_agent/repository.py`
- O repositório mistura:
  - contrato
  - implementacao SQLite
  - schema creation
  - pequenas migracoes
  - canonicalizacao especifica de LinkedIn
- A regra de identidade de vaga por portal esta vazando para a camada de persistencia.

## Principios Para Esta Refatoracao

- Cada passo deve ser pequeno e reversivel.
- Nenhuma etapa deve quebrar o loop principal.
- Cada etapa deve preservar ou melhorar testes.
- Refatoracao sem validacao nao conta como concluida.
- Nao mover responsabilidade apenas de arquivo; mover com fronteira mais clara.

## Ordem De Ataque

### Fase 1 - `app.py` (concluida)

Objetivo:
- deixar `app.py` mais proximo de composition root puro

Passos:
- extrair factories privadas ou modulo de montagem de servicos
- remover wiring duplicado do LinkedIn
- reduzir construcao inline de dependencias concretas

Definicao de pronto:
- `JobHunterApplication.__init__` menor e mais legivel
- menos detalhes de infraestrutura concretos no constructor

### Fase 2 - `notifier.py` (concluida)

Objetivo:
- separar transporte, renderizacao e politica de transicao

Passos:
- extrair builders de mensagem/cartao
- extrair regras de transicao de candidatura/revisao
- deixar `TelegramNotifier` mais focado em transporte

Definicao de pronto:
- callbacks delegam para funcoes ou servicos menores
- renderizacao nao fica misturada ao handler

### Fase 3 - `collector.py` (concluida)

Objetivo:
- reduzir o papel de fachada e compatibilidade

Passos:
- eliminar reexports desnecessarios
- deixar no arquivo apenas contratos e orquestracao real
- mover imports de compatibilidade para os modulos corretos

Definicao de pronto:
- menos superficie publica acidental
- responsabilidades mais obvias por modulo

### Fase 4 - `repository.py` (concluida)

Objetivo:
- separar persistencia de regras especificas de identidade por portal

Passos:
- extrair estrategia de canonicalizacao de URL/chave
- deixar o repositorio dependente de uma estrategia, nao dono da regra
- manter schema e SQL sob responsabilidade do repositório

Definicao de pronto:
- regra especifica de LinkedIn nao fica embutida no repositorio SQLite

## Regras Operacionais

- Cada fase deve ser commitada separadamente.
- Commits em portugues.
- Rodar testes relevantes a cada fase.
- Quando fizer sentido, validar tambem com run real curto.

## Checklist De Refatoracao

- [x] Fase 1 concluida
- [x] Fase 2 concluida
- [x] Fase 3 concluida
- [x] Fase 4 concluida
- [x] README atualizado se a estrutura publica mudar
- [ ] AGENTS atualizado se a politica operacional mudar
- [x] loop principal validado ao final
