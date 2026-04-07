# Pos-MVP: Estrutura, Refatoracao e Evolucao

## Estado Atual Validado

- [x] Coleta local de vagas funcional
- [x] Normalizacao e scoring local com fallback deterministico
- [x] Persistencia local em SQLite
- [x] Aprovacao humana antes de qualquer acao de alto impacto
- [x] Preflight real de candidatura no LinkedIn
- [x] Gate explicito em `authorized_submit`
- [x] Submit real assistido no LinkedIn validado em producao
- [x] Captura de artefatos em falhas relevantes

## Objetivo Desta Fase

Fechar o produto operacionalmente antes de expandir escopo.

Regra da fase atual:

- [ ] Nao adicionar novos portais antes de estabilizar o LinkedIn
- [ ] Nao adicionar novas features de produto antes de endurecer operacao, estados e observabilidade
- [ ] Tratar a fase atual como estabilizacao e padronizacao

## P0: Estabilizacao Operacional

### Fluxo real

- [ ] Repetir validacao real em mais amostras de vagas Easy Apply
- [ ] Catalogar variacoes reais do LinkedIn que ainda aparecem:
  - [ ] redirecionamento para `similar jobs`
  - [ ] perguntas adicionais obrigatorias
  - [ ] checkboxes opcionais
  - [ ] vagas com curriculo reaproveitado
  - [ ] vagas com etapa final sem modal classico
- [ ] Criar criterios objetivos para classificar:
  - [ ] `ready`
  - [ ] `manual_review`
  - [ ] `blocked`

### Higiene de estado

- [ ] Parar de acumular todo o historico operacional em `notes`
- [ ] Separar no armazenamento:
  - [ ] ultimo preflight
  - [ ] ultimo submit
  - [ ] ultimo erro
  - [ ] historico resumido de transicoes
- [ ] Garantir que toda transicao relevante tenha timestamp e motivo explicito
- [ ] Revisar se `support_level` e `support_rationale` devem ser atualizados por ciclo ou preservados como snapshot inicial

### Observabilidade

- [ ] Criar uma visao clara de fila operacional por status
- [ ] Expor rapidamente:
  - [ ] quantas vagas estao `approved`
  - [ ] quantas candidaturas estao `draft`
  - [ ] quantas estao `confirmed`
  - [ ] quantas estao `authorized_submit`
  - [ ] quantas estao `submitted`
  - [ ] quantas estao `error_submit`
- [ ] Padronizar nomes e estrutura dos artefatos de falha
- [ ] Adicionar um resumo final por execucao com:
  - [ ] preflights concluidos
  - [ ] submits concluidos
  - [ ] bloqueios por tipo

## P0: UX Operacional

- [ ] Eliminar operacao por `python -c` para tarefas frequentes
- [ ] Criar comandos claros para:
  - [ ] listar vagas aprovadas
  - [ ] listar candidaturas
  - [ ] preparar candidatura
  - [ ] confirmar candidatura
  - [ ] rodar preflight
  - [ ] autorizar submit
  - [ ] executar submit
  - [ ] ver artefatos da ultima falha
- [ ] Definir uma interface principal:
  - [ ] Telegram como interface de operacao principal
  - [ ] CLI como fallback tecnico
- [ ] Tornar o fluxo humano rastreavel sem editar estado manualmente no banco

## P1: Melhorias Estruturais

### Separacao de responsabilidades

- [ ] Extrair uma camada de orquestracao explicita para o fluxo de candidatura
- [ ] Reduzir o acoplamento entre:
  - [ ] `app.py`
  - [ ] `applicant.py`
  - [ ] `linkedin_application.py`
- [ ] Garantir que o modulo do LinkedIn contenha somente:
  - [ ] navegacao
  - [ ] leitura da pagina
  - [ ] acoes do portal
- [ ] Garantir que decisao de estado continue fora do adaptador Playwright

### Refatoracoes SOLID

#### Single Responsibility Principle

- [ ] Quebrar `linkedin_application.py` em componentes menores:
  - [ ] leitura do estado da pagina
  - [ ] localizacao e abertura do fluxo apply
  - [ ] preenchimento de campos
  - [ ] decisao de submit
  - [ ] captura de artefatos
- [ ] Reduzir o papel de `applicant.py` para servicos de caso de uso e transicao
- [ ] Manter logs e persistencia fora de helpers de DOM quando possivel

#### Open/Closed Principle

- [ ] Definir pontos de extensao para novos tipos de fluxo do LinkedIn sem branching espalhado
- [ ] Isolar estrategias de deteccao do fluxo:
  - [ ] modal classico
  - [ ] `apply` por URL
  - [ ] review final
  - [ ] bloqueios conhecidos
- [ ] Tornar a classificacao de preflight extensivel por estrategia

#### Liskov Substitution Principle

- [ ] Revisar protocolos de `ApplicationFlowInspector` e `JobApplicant`
- [ ] Garantir que dublês de teste preservem o contrato real
- [ ] Evitar caminhos especiais de producao que nao aparecem nos testes

#### Interface Segregation Principle

- [ ] Quebrar interfaces grandes em contratos menores quando necessario
- [ ] Separar interfaces de:
  - [ ] inspecao
  - [ ] submit
  - [ ] captura de artefatos
  - [ ] preparacao de candidatura

#### Dependency Inversion Principle

- [ ] Injetar dependencias de tempo, filesystem e geracao de artefatos onde hoje houver comportamento implicito
- [ ] Evitar construcao profunda de dependencias dentro de fluxos de negocio
- [ ] Padronizar factories na composition edge

## P1: Clean Code

### Nomes e intencao

- [ ] Revisar nomes ambigos de metodos e helpers
- [ ] Garantir que nomes expressem efeito observavel
- [ ] Remover metodos utilitarios que misturam decisao e side effect

### Tamanho e legibilidade

- [ ] Reduzir funcoes longas com muitos caminhos de erro
- [ ] Extrair blocos de fallback do LinkedIn para helpers nomeados
- [ ] Consolidar trechos repetidos de clique, espera e recuperacao

### Dados e modelos

- [ ] Revisar se `LinkedInApplicationPageState` ja esta no limite de responsabilidade
- [ ] Separar o que e:
  - [ ] sinal bruto de pagina
  - [ ] interpretacao operacional
  - [ ] decisao de fluxo
- [ ] Evitar strings compostas manualmente como unica fonte de diagnostico

### Erros e logging

- [ ] Padronizar mensagens de erro por categoria
- [ ] Diferenciar claramente:
  - [ ] erro de portal
  - [ ] bloqueio funcional
  - [ ] estado inconclusivo
  - [ ] falha inesperada
- [ ] Garantir que logs internos preservem contexto, mas mensagens operacionais sejam curtas

## P1: Persistencia e Modelo de Dados

- [ ] Rever schema para suportar historico operacional sem sobrecarregar `notes`
- [ ] Avaliar adicionar tabela de eventos de candidatura
- [ ] Avaliar adicionar tabela de artefatos com metadata minima
- [ ] Garantir que consultas operacionais nao dependam de parsing de texto livre

## P1: Qualidade e Testes

- [ ] Adicionar testes para:
  - [ ] redirecionamento para `similar jobs`
  - [ ] perguntas adicionais obrigatorias
  - [ ] fluxo `apply` por URL direta
  - [ ] review final com `submit` visivel
  - [ ] artefatos de preflight inconclusivo
- [ ] Criar fixtures HTML reais anonimizadas dos casos validados
- [ ] Adicionar testes focados em transicoes de estado
- [ ] Garantir uma suite rapida de regressao operacional

## P2: Melhoria de Produto

### Telegram e revisao

- [ ] Tornar o Telegram suficiente para operar o fluxo completo com seguranca
- [ ] Exibir melhor o motivo de `manual_review`
- [ ] Exibir quando a vaga parece cair em `similar jobs`
- [ ] Exibir quando a vaga exige perguntas adicionais

### Priorizacao

- [ ] Melhorar a selecao das vagas que valem tentativa automatica
- [ ] Evitar gastar preflight em vagas com alta chance de `manual_review`
- [ ] Dar preferencia a vagas com sinal forte de Easy Apply simples

### Configuracao

- [ ] Revisar validacao de curriculo, telefone e email para o fluxo real
- [ ] Tornar obrigatoria a validacao das configuracoes minimas antes de submit
- [ ] Melhorar mensagens de configuracao invalida

## P2: Organizacao do Repositorio

- [ ] Consolidar checklists dispersos quando houver sobreposicao
- [ ] Definir quais arquivos viram:
  - [ ] backlog vivo
  - [ ] checklist operacional
  - [ ] documentacao historica
- [ ] Evitar proliferacao de arquivos de checklist sem dono claro

## Refatoracao Proposta por Modulo

### `job_hunter_agent/app.py`

- [ ] Reduzir para orquestracao de alto nivel
- [ ] Mover comandos operacionais para uma camada de interface/CLI
- [ ] Evitar logica de transicao fora de servicos dedicados

### `job_hunter_agent/applicant.py`

- [ ] Separar preparacao, preflight e submit em casos de uso ainda mais explicitos
- [ ] Extrair logica de montagem de `detail` para formatadores dedicados
- [ ] Reduzir responsabilidade sobre strings operacionais

### `job_hunter_agent/linkedin_application.py`

- [ ] Separar DOM inspection de action execution
- [ ] Isolar estrategias de entrada no fluxo apply
- [ ] Isolar estrategias de deteccao de review final
- [ ] Extrair um componente de artifact capture

### `job_hunter_agent/notifier.py`

- [ ] Revisar se handlers de callback ainda estao fazendo mais de uma coisa
- [ ] Reduzir regras de negocio embutidas no transporte

### `job_hunter_agent/repository.py`

- [ ] Avaliar se `notes` deve continuar no formato atual
- [ ] Criar consultas mais orientadas a operacao
- [ ] Manter SQL encapsulado, mas reduzir responsabilidades auxiliares quando crescer

## Definicao de Conclusao da Fase

- [ ] Fluxo de candidatura assistida opera sem `python -c`
- [ ] Historico operacional deixa de depender de texto livre acumulado
- [ ] Casos `similar jobs` e `perguntas adicionais` ficam claramente classificados
- [ ] Regressao operacional principal permanece verde
- [ ] Estrutura do codigo fica mais modular no fluxo LinkedIn
- [ ] Telegram ou CLI passam a ser suficientes para operar o produto com seguranca

