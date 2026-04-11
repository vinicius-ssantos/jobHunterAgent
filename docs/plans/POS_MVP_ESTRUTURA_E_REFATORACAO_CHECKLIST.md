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

- [x] Nao adicionar novos portais antes de estabilizar o LinkedIn
- [x] Nao adicionar novas features de produto antes de endurecer operacao, estados e observabilidade
- [x] Tratar a fase atual como estabilizacao e padronizacao

## P0: Estabilizacao Operacional

### Fluxo real

- [x] Repetir validacao real em mais amostras de vagas Easy Apply
  - [x] amostras reais validadas: `application_id=2`, `5`, `7`, `8`, `10` em `submitted`
  - [x] bloqueios reais classificados: `application_id=1` (`vaga_expirada`), `3` (`similar_jobs`), `4`, `6`, `9` (`candidatura_externa`)
- [x] Catalogar variacoes reais do LinkedIn que ainda aparecem:
  - [x] redirecionamento para `similar jobs`
  - [x] perguntas adicionais obrigatorias
  - [x] checkboxes opcionais
  - [x] vagas com curriculo reaproveitado
    - [x] nao observadas nas amostras reais atuais; nenhum tratamento especifico adicional necessario ate aqui
  - [x] vagas com etapa final sem modal classico
    - [x] nao observadas nas amostras reais atuais; monitoradas via artefatos e classificacao operacional
- [x] Criar criterios objetivos para classificar:
  - [x] `ready`
  - [x] `manual_review`
  - [x] `blocked`

### Higiene de estado

- [x] Parar de acumular todo o historico operacional em `notes`
- [x] Separar no armazenamento:
  - [x] ultimo preflight
  - [x] ultimo submit
  - [x] ultimo erro
  - [x] historico resumido de transicoes
- [x] Garantir que toda transicao relevante tenha timestamp e motivo explicito
- [x] Revisar se `support_level` e `support_rationale` devem ser atualizados por ciclo ou preservados como snapshot inicial
  - [x] decisao: preservar como snapshot inicial do rascunho; preflight e submit nao recalculam suporte por ciclo

### Observabilidade

- [x] Criar uma visao clara de fila operacional por status
- [x] Expor rapidamente:
  - [x] quantas vagas estao `approved`
  - [x] quantas candidaturas estao `draft`
  - [x] quantas estao `confirmed`
  - [x] quantas estao `authorized_submit`
  - [x] quantas estao `submitted`
  - [x] quantas estao `error_submit`
- [x] Padronizar nomes e estrutura dos artefatos de falha
- [x] Adicionar um resumo final por execucao com:
  - [x] preflights concluidos
  - [x] submits concluidos
  - [x] bloqueios por tipo

## P0: UX Operacional

- [x] Eliminar operacao por `python -c` para tarefas frequentes
- [x] Fechar cobertura operacional completa por CLI para que o fluxo nao dependa do Telegram como unico caminho de execucao
- [x] Criar comandos claros para:
  - [x] listar vagas pendentes de revisao
  - [x] aprovar vaga
  - [x] rejeitar vaga
  - [x] listar vagas aprovadas
  - [x] listar candidaturas
  - [x] preparar candidatura
  - [x] confirmar candidatura
  - [x] cancelar candidatura
  - [x] rodar preflight
  - [x] autorizar submit
  - [x] executar submit
  - [x] ver artefatos da ultima falha
- [x] Explicitar na UX que CLI e Telegram cobrem o fluxo operacional principal, com Telegram opcional para revisao assincrona
- [x] Definir uma interface principal:
  - [x] CLI como interface operacional principal
  - [x] Telegram como interface de revisao assincrona opcional
- [x] Tornar o fluxo humano rastreavel sem editar estado manualmente no banco

## P1: Melhorias Estruturais

### Separacao de responsabilidades

- [x] Extrair uma camada de orquestracao explicita para o fluxo de candidatura
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
  - [x] leitura do estado da pagina
  - [x] localizacao e abertura do fluxo apply
  - [x] preenchimento de campos
  - [x] decisao de submit
  - [x] captura de artefatos
- [x] Reduzir o papel de `applicant.py` para servicos de caso de uso e transicao
- [ ] Manter logs e persistencia fora de helpers de DOM quando possivel

#### Open/Closed Principle

- [ ] Definir pontos de extensao para novos tipos de fluxo do LinkedIn sem branching espalhado
- [ ] Isolar estrategias de deteccao do fluxo:
  - [ ] modal classico
  - [x] `apply` por URL
  - [ ] review final
  - [x] bloqueios conhecidos
- [ ] Tornar a classificacao de preflight extensivel por estrategia

#### Liskov Substitution Principle

- [x] Revisar protocolos de `ApplicationFlowInspector` e `JobApplicant`
- [x] Garantir que dublês de teste preservem o contrato real
- [x] Evitar caminhos especiais de producao que nao aparecem nos testes

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
- [x] Extrair blocos de fallback do LinkedIn para helpers nomeados
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

### Integracao de LLMs locais

Descricao:
Essas sugestoes de evolucao com modelos locais parecem promissoras para o fluxo atual, mas ainda exigem analise mais aprofundada antes de virarem decisao de arquitetura ou implementacao. A avaliacao pendente deve cobrir beneficio operacional real, confiabilidade das saidas estruturadas, custo de manutencao, latencia local e aderencia as regras de fallback conservador do produto.

- [ ] Avaliar separar configuracao de modelos por responsabilidade, em vez de reutilizar um unico modelo para todo o pipeline
- [ ] Avaliar `qwen2.5:7b` como modelo padrao para tarefas textuais estruturadas:
  - [ ] scoring
  - [ ] extracao de requisitos
  - [ ] rationale de revisao
  - [ ] prioridade operacional
- [ ] Avaliar `qwen3-vl:8b` apenas para fluxos que realmente dependam de visao:
  - [ ] interpretacao de modal
  - [ ] leitura assistida de screenshot
  - [ ] analise visual de pagina quando heuristica textual nao bastar
- [ ] Avaliar uso opcional de `deepseek-r1:8b` para segunda opiniao em casos limitrofes, sem virar dependencia do fluxo principal
- [ ] Definir criterios objetivos para decidir quando um uso de LLM local e benefico:
  - [ ] melhora de qualidade perceptivel
  - [ ] preservacao de fallback deterministico
  - [ ] latencia aceitavel no hardware local
  - [ ] saida estruturada suficientemente confiavel
- [ ] Validar se a separacao por modelo reduz risco operacional ou apenas aumenta complexidade de configuracao e manutencao

### Oportunidades adicionais ainda em analise

Descricao:
As possibilidades abaixo parecem potencialmente beneficas para o produto, mas ainda precisam de analise de viabilidade antes de entrarem no backlog priorizado. A avaliacao deve considerar aderencia ao escopo local-first, impacto no loop principal, complexidade de manutencao, risco de ampliar demais o produto e custo operacional no uso diario.

- [ ] Avaliar calibracao do scoring com base no historico local de vagas `approved` e `rejected`
- [ ] Avaliar e implementar busca dirigida por empresas prioritarias, usando grupos de prioridade de empresas, familias de cargo, senioridade alvo e janela temporal para gerar uma fila priorizada de revisao em lote
- [ ] Avaliar registrar motivo curto e padronizado para descarte por regra ou por score
- [ ] Avaliar criar um feedback loop local de revisao humana para refinar criterios de triagem
- [ ] Avaliar um modo formal de `dry-run` para preflight e submit, com relatorio e artefatos
- [ ] Avaliar adicionar health checks antes de operacoes criticas:
  - [ ] `Ollama`
  - [ ] Playwright
  - [ ] sessao autenticada do LinkedIn
  - [ ] Telegram
  - [ ] caminhos obrigatorios como curriculo e banco
- [ ] Avaliar rate limiting, retry e backoff explicitos por portal
- [ ] Avaliar enriquecimento local de metadados da vaga:
  - [ ] idioma
  - [ ] senioridade
  - [ ] regiao
  - [ ] faixa salarial estimada quando houver sinal suficiente
- [ ] Avaliar canonicalizacao de empresas para reduzir variacoes de nome e melhorar deduplicacao
- [ ] Avaliar guardar snapshot minimo ou hash do conteudo original da vaga para auditoria e depuracao
- [ ] Avaliar a necessidade de uma acao de revisao adiada sem distorcer os estados oficiais de vaga
- [ ] Avaliar agrupamento de vagas muito parecidas para reduzir ruido no Telegram
- [ ] Avaliar um ranking operacional de atencao para destacar o que merece preflight primeiro
- [ ] Avaliar checklist de prontidao antes do preflight ou submit real
- [ ] Avaliar catalogo local de perguntas recorrentes de candidatura e respostas sugeridas, sempre com aprovacao humana antes de uso
- [ ] Avaliar deteccao antecipada de bloqueios recorrentes que hoje so aparecem no preflight
- [ ] Avaliar metricas locais simples por ciclo e por portal:
  - [ ] taxa de duplicata
  - [ ] taxa de aprovacao
  - [ ] taxa de erro
  - [ ] taxa de `manual_review`
  - [ ] tempo por etapa
- [ ] Avaliar relatorio local resumido por execucao ou por dia
- [ ] Avaliar versionamento de prompts, heuristicas e formatos estruturados para facilitar comparacao de comportamento
- [ ] Avaliar contratos mais formais para saidas estruturadas dos usos de LLM
- [ ] Avaliar separar de forma mais explicita:
  - [ ] sinal extraido
  - [ ] interpretacao
  - [ ] decisao operacional
- [ ] Avaliar se uma fila interna local de tarefas operacionais traria robustez real sem transformar o projeto em plataforma generica

### Parametrizacao e desacoplamento de criterios ainda em analise

Descricao:
Hoje existe sinal de acoplamento entre configuracao tecnica, criterios de matching e heuristicas de inferencia. Essa frente parece promissora para reduzir duplicacao e melhorar manutencao, mas ainda precisa de analise de viabilidade e recorte para evitar excesso de generalizacao. A avaliacao deve preservar o foco do produto, respeitar SOLID e impedir que a configuracao vire uma plataforma generica de regras.

- [x] Mapear tudo o que hoje representa politica de triagem ou inferencia e esta espalhado entre configuracao, prompts e heuristicas
- [x] Avaliar extrair um objeto de dominio central para perfil e criterios de matching, separado de `Settings`
- [x] Avaliar manter `Settings` focado em infraestrutura, runtime e bootstrap
- [x] Avaliar introduzir um modelo validado para perfil profissional e busca, como `CandidateProfile` ou `JobSearchProfile`
- [x] Avaliar introduzir uma policy central de matching para vocabulario, aliases e criterios reutilizaveis
- [x] Validar se a centralizacao reduz acoplamento real sem piorar a experiencia de configuracao

Mapeamento consolidado do estado atual no codigo:

- [x] `core/settings.py` concentra hoje tanto infraestrutura quanto politica de triagem:
  - [x] `profile_text`
  - [x] `relaxed_testing_profile_hint`
  - [x] `include_keywords`
  - [x] `exclude_keywords`
  - [x] `relaxed_testing_remove_exclude_keywords`
  - [x] `accepted_work_modes`
  - [x] `minimum_salary_brl`
  - [x] `minimum_relevance`
  - [x] `relaxed_testing_minimum_relevance`
  - [x] `sites.search_url` com termos de cargo/stack embutidos
- [x] `collectors/collector.py` concentra o prefiltro deterministico antes do scorer:
  - [x] corte por `exclude_keywords`
  - [x] corte por `accepted_work_modes`
  - [x] corte por `minimum_salary_brl`
  - [x] fallback de aceitacao baseado no `minimum_relevance`
- [x] `llm/scoring.py` repete politica de matching dentro do prompt e no parsing:
  - [x] usa `scoring_profile_text`
  - [x] usa `include_keywords`
  - [x] usa `scoring_exclude_keywords`
  - [x] usa `accepted_work_modes`
  - [x] usa `minimum_salary_brl`
  - [x] converte `minimum_relevance` em gate de aceitacao
- [x] `llm/job_requirements.py` centraliza hoje uma taxonomia hardcoded reutilizada por heuristica, prompt e parsing:
  - [x] senioridade: `junior`, `pleno`, `senior`, `especialista`, `lideranca`
  - [x] ingles: `nao_informado`, `basico`, `intermediario`, `avancado`, `fluente`
  - [x] stack principal: `java`, `kotlin`, `spring`, `spring boot`, `angular`, `react`
  - [x] stack secundaria: `aws`, `azure`, `docker`, `kubernetes`, `postgresql`, `sql`, `microservices`
  - [x] sinais de lideranca: `lideranca`, `liderar`, `tech lead`, `mentoria`, `coordenar`, `ownership`
- [x] `llm/application_priority.py` embute hoje uma politica derivada de prioridade:
  - [x] `alta` quando `relevance >= 8` com `remoto/hibrido`
  - [x] `media` quando `relevance >= 6`
  - [x] `baixa` no restante
- [x] `application/applicant.py` mistura regra estrutural de suporte com heuristica por portal:
  - [x] `LinkedIn + easy apply/candidatura simplificada -> auto_supported`
  - [x] `LinkedIn sem evidencia suficiente -> manual_review`
  - [x] `Gupy -> unsupported`
  - [x] `Indeed -> manual_review`
  - [x] `demais portais -> unsupported`
- [x] Parsing e normalizacao ainda dependem de enums textuais repetidos em mais de um modulo:
  - [x] `remoto`, `hibrido`, `hybrid`
  - [x] `alta`, `media`, `baixa`
  - [x] `auto_supported`, `manual_review`, `unsupported`

Decisao de recorte apos o mapeamento:

- [x] Parametrizavel sem risco de virar plataforma generica:
  - [x] vocabulos de inclusao/exclusao
  - [x] modalidades aceitas
  - [x] salario minimo
  - [x] limiar minimo de relevancia
  - [x] hint de relaxed matching para testes
  - [x] termos da busca inicial por portal
- [x] Deve permanecer estrutural e fora da futura parametrizacao ampla:
  - [x] estados do dominio
  - [x] gates humanos (`confirmed`, `authorized_submit`)
  - [x] classificacao conservadora de suporte por portal
  - [x] fallback seguro quando LLM falha
  - [x] regras de submit real no LinkedIn
- [x] Proximo alvo tecnico recomendado para implementacao:
  - [x] extrair um objeto validado de criterios de matching separado de `Settings`
  - [x] manter `Settings` focado em runtime, infraestrutura e bootstrap
  - [x] introduzir uma policy central reutilizavel por prefiltro, scorer e extracao estruturada

Possivel alvo de centralizacao a avaliar:

- [ ] aliases de cargo e titulo:
  - [ ] `engenheiro de software`
  - [ ] `software engineer`
  - [ ] `desenvolvedor backend`
- [ ] taxonomia de senioridade
- [ ] taxonomia de stack principal e secundaria
- [ ] sinais de lideranca
- [ ] niveis de ingles
- [ ] criterios de modalidade
- [ ] criterios salariais
- [ ] regras de relaxed matching para teste
- [ ] termos usados em busca inicial por portal

Impactos arquiteturais a validar:

- [ ] reduzir dependencia direta de `llm/scoring.py` em `Settings` para criterios de negocio
- [ ] reduzir dependencia de heuristicas locais em listas hardcoded dentro de `llm/job_requirements.py`
- [ ] reutilizar a mesma taxonomia entre prompt, heuristica, parsing e validacao
- [ ] evitar divergencia entre configuracao de busca, scoring e extracao estruturada
- [ ] manter composicao na borda sem espalhar factories de criterio pelo codigo
- [ ] preservar testabilidade com perfis alternativos sem duplicar fixtures ou mocks demais

Problema explicitado a partir do uso real:

- [ ] Corrigir a lacuna entre perfil do candidato e perfil da busca atual
- [ ] Evitar que `relaxed_matching_for_testing` seja usado como substituto de configuracao real de senioridade alvo
- [ ] Permitir cenarios como "sou senior, mas quero buscar somente junior e pleno" sem precisar alterar codigo

Solucao arquitetural a avaliar e implementar depois:

- [ ] Separar explicitamente `candidate_profile` de `search_profile`
- [ ] Tornar senioridade alvo um criterio configuravel de primeira classe
- [ ] Adicionar algo equivalente a `allowed_seniority_levels`
- [ ] Adicionar uma politica explicita para `allow_unknown_seniority`
- [ ] Tornar configuraveis tambem outros criterios centrais da busca atual, e nao apenas senioridade
- [ ] Permitir configurar familias de cargo alvo, por exemplo:
  - [ ] `engenheiro de software`
  - [ ] `software engineer`
  - [ ] `desenvolvedor backend`
  - [ ] `analista desenvolvedor`
- [ ] Permitir configurar modalidades aceitas, por exemplo:
  - [ ] `remoto`
  - [ ] `hibrido`
  - [ ] `presencial`
- [ ] Permitir configurar stacks e palavras-chave prioritarias da busca atual
- [ ] Permitir configurar localidade ou regiao alvo quando fizer sentido
- [ ] Garantir que esses criterios facam parte do `search_profile`, e nao do `candidate_profile`
- [ ] Aplicar o criterio de senioridade de forma consistente em:
  - [ ] busca inicial por portal
  - [ ] prefiltro deterministico
  - [ ] scorer
  - [ ] rationale operacional
- [ ] Aplicar os demais criterios configuraveis de forma consistente em:
  - [ ] busca inicial por portal
  - [ ] prefiltro deterministico
  - [ ] scorer
  - [ ] rationale operacional
- [ ] Garantir que mudar entre junior, pleno, senior ou combinacoes seja apenas alteracao de configuracao, e nao de codigo

### OpenClaw como operador futuro ainda em analise

Descricao:
Existe uma hipotese de evolucao em que o OpenClaw opere a aplicacao como camada externa de orquestracao, consolidando contexto e executando etapas preparatorias, enquanto a decisao humana final por vaga permanece reduzida a uma unica acao de `sim` ou `nao`. O entendimento atual e que o OpenClaw nao deveria navegar diretamente no portal nem executar logica critica fora do sistema. O desenho mais plausivel e usar o `jobHunterAgent` como executor real, com OpenClaw preenchendo parametros, chamando operacoes publicas e organizando o fluxo como se fosse um operador da aplicacao. Essa direcao parece coerente como camada opcional de operacao, mas ainda exige analise de viabilidade, limites de autonomia e possiveis ajustes de estados e regras do produto.

- [ ] Avaliar OpenClaw apenas como operador externo da aplicacao, e nao como runtime principal do produto
- [ ] Registrar explicitamente que o `jobHunterAgent` continua como executor real de navegacao, coleta, preflight, submit e validacoes de estado
- [ ] Registrar explicitamente que OpenClaw atua como orquestrador e operador de interface, e nao como executor direto do portal
- [ ] Avaliar um fluxo futuro com apenas uma decisao humana final por vaga
- [ ] Validar se esse desenho preserva a regra de aprovacao humana antes de qualquer acao de alto impacto
- [ ] Validar o modelo operacional em que OpenClaw preenche parametros e usa o `jobHunterAgent` como interface operacional, sem acesso direto a banco ou bypass de estados
- [ ] Definir quais etapas poderiam ser automatizadas antes da decisao final:
  - [ ] coleta
  - [ ] scoring
  - [ ] extracao de sinais
  - [ ] priorizacao
  - [ ] preflight
  - [ ] consolidacao de resumo operacional
- [ ] Definir quais etapas devem continuar bloqueadas sem autorizacao humana explicita
- [ ] Definir explicitamente o que nao deve ser responsabilidade do OpenClaw:
  - [ ] navegar diretamente no LinkedIn fora do executor oficial
  - [ ] interpretar DOM cru como fonte de verdade operacional
  - [ ] criar transicoes de estado fora das regras do sistema
  - [ ] executar submit real fora do gate formal de autorizacao
- [ ] Registrar exemplos plausiveis de uso:
  - [ ] disparar coleta e consolidar a fila para revisao
  - [ ] pedir detalhes e sinais de vagas elegiveis
  - [ ] rodar preflight via operacao publica do sistema
  - [ ] apresentar um pacote consolidado para decisao final de `sim` ou `nao`
- [ ] Registrar exemplos nao recomendados:
  - [ ] autonomia longa sem contratos rigidos
  - [ ] submit sem gate explicito
  - [ ] regra de negocio implicita carregada pela LLM
  - [ ] navegacao e execucao real fora do `jobHunterAgent`
- [ ] Avaliar se o estado atual suporta bem um modelo de `uma decisao por vaga` ou se exige novos estados intermediarios
- [ ] Avaliar a necessidade de um estado consolidado equivalente a `pronta para decisao final`
- [ ] Garantir que OpenClaw nao altere estado critico fora das interfaces publicas e controladas do sistema
- [ ] Avaliar a necessidade de expor operacoes formais para o operador externo:
  - [x] listar fila
  - [x] detalhar vaga
  - [ ] aprovar ou rejeitar
  - [ ] preparar candidatura
  - [ ] rodar preflight
  - [ ] autorizar submit
  - [ ] executar submit quando permitido
- [ ] Definir o pacote minimo de contexto consolidado que deve voltar ao humano antes do `sim` ou `nao`:
  - [ ] dados normalizados da vaga
  - [ ] score e rationale
  - [ ] sinais extraidos
  - [ ] resultado do preflight
  - [ ] risco principal
  - [ ] motivo de bloqueio quando houver
- [ ] Avaliar se uma LLM local e suficiente para essa camada de orquestracao, desde que o escopo fique restrito a leitura de contexto, escolha de operacoes publicas e consolidacao de resposta
- [ ] Validar se o uso de LLM local continua plausivel apenas para orquestracao curta, e nao para autonomia longa com improvisacao operacional
- [ ] Avaliar se esse desenho reduz atrito operacional sem esconder demais o que foi feito automaticamente
- [ ] Avaliar impacto dessa abordagem no escopo atual do produto e no `AGENTS.md`

### Telegram e revisao

- [ ] Tornar o Telegram suficiente para operar o fluxo completo com seguranca
- [ ] Exibir melhor o motivo de `manual_review`
- [x] Exibir quando a vaga parece cair em `similar jobs`
- [x] Exibir quando a vaga exige perguntas adicionais

### Priorizacao

- [ ] Melhorar a selecao das vagas que valem tentativa automatica
- [ ] Evitar gastar preflight em vagas com alta chance de `manual_review`
- [ ] Dar preferencia a vagas com sinal forte de Easy Apply simples
- [ ] Avaliar ordenar a captura do LinkedIn por vagas mais recentes primeiro
- [ ] Avaliar parametrizar janela de recencia por portal, por exemplo ultimas 24h ou ultima semana
- [ ] Isolar a montagem desses filtros de recencia no adaptador do LinkedIn, sem espalhar parametros de URL pelo dominio

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

- [x] Fluxo de candidatura assistida opera sem `python -c`
- [x] Historico operacional deixa de depender de texto livre acumulado
- [x] Casos `similar jobs` e `perguntas adicionais` ficam claramente classificados
- [x] Regressao operacional principal permanece verde
- [x] Estrutura do codigo fica mais modular no fluxo LinkedIn
- [x] Telegram ou CLI passam a ser suficientes para operar o produto com seguranca
