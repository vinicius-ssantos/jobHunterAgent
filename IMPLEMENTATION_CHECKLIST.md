# Checklist Detalhado de Implementacao do Job Hunter Agent

## Resumo

- [x] Implementar o projeto como MVP local e pessoal.
- [x] Manter foco exclusivo no ciclo `coletar -> normalizar -> ranquear -> persistir -> notificar -> revisar`.
- [x] Garantir 1 portal confiavel na primeira entrega.
- [x] Garantir Telegram como interface de revisao humana.
- [x] Garantir persistencia local com estados explicitos.
- [x] Garantir tolerancia a falhas por fonte.
- [x] Garantir cobertura de testes para regras centrais.

## Regra obrigatoria de fechamento

- [x] Ao finalizar cada etapa, registrar:
- [x] status da etapa
- [x] comentario curto sobre o que foi concluido
- [x] data da conclusao no formato `YYYY-MM-DD`
- [x] Modelo obrigatorio de registro ao fim de cada etapa:

```text
Concluido em: YYYY-MM-DD
Comentario: <o que foi entregue, o que ficou pendente, riscos ou observacoes>
```

## Fase 1. Base estavel

- [x] Manter `main.py` como entrypoint fino.
- [x] Manter `job_hunter_agent/app.py` como unico ponto de composicao.
- [x] Garantir composicao explicita de `Settings`, `JobRepository`, `SiteCollector`, `JobScorer` e `ReviewNotifier`.
- [x] Remover construcoes implicitas de infraestrutura fora da borda da aplicacao.
- [x] Unificar o fluxo `--agora` e o fluxo agendado.
- [x] Garantir startup validation.
- [x] Garantir shutdown limpo do notifier.
- [x] Garantir tratamento explicito de excecoes no ciclo principal.
- [x] Resultado esperado:
- [x] aplicacao roda com estrutura consistente
- [x] sem divida arquitetural obvia
- [x] Finalizacao da fase:
- [x] registrar comentario
- [x] registrar data

## Fase 2. Contratos e boundaries

- [x] Formalizar contratos em `collector.py`, `repository.py` e `notifier.py` com interfaces pequenas e estaveis.
- [x] Garantir que `domain.py` nao dependa de SQLite, Telegram, browser-use ou Ollama.
- [x] Separar no coletor:
- [x] extracao
- [x] normalizacao
- [x] scoring
- [x] filtragem por regra
- [x] deduplicacao via repositorio
- [x] Garantir que handlers do Telegram facam apenas transicao de estado e callbacks previstos.
- [x] Resultado esperado:
- [x] limites arquiteturais claros
- [x] menor acoplamento
- [x] Finalizacao da fase:
- [x] registrar comentario
- [x] registrar data

## Fase 3. Configuracao para uso real

- [x] Manter `job_hunter_agent/settings.py` como fonte de configuracao validada.
- [x] Ler variaveis de ambiente com fallback explicito.
- [x] Formalizar setup hibrido recomendado:
- [x] aplicacao Python local
- [x] Playwright e Chromium locais em pasta do projeto
- [x] Ollama opcionalmente em Docker
- [x] Adicionar script de setup local para Playwright.
- [x] Ignorar browsers locais e `.env` no Git.
- [x] Redirecionar configuracao do `browser-use` para pasta local do projeto.
- [x] Validar obrigatoriamente no startup:
- [x] Telegram token
- [x] Telegram chat id
- [x] profile_text
- [x] ao menos um site ativo
- [x] horario valido
- [x] Adicionar caminho configuravel para banco.
- [ ] Adicionar caminho configuravel para logs, se necessario.
- [x] Eliminar valores magicos de modelo e URL do Ollama fora de settings.
- [x] Adicionar suporte a `.env` e `.env.example`.
- [x] Ajustar o modelo default do MVP para `qwen2.5:7b` por viabilidade operacional.
- [x] Criar `.env` inicial local para acelerar o primeiro teste real.
- [x] Resultado esperado:
- [x] configuracao segura
- [x] falha rapida quando invalida
- [x] Finalizacao da fase:
- [x] registrar comentario
- [x] registrar data

## Fase 4. Persistencia e lifecycle

- [x] Manter `SqliteJobRepository` como implementacao principal.
- [x] Garantir unicidade por `url`.
- [x] Garantir fallback de deduplicacao por `external_key`.
- [x] Preservar estados:
- [x] `collected`
- [x] `approved`
- [x] `rejected`
- [x] `error_collect`
- [x] Adicionar consultas operacionais:
- [x] listagem por status
- [x] busca por id
- [x] resumo agregado
- [x] logs de coleta por site
- [x] Adicionar tabela de execucoes de coleta.
- [x] Nao misturar revisao com estados futuros de aplicacao automatica.
- [ ] Resultado esperado:
- [x] persistencia auditavel
- [x] lifecycle claro
- [x] Finalizacao da fase:
- [x] registrar comentario
- [x] registrar data

## Fase 5. Coleta real por adapter

- [x] Implementar coleta por adapter concreto de portal.
- [x] Ordem recomendada:
- [x] LinkedIn
- [x] Gupy
- [x] Indeed
- [x] Garantir que cada adapter:
- [x] receba `SiteConfig`
- [x] busque vagas do portal
- [x] devolva `RawJob` normalizado
- [x] encapsule so a logica especifica do portal
- [x] Garantir tolerancia a mudancas de UI com logs uteis.
- [x] Garantir falha isolada por portal.
- [x] Definir `RawJob` minimo valido:
- [x] `title`
- [x] `company`
- [x] `url`
- [x] `source_site`
- [x] Permitir fallback textual controlado para demais campos.
- [x] Resultado esperado:
- [x] coleta real estavel em 1 portal
- [x] Finalizacao da fase:
- [x] registrar comentario
- [x] registrar data

## Fase 6. Scoring e triagem

- [x] Manter estrategia em duas etapas:
- [x] filtros deterministicos
- [x] scoring por LLM
- [x] Expandir regras deterministicas para:
- [x] termos excluidos
- [x] modalidade incompativel
- [x] salario abaixo do minimo quando parseavel
- [x] Fazer o scorer retornar sempre:
- [x] nota de 1 a 10
- [x] rationale curta
- [x] decisao `accepted`
- [x] Registrar em log:
- [x] vagas coletadas
- [x] vagas descartadas por regra
- [x] vagas descartadas por score
- [x] vagas persistidas
- [x] Evitar scoring de vagas incompletas ou invalidas.
- [x] Resultado esperado:
- [x] triagem relevante e explicavel
- [x] Finalizacao da fase:
- [x] registrar comentario
- [x] registrar data

## Fase 7. Telegram e revisao

- [x] Manter o bot exclusivamente como interface de revisao humana.
- [x] Garantir que cada card tenha:
- [x] titulo
- [x] empresa
- [x] local
- [x] modalidade
- [x] salario
- [x] score
- [x] rationale
- [x] link
- [x] Tornar callbacks idempotentes.
- [x] Garantir:
- [x] aprovar item ja aprovado nao quebra
- [x] rejeitar item inexistente responde de forma segura
- [x] janela curta de polling no modo `--agora` para processar callbacks apos envio dos cards
- [x] Melhorar comandos:
- [x] `/status` com resumo completo
- [x] `/pendentes` com amostra dos itens
- [x] `/recentes` opcional
- [x] `/candidaturas` com visibilidade dos rascunhos e candidaturas em andamento
- [x] Nao acoplar callbacks a acoes fora do escopo do MVP.
- [ ] Resultado esperado:
  - [x] revisao humana operacional via Telegram
- [x] Finalizacao da fase:
- [x] registrar comentario
- [x] registrar data

## Fase 8. Observabilidade e operacao

- [x] Definir logs minimos por ciclo:
- [x] inicio da coleta
- [x] fim da coleta
- [x] resultado por portal
- [x] numero de itens persistidos
- [x] falhas por adapter
- [x] Padronizar mensagens para:
- [x] erro de configuracao
- [x] erro de coleta
- [x] erro de parsing
- [x] erro de scoring
- [x] erro de notificacao Telegram
- [x] Garantir que falhas de um portal nao derrubem as demais fontes.
- [x] Manter mensagens ao usuario curtas.
- [x] Deixar detalhes tecnicos em log local.
- [x] Resultado esperado:
- [x] operacao auditavel e depuravel
- [x] Finalizacao da fase:
- [x] registrar comentario
- [x] registrar data

## Fase 9. Documentacao e convencoes

- [x] Atualizar `README.md` com arquitetura e setup reais.
- [x] Manter `AGENTS.md` como politica tecnica.
- [x] Documentar:
- [x] escopo da v1
- [x] dependencias locais
- [x] fluxo operacional
- [x] limites conhecidos
- [x] como adicionar novo adapter
- [x] Se usar `.env`, criar `.env.example`.
- [x] Resultado esperado:
- [x] documentacao coerente com o runtime
- [x] Finalizacao da fase:
- [x] registrar comentario
- [x] registrar data

## Checklist de interfaces e tipos

- [x] `Settings` permanece como contrato unico de configuracao validada.
- [x] `SiteConfig` representa fonte ativa de coleta.
- [x] `RawJob` representa contrato minimo entre adapter e pipeline.
- [x] `ScoredJob` representa contrato de scoring.
- [x] `JobPosting` representa entidade persistida e revisavel.
- [x] `JobRepository` representa interface de persistencia.
- [x] `SiteCollector` representa interface de adapters de coleta.
- [x] `JobScorer` representa interface de scoring.
- [x] `ReviewNotifier` representa interface de revisao humana.

## Checklist de testes

- [x] Testes de settings:
- [x] falha com token placeholder
- [x] falha sem chat id
- [x] falha sem profile_text
- [x] falha sem sites ativos
- [x] falha com horario invalido
- [x] Testes de repository:
- [x] persistencia de jobs validos
- [x] deduplicacao por `url`
- [x] deduplicacao por `external_key`
- [x] transicoes de estado validas
- [x] resumo agregado correto
- [x] tracking de collection runs
- [x] Testes de collector:
- [x] adapter devolve `RawJob` minimo valido
- [x] vagas invalidas nao entram no pipeline
- [x] filtros deterministicos descartam termos proibidos
- [x] scorer converte resposta em `ScoredJob`
- [x] falha de um portal nao interrompe os demais
- [x] Testes de notifier:
- [x] card com campos essenciais
- [x] approve altera status para `approved`
- [x] reject altera status para `rejected`
- [x] callback para job inexistente responde com seguranca
- [x] callback duplicado e idempotente
- [x] Testes de integracao:
- [x] ciclo `--agora` com doubles
- [x] persistencia e revisao funcionando juntas
- [x] Checagens estaticas:
- [x] `py_compile` dos modulos ativos
- [x] `unittest` rodando no workspace
- [x] `pytest` rodando no workspace

## Assuncoes

- [x] Projeto continua de uso pessoal e local.
- [x] Telegram continua como interface principal de revisao.
- [x] Ollama local continua obrigatorio para scoring.
- [x] Automatic application continua fora do escopo.
- [x] O primeiro portal priorizado e LinkedIn.
- [x] SQLite continua suficiente para a v1.

## Pre-fase de candidatura assistida

- [x] Separar candidatura dos estados de revisao de vaga.
- [x] Criar contrato proprio para submissao futura em `job_hunter_agent/applicant.py`.
- [x] Persistir rascunhos e tentativas de candidatura em tabela separada.
- [x] Manter candidatura fora do loop principal ate haver confirmacao humana forte.
- [x] Preservar estados proprios de candidatura:
- [x] `draft`
- [x] `ready_for_review`
- [x] `confirmed`
- [x] `submitted`
- [x] `error_submit`
- [x] `cancelled`
- [x] Garantir consultas operacionais basicas:
- [x] busca por candidatura via `job_id`
- [x] listagem por status
- [x] resumo agregado
- [x] Integrar candidatura assistida ao fluxo humano de revisao.
- [x] Classificar rascunhos entre `auto_supported`, `manual_review` e `unsupported`.
- [x] Permitir confirmacao humana explicita da candidatura antes de qualquer submissao.
- [ ] Implementar automacao real de candidatura por portal.

## Modelo de comentario de finalizacao

- [x] Use sempre este padrao ao concluir qualquer fase ou bloco:

```text
Concluido em: YYYY-MM-DD
Comentario: <resumo objetivo do que foi finalizado, impacto, pendencias e riscos se houver>
```

Concluido em: 2026-04-03
Comentario: arquivo de checklist criado na raiz com o plano detalhado em formato operacional e com a regra obrigatoria de comentario final com data.

Concluido em: 2026-04-03
Comentario: configuracao por ambiente, tracking de execucoes, filtros deterministicos, callbacks idempotentes e comando /recentes foram implementados e validados por testes.

Concluido em: 2026-04-03
Comentario: a configuracao foi migrada para pydantic-settings com suporte a .env, pytest foi adicionado como runner padrao de testes e o ambiente foi validado com 19 testes passando.

Concluido em: 2026-04-03
Comentario: a coleta foi reestruturada em adapters explicitos por portal com LinkedIn, Gupy e Indeed, com validacao minima de RawJob, falha isolada por fonte e testes ampliados para 25 casos aprovados.

Concluido em: 2026-04-03
Comentario: o scorer passou a tratar resposta malformada e falha de modelo sem derrubar o ciclo, a deduplicacao por external_key foi reforcada no repositorio e a suite foi ampliada para 33 testes aprovados cobrindo settings, repository, collector e notifier.

Concluido em: 2026-04-03
Comentario: o setup hibrido recomendado foi incorporado ao projeto com `.gitignore`, script local para instalar Playwright Chromium em `.playwright-browsers` e documentacao atualizada para manter browser local e Ollama opcionalmente em Docker.

Concluido em: 2026-04-03
Comentario: o modelo padrao do projeto foi reduzido para a variante 7B viavel do catalogo atual do Ollama, `qwen2.5:7b`, em configuracao e documentacao para melhorar a viabilidade operacional do MVP na maquina alvo.

Concluido em: 2026-04-03
Comentario: um `.env` inicial local foi criado com placeholders seguros e com o modelo correto do Ollama, removendo o bloqueio de bootstrap para o primeiro teste controlado do projeto.

Concluido em: 2026-04-03
Comentario: a configuracao do `browser-use` foi redirecionada para a pasta local `.browseruse`, eliminando a dependencia de escrita em `~/.config` e removendo o bloqueio de permissao encontrado no primeiro teste real.

Concluido em: 2026-04-03
Comentario: o escopo do primeiro teste real foi reduzido para LinkedIn apenas, diminuindo tempo de execucao e superficie de erro para a validacao inicial do MVP.

Concluido em: 2026-04-03
Comentario: foi adicionado um modo `--sem-telegram` com notifier nulo para permitir validacao real de coleta, scoring e persistencia sem depender da rede do bot durante o diagnostico inicial.

Concluido em: 2026-04-03
Comentario: o navegador passou a ser configuravel por ambiente e o setup local foi deixado em modo visual (`headless=false`) para facilitar a depuracao do fluxo real no LinkedIn.

Concluido em: 2026-04-03
Comentario: a observabilidade da coleta foi reforcada com timeout explicitamente logado por portal, duracao da automacao, trecho da resposta bruta quando o parser nao encontra JSON valido e resumo por portal incluindo vagas aprovadas e duplicadas.

Concluido em: 2026-04-03
Comentario: o LinkedIn deixou de depender do fluxo aberto do agente e passou a usar uma coleta deterministica autenticada via Playwright e `storage_state`, enquanto os demais portais continuam no caminho adaptativo existente.

Concluido em: 2026-04-03
Comentario: os testes passaram a saneiar `.tmp-tests` automaticamente, mantendo apenas o diretorio temporario mais recente por execucao para evitar acúmulo de lixo no workspace.

Concluido em: 2026-04-03
Comentario: a normalizacao do LinkedIn foi endurecida para limpar `title`, `company`, `summary` e `description`, separar melhor `location` e `work_mode` e remover metadados de card como `Promovida`, `with verification`, `Candidatura simplificada`, `Visualizado` e contadores de candidaturas.

Concluido em: 2026-04-03
Comentario: o fluxo completo com Telegram foi validado em execucao real, com polling iniciado, ciclo de coleta concluido e cards enviados com sucesso para revisao humana.

Concluido em: 2026-04-03
Comentario: o modo `--agora` com Telegram passou a manter uma janela curta de polling apos o envio dos cards, permitindo que callbacks de aprovacao e rejeicao sejam processados antes do encerramento do processo.

Concluido em: 2026-04-03
Comentario: a execucao real do MVP confirmou persistencia local com estados explicitos, cobertura dos testes centrais e o ciclo completo de revisao humana no Telegram com transicoes para `approved` e `rejected`.

Concluido em: 2026-04-04
Comentario: as fases centrais do MVP foram consolidadas na checklist com base no runtime real do LinkedIn, no ciclo completo de revisao via Telegram e na estabilizacao do parsing residual com detalhe da vaga e fallback local de repair.

Concluido em: 2026-04-04
Comentario: a checklist foi alinhada ao estado real do MVP e o parser residual do LinkedIn foi endurecido para evitar fragmentos de local como empresa, preservar localizacoes explicitas validas e acionar repair local apenas nos casos realmente suspeitos; o run real 53 persistiu vagas novas com campos limpos.

Concluido em: 2026-04-04
Comentario: a pre-fase de candidatura assistida foi aberta com contratos proprios, tabela separada de persistencia e testes de repositorio cobrindo rascunho, transicoes de status, listagem e resumo; nada foi acoplado ao loop principal nem habilitou candidatura automatica.

Concluido em: 2026-04-04
Comentario: a aprovacao humana no Telegram agora cria rascunhos de candidatura apenas para vagas `approved`, usando um servico proprio de preparacao; isso integra a pre-fase ao fluxo real sem habilitar submissao automatica.

Concluido em: 2026-04-04
Comentario: o Telegram ganhou visibilidade da pre-fase de candidatura via comando `/candidaturas`, mostrando resumo e fila de rascunhos/candidaturas em andamento sem adicionar automacao de submissao.

Concluido em: 2026-04-04
Comentario: a pre-fase de candidatura passou a classificar cada rascunho como `auto_supported`, `manual_review` ou `unsupported`, e o comando `/candidaturas` agora expõe essa classificacao para orientar a futura automacao por portal.

Concluido em: 2026-04-04
Comentario: a classificacao conservadora de aplicabilidade foi integrada ao fluxo real dos rascunhos de candidatura e passou a ficar visivel no Telegram, distinguindo claramente o que pode entrar em automacao futura do que deve permanecer manual ou nao suportado.

Concluido em: 2026-04-04
Comentario: o Telegram passou a permitir a progressao humana explicita dos rascunhos de candidatura entre `draft`, `ready_for_review`, `confirmed` e `cancelled`, mantendo a submissao automatica ainda fora do fluxo.
