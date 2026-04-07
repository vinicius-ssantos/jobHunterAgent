# AGENTS.md

## Objetivo

Este repositório implementa um assistente local-first para descoberta e triagem de vagas.

O escopo ativo do produto é:

- coletar vagas a partir de fontes configuradas
- normalizar e pontuar vagas contra um perfil profissional local
- persistir vagas relevantes localmente
- enviar vagas ao Telegram para revisão humana
- registrar decisões de aprovação ou rejeição
- suportar etapas assistidas de candidatura explicitamente autorizadas após confirmação humana

Fora de escopo por padrão:

- candidatura autônoma
- suporte multiusuário
- preocupações de SaaS
- persistência em nuvem
- funcionalidades genéricas de plataforma de agentes

## Convenções de Git e Branch

A política de branches e commits vem primeiro. Respeite isso antes de iniciar qualquer implementação.

Regra de GitFlow:

- seguir GitFlow de forma rígida no trabalho diário deste repositório
- `master` é a branch estável de integração e não deve ser usada para iniciar trabalho novo de implementação
- toda feature nova deve ser iniciada e desenvolvida em branch própria
- todo fix que não seja trivial deve ser isolado em branch própria
- toda refatoração arquitetural deve ser isolada em branch própria
- se a tarefa introduz nova capacidade de produto, novo comportamento configurável, novo comportamento de portal, novo fluxo operacional ou refatoração arquitetural, criar a branch antes
- branch primeiro, implementação depois

Nomenclatura recomendada:

- `feature/<tema-curto>`
- `fix/<tema-curto>`
- `refactor/<tema-curto>`
- `docs/<tema-curto>`

Exemplos:

- `feature/candidatura-assistida-arquitetura`
- `feature/perfil-busca-configuravel`
- `fix/linkedin-parser-residual`
- `refactor/separa-modulo-applicant`
- `docs/fluxo-candidatura-v1`

Regras de commit:

- sempre que houver modificações significativas ainda não commitadas, preparar e criar commits no padrão adotado no repositório
- as mensagens de commit devem ser escritas em português
- preferir commits pequenos, coerentes e com uma única razão clara para mudança

Expectativa operacional:

- features novas sempre começam em branch `feature/*`
- refactors amplos sempre começam em branch `refactor/*`
- fixes devem preferir branch `fix/*`, salvo quando forem muito pequenos e obviamente seguros
- trabalho só de documentação deve preferir branch `docs/*` quando fizer parte de uma linha de trabalho mais ampla
- trabalho direto em `master` deve ser tratado como exceção, não como padrão
- só fazer merge de volta quando a branch estiver coerente, validada e revisada de forma intencional

## Restrições de Produto

- Este é um sistema de uso pessoal.
- Aprovação humana é obrigatória antes de qualquer ação de alto impacto.
- Dados do candidato permanecem locais por padrão.
- Confiabilidade é mais importante que abrangência.
- Um fluxo estreito e estável é preferível a automação ampla e instável.

## Fonte de Verdade

- A aplicação ativa vive em `job_hunter_agent/`.
- `main.py` é apenas um entrypoint fino.
- Protótipos legados não devem ser usados como dependências de runtime.
- Não recriar `files/` nem qualquer arquitetura paralela equivalente.

## Fronteiras Arquiteturais

Manter responsabilidades separadas e direcionais:

- `job_hunter_agent/core/`
  Entidades de domínio, configurações validadas, helpers de runtime, suporte de browser e primitivas de identidade de vaga.
- `job_hunter_agent/application/`
  Composição de processo, orquestração de ciclo de vida, serviços de aplicação e regras do fluxo de revisão.
- `job_hunter_agent/collectors/`
  Orquestração de coleta, adaptadores de portal e automação específica do LinkedIn.
- `job_hunter_agent/infrastructure/`
  Persistência e adaptadores de transporte/renderização de notificações.
- `job_hunter_agent/llm/`
  Scoring assistivo, extração de requisitos, formatação de rationale e priorização de fila.
- `job_hunter_agent/__init__.py`
  Apenas entrypoint do pacote. Módulos de runtime devem ser importados dos subpacotes acima.

Regra de dependência:

- camadas externas podem depender de camadas internas
- domínio não deve depender de infraestrutura
- repositório, notifier e coletores externos são infraestrutura
- a composição da aplicação acontece na borda (`application/app.py` + `application/composition.py`), não espalhada pelos módulos de negócio

## Regras SOLID

### Single Responsibility Principle

- Cada módulo deve ter um único motivo para mudar.
- Não misturar lógica de domínio, persistência, transporte e wiring de processo na mesma classe.
- Se uma classe faz parsing, scoring, storage e mensageria, ela está grande demais.

### Open/Closed Principle

- Estender comportamento por interfaces e novas implementações, não adicionando branching por toda parte.
- Novos portais devem entrar atrás de abstrações de collector.
- Novos notifiers devem ser aditivos, sem exigir reescrita do fluxo de coleta.

### Liskov Substitution Principle

- Implementações de contratos de repositório, scorer, collector e notifier devem preservar o comportamento esperado.
- Dublês de teste devem se comportar como os contratos de produção, sem atalhos ocultos.

### Interface Segregation Principle

- Manter interfaces pequenas e orientadas à tarefa.
- Não forçar implementações a depender de métodos que não usam.
- Preferir protocolos focados a bases grandes e multipropósito.

### Dependency Inversion Principle

- O fluxo de negócio de alto nível deve depender de abstrações, não de detalhes concretos de infraestrutura.
- Serviços de aplicação devem receber repositórios, collectors, scorers e notifiers por injeção de dependência.
- Evitar construir infraestrutura profundamente dentro da lógica de negócio, salvo quando a composição na borda exigir.

## Regras de Domínio e Estado

Vagas devem usar apenas estados explícitos e estáveis.

Estados válidos atuais:

- `collected`
- `approved`
- `rejected`
- `error_collect`

Regras:

- nomes de status devem permanecer semanticamente estreitos
- não sobrecarregar um status com múltiplos significados
- não adicionar estados transitórios ou apenas de UI sem valor operacional claro
- toda transição de estado deve ser explícita e rastreável

Rascunhos e submissões de candidatura também devem usar apenas estados explícitos e estáveis.

Estados válidos atuais de candidatura:

- `draft`
- `ready_for_review`
- `confirmed`
- `authorized_submit`
- `submitted`
- `error_submit`
- `cancelled`

Regras:

- `authorized_submit` é o gate final de autorização humana antes de qualquer tentativa real de envio
- etapas de preflight e dry-run não podem pular silenciosamente esse gate
- automação de submit só pode rodar a partir de um estado explicitamente autorizado

## Regras de Coleta e Scoring

- Tratar portais externos como sistemas instáveis.
- Collectors são adaptadores de I/O e devem falhar independentemente por fonte.
- Falha em uma única fonte não deve abortar o ciclo inteiro.
- Normalizar dados brutos antes da persistência.
- Deduplicação deve acontecer antes de salvar ou despachar notificações.
- Preferir uma estratégia em duas etapas:
  - extração na fonte
  - scoring de relevância
- Usar rejeição por regra primeiro quando critérios de exclusão forem óbvios.
- Usar a LLM como scorer assistivo, não como autoridade incontestável.
- Scoring positivo deve produzir rationale curto.
- Nunca permitir que o modelo invente dados do candidato ausentes nas configurações.

## Regras de Uso de LLM Local

- Funcionalidades com LLM local são apenas assistivas e devem preservar fallback determinístico.
- Classificação de suporte, extração de requisitos, formatação de rationale e priorização de fila devem degradar com segurança quando o modelo falhar.
- Saídas de LLM devem ser parseadas em dados estruturados explícitos antes do uso.
- Respostas inválidas ou incompletas devem cair em comportamento conservador e determinístico.
- Metadados assistidos por LLM não podem sobrescrever silenciosamente dados confiáveis da fonte com conteúdo inventado.

## Regras de Telegram e Revisão

- Telegram é a interface de revisão humana.
- Notificações devem ser curtas, estruturadas e orientadas à ação.
- Um card de vaga deve incluir:
  - título
  - empresa
  - local
  - modalidade
  - texto salarial quando disponível
  - score de relevância
  - rationale
  - link da fonte
- Handlers de callback devem mapear para uma única transição de estado.
- Handlers devem ser idempotentes quando viável.
- Ações de revisão não devem disparar efeitos colaterais não relacionados.
- Ações de submit real devem permanecer explicitamente separadas de aprovação de review e preflight.
- Qualquer ação com potencial de submit deve exigir um estado dedicado de autorização humana antes da execução.

## Regras de Configuração

- Configuração deve falhar rápido quando inválida.
- Secrets placeholder nunca devem ser aceitos silenciosamente.
- Configurações obrigatórias devem ser validadas no startup.
- Defaults devem ser seguros para desenvolvimento e obviamente inválidos para secrets reais.
- Não espalhar lookups de configuração pelo código.
- Acessar configurações por um objeto validado.

## Regras de Persistência

- O código de repositório é dono de SQL e detalhes de schema.
- Objetos de domínio não devem conter preocupações específicas de SQLite.
- Manter o schema simples até o produto provar necessidade real de algo mais forte.
- Persistir metadados suficientes para depurar falhas operacionais.
- Evitar vazar shape de row de banco para camadas superiores.

## Tratamento de Erros e Observabilidade

- Falhas devem ser visíveis, não engolidas.
- Logar nas bordas da fonte com contexto suficiente para depuração posterior.
- Preferir degradação controlada a falha total.
- Mensagens voltadas ao usuário devem ser curtas.
- Logs internos devem preservar fonte, ação e motivo da falha.

## Padrões de Teste

Toda mudança não trivial deve preservar ou melhorar a verificação.

Expectativas mínimas:

- testes de repositório para persistência, deduplicação e resumos de estado
- testes de collector para normalização, filtragem e decisões de scoring
- testes de validação de settings quando regras de configuração mudarem
- testes de notifier quando comportamento de callback ou review mudar

Diretrizes de teste:

- preferir testes unitários para regras de negócio
- adicionar testes de integração apenas em seams críticos
- testar comportamento, não detalhe de implementação
- usar caminhos temporários locais dentro do workspace para testes seguros no sandbox

## Regras de Qualidade de Código

- Usar código compatível com Python 3.11+.
- Preferir nomes explícitos a nomes curtos e “espertos”.
- Manter funções e classes pequenas.
- Preferir dataclasses imutáveis para modelos de domínio.
- Evitar estado compartilhado oculto.
- Evitar abstração prematura, mas refatorar quando a duplicação se tornar estrutural.
- Usar ASCII, salvo quando o arquivo já justificar outra escolha.
- Comentários devem explicar intenção ou tradeoff não óbvio, não repetir o código.

## Controle de Mudança

Antes de mudar código, verificar:

- isso melhora o loop principal?
- isso preserva as fronteiras arquiteturais?
- isso reduz ou aumenta acoplamento?
- isso introduz comportamento implícito de runtime?
- isso exige atualização de README ou AGENTS?

Não adicionar features apenas porque são tecnicamente possíveis.

## Regra de Autoevolução

`AGENTS.md` não pode ficar defasado em relação ao código.

Sempre que uma mudança significativa entrar, reavaliar explicitamente se este arquivo ainda reflete:

- as fronteiras reais dos módulos
- o fluxo real de runtime
- a política atual de branch e commit
- as regras operacionais que o trabalho futuro deve seguir

Se a resposta for não, atualizar `AGENTS.md` na mesma linha de trabalho antes de considerar a tarefa concluída.

Ao fim de um trabalho substancial, fazer uma checagem curta:

- o `AGENTS.md` ainda descreve a arquitetura atual com veracidade?
- algum módulo ganhou ou perdeu responsabilidade?
- regras de processo, branching ou validação mudaram?

Se qualquer uma dessas respostas for sim, `AGENTS.md` deve ser atualizado imediatamente, sem postergar.

## Política de Branch

Usar as convenções acima como regra operacional padrão.

Casos em que branch dedicada é obrigatória:

- novas capacidades de produto fora do loop atualmente validado
- novos comportamentos configuráveis que afetem matching, review ou fluxo operacional
- refatorações arquiteturais que atravessem múltiplos módulos
- novos fluxos de automação com efeitos colaterais externos
- mudanças que introduzam novos estados, regras de persistência ou fluxos de review
- fluxos de aplicação específicos de portal

Casos em que trabalho direto na branch atual ainda pode ser aceitável:

- pequenos fixes
- limpeza localizada de parser
- mudanças só em testes
- mudanças só em documentação
- alinhamento de checklist sem impacto de runtime

Regra prática:

- se o trabalho pode desestabilizar `coletar -> normalizar -> ranquear -> persistir -> notificar -> revisar`, usar branch dedicada
- se o trabalho é uma feature nova, usar branch dedicada mesmo que a implementação pareça pequena
- se houver qualquer dúvida, criar a branch

## Antipadrões

- prompts gigantes que navegam, raciocinam, pontuam e agem ao mesmo tempo
- regras de negócio embutidas em handlers do Telegram
- infraestrutura instanciada em módulos aleatórios
- SQL direto fora da camada de repositório
- modelos de domínio conscientes de transporte ou storage
- reintroduzir candidatura autônoma no loop principal sem aprovação explícita de produto
- usar o repositório como playground para experimentos genéricos de agentes sem relação com o produto

## Definição de Pronto

Uma mudança só está completa quando:

- o loop `collect -> score -> persist -> notify -> review` continua funcionando
- responsabilidades permanecem corretamente separadas
- transições de estado continuam válidas
- o comportamento de falha é explícito
- testes cobrem o comportamento alterado ou uma lacuna concreta fica documentada
- documentação é atualizada quando runtime ou setup mudam
