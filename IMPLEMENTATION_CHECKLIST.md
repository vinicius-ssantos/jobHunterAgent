# Checklist Detalhado de Implementacao do Job Hunter Agent

## Resumo

- [ ] Implementar o projeto como MVP local e pessoal.
- [ ] Manter foco exclusivo no ciclo `coletar -> normalizar -> ranquear -> persistir -> notificar -> revisar`.
- [ ] Garantir 1 portal confiavel na primeira entrega.
- [x] Garantir Telegram como interface de revisao humana.
- [ ] Garantir persistencia local com estados explicitos.
- [ ] Garantir tolerancia a falhas por fonte.
- [ ] Garantir cobertura de testes para regras centrais.

## Regra obrigatoria de fechamento

- [ ] Ao finalizar cada etapa, registrar:
- [ ] status da etapa
- [ ] comentario curto sobre o que foi concluido
- [ ] data da conclusao no formato `YYYY-MM-DD`
- [ ] Modelo obrigatorio de registro ao fim de cada etapa:

```text
Concluido em: YYYY-MM-DD
Comentario: <o que foi entregue, o que ficou pendente, riscos ou observacoes>
```

## Fase 1. Base estavel

- [x] Manter `main.py` como entrypoint fino.
- [x] Manter `job_hunter_agent/app.py` como unico ponto de composicao.
- [x] Garantir composicao explicita de `Settings`, `JobRepository`, `SiteCollector`, `JobScorer` e `ReviewNotifier`.
- [ ] Remover construcoes implicitas de infraestrutura fora da borda da aplicacao.
- [x] Unificar o fluxo `--agora` e o fluxo agendado.
- [x] Garantir startup validation.
- [x] Garantir shutdown limpo do notifier.
- [x] Garantir tratamento explicito de excecoes no ciclo principal.
- [ ] Resultado esperado:
- [ ] aplicacao roda com estrutura consistente
- [ ] sem divida arquitetural obvia
- [ ] Finalizacao da fase:
- [ ] registrar comentario
- [ ] registrar data

## Fase 2. Contratos e boundaries

- [x] Formalizar contratos em `collector.py`, `repository.py` e `notifier.py` com interfaces pequenas e estaveis.
- [x] Garantir que `domain.py` nao dependa de SQLite, Telegram, browser-use ou Ollama.
- [ ] Separar no coletor:
- [x] extracao
- [x] normalizacao
- [ ] scoring
- [x] filtragem por regra
- [x] deduplicacao via repositorio
- [x] Garantir que handlers do Telegram facam apenas transicao de estado e callbacks previstos.
- [ ] Resultado esperado:
- [ ] limites arquiteturais claros
- [ ] menor acoplamento
- [ ] Finalizacao da fase:
- [ ] registrar comentario
- [ ] registrar data

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
- [ ] Validar obrigatoriamente no startup:
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
- [ ] Resultado esperado:
- [ ] configuracao segura
- [ ] falha rapida quando invalida
- [ ] Finalizacao da fase:
- [ ] registrar comentario
- [ ] registrar data

## Fase 4. Persistencia e lifecycle

- [x] Manter `SqliteJobRepository` como implementacao principal.
- [x] Garantir unicidade por `url`.
- [x] Garantir fallback de deduplicacao por `external_key`.
- [ ] Preservar estados:
- [x] `collected`
- [x] `approved`
- [x] `rejected`
- [x] `error_collect`
- [ ] Adicionar consultas operacionais:
- [x] listagem por status
- [x] busca por id
- [x] resumo agregado
- [x] logs de coleta por site
- [x] Adicionar tabela de execucoes de coleta.
- [ ] Nao misturar revisao com estados futuros de aplicacao automatica.
- [ ] Resultado esperado:
- [ ] persistencia auditavel
- [ ] lifecycle claro
- [ ] Finalizacao da fase:
- [ ] registrar comentario
- [ ] registrar data

## Fase 5. Coleta real por adapter

- [x] Implementar coleta por adapter concreto de portal.
- [ ] Ordem recomendada:
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
- [ ] Definir `RawJob` minimo valido:
- [x] `title`
- [x] `company`
- [x] `url`
- [x] `source_site`
- [x] Permitir fallback textual controlado para demais campos.
- [ ] Resultado esperado:
- [ ] coleta real estavel em 1 portal
- [ ] Finalizacao da fase:
- [ ] registrar comentario
- [ ] registrar data

## Fase 6. Scoring e triagem

- [x] Manter estrategia em duas etapas:
- [x] filtros deterministicos
- [x] scoring por LLM
- [ ] Expandir regras deterministicas para:
- [x] termos excluidos
- [x] modalidade incompativel
- [x] salario abaixo do minimo quando parseavel
- [ ] Fazer o scorer retornar sempre:
- [x] nota de 1 a 10
- [x] rationale curta
- [x] decisao `accepted`
- [ ] Registrar em log:
- [x] vagas coletadas
- [x] vagas descartadas por regra
- [x] vagas descartadas por score
- [x] vagas persistidas
- [x] Evitar scoring de vagas incompletas ou invalidas.
- [ ] Resultado esperado:
- [ ] triagem relevante e explicavel
- [ ] Finalizacao da fase:
- [ ] registrar comentario
- [ ] registrar data

## Fase 7. Telegram e revisao

- [x] Manter o bot exclusivamente como interface de revisao humana.
- [ ] Garantir que cada card tenha:
- [x] titulo
- [x] empresa
- [x] local
- [x] modalidade
- [x] salario
- [x] score
- [x] rationale
- [x] link
- [x] Tornar callbacks idempotentes.
- [ ] Garantir:
- [x] aprovar item ja aprovado nao quebra
- [x] rejeitar item inexistente responde de forma segura
- [x] janela curta de polling no modo `--agora` para processar callbacks apos envio dos cards
- [ ] Melhorar comandos:
- [x] `/status` com resumo completo
- [x] `/pendentes` com amostra dos itens
- [x] `/recentes` opcional
- [ ] Nao acoplar callbacks a acoes fora do escopo do MVP.
- [ ] Resultado esperado:
  - [x] revisao humana operacional via Telegram
- [ ] Finalizacao da fase:
- [ ] registrar comentario
- [ ] registrar data

## Fase 8. Observabilidade e operacao

- [x] Definir logs minimos por ciclo:
- [x] inicio da coleta
- [x] fim da coleta
- [x] resultado por portal
- [x] numero de itens persistidos
- [x] falhas por adapter
- [ ] Padronizar mensagens para:
- [ ] erro de configuracao
- [x] erro de coleta
- [x] erro de parsing
- [x] erro de scoring
- [ ] erro de notificacao Telegram
- [x] Garantir que falhas de um portal nao derrubem as demais fontes.
- [ ] Manter mensagens ao usuario curtas.
- [ ] Deixar detalhes tecnicos em log local.
- [ ] Resultado esperado:
- [ ] operacao auditavel e depuravel
- [ ] Finalizacao da fase:
- [ ] registrar comentario
- [ ] registrar data

## Fase 9. Documentacao e convencoes

- [x] Atualizar `README.md` com arquitetura e setup reais.
- [ ] Manter `AGENTS.md` como politica tecnica.
- [ ] Documentar:
- [ ] escopo da v1
- [ ] dependencias locais
- [x] fluxo operacional
- [ ] limites conhecidos
- [ ] como adicionar novo adapter
- [x] Se usar `.env`, criar `.env.example`.
- [ ] Resultado esperado:
- [ ] documentacao coerente com o runtime
- [ ] Finalizacao da fase:
- [ ] registrar comentario
- [ ] registrar data

## Checklist de interfaces e tipos

- [ ] `Settings` permanece como contrato unico de configuracao validada.
- [ ] `SiteConfig` representa fonte ativa de coleta.
- [ ] `RawJob` representa contrato minimo entre adapter e pipeline.
- [ ] `ScoredJob` representa contrato de scoring.
- [ ] `JobPosting` representa entidade persistida e revisavel.
- [ ] `JobRepository` representa interface de persistencia.
- [ ] `SiteCollector` representa interface de adapters de coleta.
- [ ] `JobScorer` representa interface de scoring.
- [ ] `ReviewNotifier` representa interface de revisao humana.

## Checklist de testes

- [ ] Testes de settings:
- [x] falha com token placeholder
- [x] falha sem chat id
- [x] falha sem profile_text
- [x] falha sem sites ativos
- [x] falha com horario invalido
- [ ] Testes de repository:
- [x] persistencia de jobs validos
- [x] deduplicacao por `url`
- [x] deduplicacao por `external_key`
- [x] transicoes de estado validas
- [x] resumo agregado correto
- [x] tracking de collection runs
- [ ] Testes de collector:
- [x] adapter devolve `RawJob` minimo valido
- [x] vagas invalidas nao entram no pipeline
- [x] filtros deterministicos descartam termos proibidos
- [x] scorer converte resposta em `ScoredJob`
- [x] falha de um portal nao interrompe os demais
- [ ] Testes de notifier:
- [x] card com campos essenciais
- [x] approve altera status para `approved`
- [x] reject altera status para `rejected`
- [x] callback para job inexistente responde com seguranca
- [x] callback duplicado e idempotente
- [ ] Testes de integracao:
- [ ] ciclo `--agora` com doubles
- [ ] persistencia e revisao funcionando juntas
- [ ] Checagens estaticas:
- [x] `py_compile` dos modulos ativos
- [x] `unittest` rodando no workspace
- [x] `pytest` rodando no workspace

## Assuncoes

- [ ] Projeto continua de uso pessoal e local.
- [x] Telegram continua como interface principal de revisao.
- [ ] Ollama local continua obrigatorio para scoring.
- [ ] Automatic application continua fora do escopo.
- [x] O primeiro portal priorizado e LinkedIn.
- [ ] SQLite continua suficiente para a v1.

## Modelo de comentario de finalizacao

- [ ] Use sempre este padrao ao concluir qualquer fase ou bloco:

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
