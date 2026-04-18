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

## Produto

Objetivo do repositório:

- coletar vagas de fontes configuradas
- normalizar e pontuar vagas contra um perfil local
- persistir vagas relevantes localmente
- enviar vagas para revisão humana
- registrar aprovação ou rejeição
- executar etapas assistidas de candidatura somente após autorização humana explícita

## Fonte de Verdade

- a aplicação ativa vive em `job_hunter_agent/`
- `main.py` é apenas um entrypoint fino
- protótipos legados não entram no runtime
- não recriar arquiteturas paralelas como `files/`
- o runtime principal deve preferir a fonte estruturada de matching
- fallback legado existe apenas como compatibilidade temporária e explícita

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

## Matching

Quando tocar no matching:

- a fonte estruturada é o caminho principal
- o legado não deve voltar a ganhar protagonismo
- policy de senioridade deve ficar centralizada e reaproveitável
- prefiltro e scorer devem convergir nas mesmas regras principais
- não espalhe novas regras em strings soltas ou `if` locais quando houver policy/helper possível

## Configuração

Quando mexer em configuração:

- valide tudo no startup
- falhe rápido em caso inválido
- concentre acesso em um objeto de settings validado
- não espalhe lookup de variável de ambiente pelo código
- não reintroduza `JOB_HUNTER_PROFILE_TEXT` como centro de evolução do matching
- não trate fallback legado como equivalente ao caminho principal em código novo

## Testes

Toda mudança não trivial deve preservar ou melhorar a verificação.

- prefira teste unitário para regra de negócio
- use integração só em seams críticos
- teste comportamento, não detalhe interno
- quando migrar centro de gravidade arquitetural, adicione regressão cobrindo o caminho principal novo
