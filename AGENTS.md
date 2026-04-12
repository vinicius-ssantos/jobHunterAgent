# AGENTS.md

## Prioridade

Siga esta ordem em todo trabalho:

1. respeitar GitFlow e convenções de branch/commit
2. preservar o loop principal do produto
3. manter as fronteiras arquiteturais
4. preferir mudanças pequenas, explícitas e testáveis
5. atualizar documentação quando a verdade do sistema mudar

## GitFlow

Quando iniciar trabalho novo:

- se for feature nova, crie uma branch `feature/*` antes de implementar
- se for refatoração ampla, crie uma branch `refactor/*` antes de implementar
- se for fix não trivial, crie uma branch `fix/*` antes de implementar
- se for documentação ligada a uma linha de trabalho ampla, use `docs/*`

Regras:

- `master` é a branch estável
- não iniciar feature nova diretamente em `master`
- branch primeiro, implementação depois
- commits devem ser em português
- prefira commits pequenos e coerentes

## Higiene De Branch

Para evitar branches defasadas e regressões por rebase:

- se uma branch for continuar viva por mais de uma linha de trabalho, rebaseie em `master` antes de seguir implementando
- antes de mergear ou retomar uma branch antiga, compare `ahead/behind` contra `master`
- apague branch local sem trabalho exclusivo assim que ela for absorvida por `master`
- não preserve branch só por inércia; ou ela segue viva com escopo claro, ou deve ser encerrada

Quando houver rebase, cherry-pick ou porte manual de commit:

- nunca reintroduza arquivos em caminhos antigos só porque existiam no commit original
- sempre porte a mudança para a arquitetura atual do projeto
- se um commit antigo tocar módulos que já mudaram de camada, adapte a mudança em vez de restaurar a estrutura anterior
- após resolver conflito, rode os testes focados da área portada antes de continuar

Exemplos aceitos:

- `feature/perfil-busca-configuravel`
- `refactor/separa-fluxo-candidatura`
- `fix/linkedin-preflight-url`

Exemplos não aceitos:

- começar feature nova em `master`
- juntar refactor, feature e docs no mesmo commit sem necessidade

## Produto

Objetivo do repositório:

- coletar vagas de fontes configuradas
- normalizar e pontuar vagas contra um perfil local
- persistir vagas relevantes localmente
- enviar vagas para revisão humana
- registrar aprovação ou rejeição
- executar etapas assistidas de candidatura somente após autorização humana explícita

Fora de escopo por padrão:

- candidatura autônoma
- multiusuário
- SaaS
- persistência em nuvem
- plataforma genérica de agentes

## Restrições do Produto

- uso pessoal
- dados do candidato permanecem locais por padrão
- confiabilidade vale mais que abrangência
- o fluxo estreito e estável vale mais que automação ampla e instável
- toda ação de alto impacto exige aprovação humana

## Fluxo Principal

O sistema só está correto quando este loop continua íntegro:

`coletar -> normalizar -> ranquear -> persistir -> notificar -> revisar`

Para candidaturas, o gate obrigatório é:

`draft -> ready_for_review -> confirmed -> authorized_submit -> submitted`

Regras:

- `authorized_submit` é o gate final antes de submit real
- preflight e dry-run não podem pular esse gate
- submit real só pode sair de `authorized_submit`

## Fonte de Verdade

- a aplicação ativa vive em `job_hunter_agent/`
- `main.py` é apenas um entrypoint fino
- protótipos legados não entram no runtime
- não recriar arquiteturas paralelas como `files/`

## Fronteiras Arquiteturais

Use estas responsabilidades:

- `job_hunter_agent/core/`
  domínio, settings validados, helpers de runtime, suporte de browser e identidade de vaga
- `job_hunter_agent/application/`
  composição, orquestração, casos de uso e regras de revisão
- `job_hunter_agent/collectors/`
  coleta, adaptadores de portal e automação do LinkedIn
- `job_hunter_agent/infrastructure/`
  persistência e notificações
- `job_hunter_agent/llm/`
  scoring assistivo, extração de requisitos, rationale, priorização, interpretação assistida de modal e sugestão de perfil estruturado do candidato

Regra de dependência:

- camadas externas podem depender de camadas internas
- domínio não depende de infraestrutura
- wiring acontece na borda de composição, não espalhado pelos módulos

## SOLID

Antes de implementar, confirme:

- SRP: este módulo tem um único motivo para mudar?
- OCP: estou estendendo comportamento sem espalhar `if`?
- LSP: implementações e dublês preservam o contrato?
- ISP: a interface está pequena e focada?
- DIP: o fluxo de negócio depende de abstrações e não de detalhes concretos?

Se a resposta for não, ajuste a estrutura antes de continuar.

## Controle De Escopo E Refatoracao

Siga um padrao de `AGENTS.md` curto, objetivo e acionavel:

- use este arquivo como mapa de decisao, nao como licenca para reescrever areas vizinhas
- execute apenas o menor recorte necessario para concluir a tarefa atual com seguranca
- nao amplie escopo por "aproveitar o contexto" sem necessidade direta

Refatoracao so e aceitavel sem confirmacao extra quando:

- remove acoplamento que bloqueia a tarefa atual
- corrige uma regressao descoberta durante a implementacao
- reduz duplicacao estrutural no mesmo seam tocado pela tarefa

Pare e replaneje antes de continuar quando a mudanca passar de um recorte local. Trate como refatoracao ampla quando ocorrer qualquer um destes sinais:

- tocar mais de 3 modulos principais na mesma linha de trabalho
- atravessar mais de uma camada arquitetural sem ser wiring explicito
- misturar feature, refactor e limpeza geral no mesmo passo
- exigir renomeacao ou redistribuicao de responsabilidades em cadeia
- fechar mais de um item grande de checklist sem validacao intermediaria

Quando houver refatoracao ampla:

- quebre em etapas pequenas e testaveis
- valide cada etapa antes de seguir para a proxima
- atualize a checklist conforme cada seam for realmente concluido
- nao marque item pai como concluido so por proximidade; marque apenas quando houver lastro claro no codigo e nos testes

## Regras de Estado

Estados válidos de vaga:

- `collected`
- `approved`
- `rejected`
- `error_collect`

Estados válidos de candidatura:

- `draft`
- `ready_for_review`
- `confirmed`
- `authorized_submit`
- `submitted`
- `error_submit`
- `cancelled`

Use apenas estados explícitos e semanticamente estreitos.

Não faça:

- estados transitórios só de UI
- um mesmo status com múltiplos significados
- transição implícita sem registro

## Coleta e Scoring

Quando trabalhar na coleta:

- trate portais como sistemas instáveis
- isole falhas por fonte
- normalize antes de persistir
- deduplique antes de salvar ou notificar

Quando trabalhar no matching/scoring:

- aplique rejeição por regra primeiro
- use a LLM como scorer assistivo
- mantenha fallback determinístico
- nunca deixe o modelo inventar dados do candidato

## LLM Local

Use LLM local apenas para apoio:

- classificação de suporte
- extração de requisitos
- formatação de rationale
- priorização de fila
- interpretação assistida onde já houver fallback seguro

Sempre:

- parsear resposta em estrutura explícita
- cair para comportamento conservador em caso de erro
- impedir sobrescrita silenciosa de dados confiáveis

## Telegram e CLI

Telegram é interface de revisão humana.
CLI é interface operacional principal ou fallback técnico.

Quando adicionar ação operacional:

- mantenha a ação curta e rastreável
- faça cada handler mapear para uma única transição de estado
- mantenha ações de review separadas de ações de submit
- preserve o gate humano antes de submit real

## Configuração

Quando mexer em configuração:

- valide tudo no startup
- falhe rápido em caso inválido
- não aceite placeholders silenciosamente
- concentre acesso em um objeto de settings validado
- não espalhe lookup de variável de ambiente pelo código

## Persistência

Quando mexer em banco/repositório:

- deixe SQL e schema dentro da camada de repositório
- mantenha o domínio livre de detalhes de SQLite
- persista metadados suficientes para depuração operacional
- não exponha shape de row para camadas superiores

## Erros e Observabilidade

Quando tratar falhas:

- não engula erro silenciosamente
- registre contexto na borda da fonte
- diferencie bloqueio funcional, erro de portal e falha inesperada
- mantenha mensagem operacional curta
- mantenha log interno útil para depuração

## Testes

Toda mudança não trivial deve preservar ou melhorar a verificação.

Mínimo esperado por tipo de mudança:

- repositório: persistência, deduplicação, resumos e transições
- collectors: normalização, filtros e scoring
- settings: validação
- notifier: callbacks e review

Diretrizes:

- prefira teste unitário para regra de negócio
- use integração só em seams críticos
- teste comportamento, não detalhe interno
- use caminhos temporários dentro do workspace

## Qualidade de Código

- use Python 3.11+
- prefira nomes explícitos
- mantenha funções e classes pequenas
- prefira dataclasses imutáveis no domínio
- evite estado compartilhado oculto
- evite abstração prematura
- refatore quando a duplicação ficar estrutural
- use comentários só para intenção ou tradeoff não óbvio

## Workflow Antes de Implementar

Antes de escrever código, responda:

1. isso melhora o loop principal?
2. isso está dentro do escopo do produto?
3. isso preserva as fronteiras arquiteturais?
4. isso reduz ou aumenta acoplamento?
5. isso introduz comportamento implícito de runtime?
6. isso exige branch dedicada?
7. isso exige atualização de README ou AGENTS?

Se houver dúvida sobre branch, crie a branch.

## Workflow Depois de Implementar

Antes de encerrar a tarefa:

1. rode os testes relevantes
2. confirme que estados e transições continuam válidos
3. confirme que falhas continuam explícitas
4. atualize README se setup ou operação mudaram
5. atualize AGENTS se arquitetura, processo ou regras mudaram
6. prepare commits pequenos e em português

## Regra de Autoatualização

`AGENTS.md` não pode ficar atrás da realidade do código.

Atualize este arquivo na mesma linha de trabalho quando mudar:

- a arquitetura real
- o fluxo operacional real
- a política de branch/commit
- regras de validação ou de estados

## Antipadrões

Evite:

- prompts gigantes que navegam, raciocinam, pontuam e agem ao mesmo tempo
- regra de negócio em handler de Telegram
- infraestrutura instanciada aleatoriamente em módulos de negócio
- SQL fora do repositório
- modelos de domínio conscientes de transporte ou storage
- reintroduzir candidatura autônoma no loop principal sem decisão explícita de produto
- usar o repositório como playground de agente genérico

## Definição de Pronto

Uma mudança só está pronta quando:

- o loop principal continua funcionando
- as responsabilidades seguem separadas
- os estados continuam válidos
- o comportamento de falha está explícito
- os testes cobrem a mudança ou a lacuna está documentada
- a documentação necessária foi atualizada
