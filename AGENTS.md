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

## Produto

Objetivo do repositório:

- coletar vagas de fontes configuradas
- normalizar e pontuar vagas contra um perfil local
- persistir vagas relevantes localmente
- enviar vagas para revisão humana
- registrar aprovação ou rejeição
- executar etapas assistidas de candidatura somente após autorização humana explícita

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

## Fonte de Verdade

- a aplicação ativa vive em `job_hunter_agent/`
- `main.py` é apenas um entrypoint fino
- protótipos legados não entram no runtime
- não recriar arquiteturas paralelas como `files/`

## Fronteiras Arquiteturais

Use estas responsabilidades:

- `job_hunter_agent/core/`
  domínio, settings validados, helpers de runtime, suporte de browser, identidade de vaga e contratos explícitos de compatibilidade
- `job_hunter_agent/application/`
  composição, orquestração, casos de uso e regras de revisão
- `job_hunter_agent/collectors/`
  coleta, adaptadores de portal e automação do LinkedIn
- `job_hunter_agent/infrastructure/`
  persistência e notificações
- `job_hunter_agent/llm/`
  scoring assistivo, extração de requisitos, rationale, priorização e interpretação assistida

Regra de dependência:

- camadas externas podem depender de camadas internas
- domínio não depende de infraestrutura
- wiring acontece na borda de composição, não espalhado pelos módulos
- compatibilidade legada deve passar por contrato explícito; não dependa do shape inteiro de `Settings` em módulos de negócio

## SOLID

Antes de implementar, confirme:

- SRP: este módulo tem um único motivo para mudar?
- OCP: estou estendendo comportamento sem espalhar `if`?
- LSP: implementações e dublês preservam o contrato?
- ISP: a interface está pequena e focada?
- DIP: o fluxo de negócio depende de abstrações e não de detalhes concretos?

## Controle De Escopo E Refatoracao

- use este arquivo como mapa de decisao, nao como licenca para reescrever areas vizinhas
- execute apenas o menor recorte necessario para concluir a tarefa atual com seguranca
- nao amplie escopo por aproveitar contexto sem necessidade direta

## Coleta e Scoring

Quando trabalhar no matching/scoring:

- aplique rejeição por regra primeiro
- use a LLM como scorer assistivo
- mantenha fallback determinístico
- nunca deixe o modelo inventar dados do candidato
- ao tocar caminho legado de matching, encapsule compatibilidade em helper/contrato explícito antes de expandir o uso

## Configuração

Quando mexer em configuração:

- valide tudo no startup
- falhe rápido em caso inválido
- concentre acesso em um objeto de settings validado
- não espalhe lookup de variável de ambiente pelo código
- não reintroduza `JOB_HUNTER_PROFILE_TEXT` como centro de evolução do matching

## Testes

Toda mudança não trivial deve preservar ou melhorar a verificação.

- prefira teste unitário para regra de negócio
- use integração só em seams críticos
- teste comportamento, não detalhe interno

## Workflow Depois de Implementar

Antes de encerrar a tarefa:

1. rode os testes relevantes
2. confirme que estados e transições continuam válidos
3. confirme que falhas continuam explícitas
4. atualize README se setup ou operação mudaram
5. atualize AGENTS se arquitetura, processo ou regras mudaram
6. prepare commits pequenos e em português
