# Funcionalidades do Projeto

## Escopo Atual

O `jobHunterAgent` e um sistema local para:ACHO 

- coletar vagas de fontes configuradas
- normalizar e pontuar vagas contra um perfil local
- persistir vagas relevantes
- enviar vagas para revisao humana
- registrar aprovacao ou rejeicao
- preparar, validar e submeter candidaturas assistidas no LinkedIn somente com gate humano explicito

Fora de escopo por padrao:

- candidatura autonoma
- multiusuario
- SaaS
- persistencia em nuvem
- plataforma generica de agentes

## Funcionalidades Principais

### 1. Coleta de vagas

O sistema consegue:

- rodar ciclos de coleta por portal habilitado
- controlar timeout por portal
- evitar reprocessar vagas ja vistas
- registrar logs de coleta e execucoes
- manter cursor operacional quando aplicavel

Resultados esperados:

- novas vagas coletadas entram no banco com status `collected`
- falhas de coleta ficam registradas explicitamente

### 2. Normalizacao e triagem

O pipeline de triagem faz:

- validacao minima da vaga
- limpeza e normalizacao de campos
- prefiltro deterministico por regras
- scoring hibrido com apoio de LLM
- descarte controlado de vagas fora do perfil

Sinais usados hoje:

- palavras-chave de inclusao/exclusao
- modalidade de trabalho
- salario minimo quando houver
- relevancia minima

### 3. Persistencia local

O sistema persiste localmente:

- vagas
- eventos de status da vaga
- candidaturas
- eventos da candidatura
- ciclos de coleta
- logs operacionais
- vagas vistas e deduplicacao

Objetivo:

- permitir operacao rastreavel
- manter historico suficiente para depuracao
- evitar depender de texto livre para operar o fluxo principal

### 4. Revisao humana

O sistema oferece revisao humana por:

- CLI
- Telegram

Acoes de revisao de vaga:

- listar fila
- detalhar vaga
- aprovar vaga
- rejeitar vaga

Regra:

- nenhuma acao de candidatura real deve acontecer sem aprovacao humana anterior

### 5. Fluxo de candidatura assistida

O sistema suporta o fluxo:

`draft -> ready_for_review -> confirmed -> authorized_submit -> submitted`

Capacidades:

- criar rascunho de candidatura a partir de vaga aprovada
- preparar candidatura
- confirmar candidatura pronta para revisao
- cancelar candidatura
- listar candidaturas por status
- mostrar detalhe e eventos da candidatura

### 6. Preflight de candidatura no LinkedIn

O preflight existe para validar a chance de submit antes da autorizacao final.

O sistema consegue:

- abrir o fluxo Easy Apply
- detectar bloqueios conhecidos
- identificar quando a vaga cai em `similar jobs`
- identificar quando ha perguntas adicionais obrigatorias
- detectar review final com submit visivel
- registrar resultado operacional do preflight
- capturar artefatos quando a falha e relevante

Regra:

- preflight nao executa submit real
- preflight nao pula o gate `authorized_submit`

### 7. Submit real assistido no LinkedIn

O submit real existe somente para candidaturas que ja passaram pelo gate humano.

O sistema consegue:

- validar readiness minima antes de enviar
- usar sessao autenticada do LinkedIn
- executar o submit real quando permitido
- atualizar status e eventos de candidatura
- registrar falhas explicitas e detalhes do ultimo submit

Regra:

- submit real so pode sair de `authorized_submit`

### 8. Captura de artefatos

Quando ocorre falha relevante no fluxo LinkedIn, o sistema pode salvar:

- metadados do erro
- screenshot
- HTML ou material de apoio disponivel

Objetivo:

- facilitar depuracao operacional
- tornar casos inconclusivos rastreaveis

### 9. Resumo operacional

O sistema expoe visao operacional por:

- resumo de status de vagas
- resumo de status de candidaturas
- fila operacional por status
- eventos recentes de candidatura
- artefatos recentes de falha
- resumo final por execucao

### 10. Perfil estruturado do candidato

O sistema inclui suporte a perfil estruturado local do candidato.

Capacidades atuais:

- extrair texto do curriculo
- sugerir anos de experiencia por tecnologia com apoio de LLM
- mesclar sugestoes no arquivo de perfil local

Objetivo:

- apoiar matching e candidatura sem inventar dados silenciosamente

## Interfaces Disponiveis Hoje

### CLI

Comandos de alto nivel:

- `status`
- `jobs list`
- `jobs show`
- `jobs approve`
- `jobs reject`
- `applications list`
- `applications create`
- `applications show`
- `applications events`
- `applications prepare`
- `applications confirm`
- `applications cancel`
- `applications artifacts`
- `applications preflight`
- `applications authorize`
- `applications submit`
- `candidate-profile suggest`

Modos de execucao:

- ciclo imediato com `--agora`
- varios ciclos com `--ciclos`
- execucao sem Telegram com `--sem-telegram`
- bootstrap de sessao autenticada do LinkedIn

### Telegram

Capacidades atuais:

- notificar vagas para revisao
- aprovar ou rejeitar vagas via callback
- acionar operacoes curtas ligadas ao fluxo de candidatura

Papel:

- revisao assincrona opcional
- nao substitui a CLI como interface operacional principal

## Estados Oficiais

### Status de vaga

- `collected`
- `approved`
- `rejected`
- `error_collect`

### Status de candidatura

- `draft`
- `ready_for_review`
- `confirmed`
- `authorized_submit`
- `submitted`
- `error_submit`
- `cancelled`

## Regras de Produto Que Moldam as Funcionalidades

- uso pessoal e local-first
- dados do candidato permanecem locais por padrao
- gate humano obrigatorio antes de submit real
- confiabilidade vale mais que abrangencia
- LLM e suporte assistivo, nao executor soberano do fluxo

## Funcionalidades Ja Endurecidas na Fase Atual

- CLI suficiente para operar o fluxo principal
- historico operacional separado de `notes`
- classificacao clara de casos `similar jobs` e `perguntas adicionais`
- fluxo LinkedIn modularizado em componentes menores
- notifier com menos regra de negocio embutida no transporte
- consultas operacionais de repositorio orientadas a uso real

## O Que Ainda E Backlog, Nao Funcionalidade Fechada

Ainda estao em analise ou backlog:

- melhoria do Telegram para operar o fluxo completo com mais seguranca
- mais testes operacionais de regressao
- health checks antes de operacoes criticas
- priorizacao mais refinada da fila
- configuracao mais rica de perfil e busca
- possivel operacao externa via OpenClaw
- separacao futura de modelos LLM por responsabilidade

## Documentos Relacionados

- `docs/ARQUITETURA_DO_PROJETO.md`
- `docs/plans/POS_MVP_ESTRUTURA_E_REFATORACAO_CHECKLIST.md`
- `AGENTS.md`
