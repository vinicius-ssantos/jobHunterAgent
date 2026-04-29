# Post-MVP Safety Boundaries

## Objetivo

Documentar explicitamente o que fica fora do MVP local atual para evitar expansao de escopo insegura.

Este documento complementa `docs/V1_HARDENING_CHECKLIST.md` e registra itens estacionados para fases posteriores.

## Principio Geral

A v1 deve permanecer local-first, auditavel e centrada em revisao humana.

Qualquer funcionalidade que aumente autonomia operacional, reduza rastreabilidade ou execute acoes externas de alto impacto deve ficar fora do caminho critico ate existir contrato, teste, observabilidade e gate humano suficientes.

## Itens Estacionados Fora Da V1

### Broker Externo

Status: estacionado para pos-MVP.

Riscos:

- aumenta complexidade operacional;
- cria novos modos de falha e retry;
- exige DLQ, idempotencia e observabilidade mais fortes;
- pode mascarar a ordem real de decisoes humanas.

Motivo da decisao:

- SQLite e execucao local ainda sao suficientes para a v1;
- a prioridade atual e consolidar fluxo local reproduzivel;
- workers externos so devem entrar depois de testes e contratos de eventos mais maduros.

Condicao minima para reavaliar:

- contratos de eventos estaveis;
- DLQ documentada;
- idempotencia por comando/evento;
- runbook de recuperacao;
- testes de retry e falha parcial.

### Submit Automatico Sem Revisao/Autorizacao Humana

Status: fora do caminho critico.

Riscos:

- envio incorreto de candidatura;
- exposicao indevida de dados pessoais;
- acao irreversivel em portal externo;
- dano reputacional para o candidato;
- violacao de expectativa do usuario.

Motivo da decisao:

- candidatura real e acao de alto impacto;
- a v1 exige revisao humana, preflight e autorizacao explicita;
- `authorized_submit` deve continuar sendo gate obrigatorio para submit real.

Condicao minima para reavaliar:

- politicas operacionais mais completas;
- logs/auditoria de decisao humana;
- limites por portal;
- circuit breakers;
- confirmacao humana em etapa final;
- testes de regressao para estados `confirmed` vs `authorized_submit`.

### Automacao Agressiva Em Plataformas De Vagas

Status: estacionado para pos-MVP.

Exemplos:

- navegacao massiva sem limites;
- cliques automatizados em alta escala;
- contorno de telas incertas;
- preenchimento automatico sem revisao;
- retries agressivos em portais instaveis.

Riscos:

- bloqueio de conta;
- comportamento incompatível com termos ou expectativas do portal;
- falso positivo em submit;
- degradacao de confiabilidade;
- dificuldade de diagnostico.

Motivo da decisao:

- o MVP deve priorizar coleta, revisao, diagnostico e submit controlado;
- qualquer automacao de portal precisa ser conservadora e observavel.

Condicao minima para reavaliar:

- limites por portal;
- `--dry-run` confiavel;
- screenshots/artifacts de diagnostico;
- circuit breaker por falha repetida;
- fallback manual claro.

### Fluxos Sem Rastreabilidade De Decisao

Status: bloqueado por principio.

Riscos:

- impossibilidade de explicar por que uma candidatura avancou;
- dificuldade de auditar erro operacional;
- perda de confianca no sistema;
- regressao silenciosa em gates humanos.

Motivo da decisao:

- a v1 depende de revisao humana e estados persistidos;
- acoes relevantes devem deixar trilha em SQLite, logs e, quando habilitado, domain-events.

Condicao minima para reavaliar:

- evento ou registro persistido para decisao critica;
- correlation id por candidatura quando aplicavel;
- diagnostico CLI capaz de explicar estado atual;
- testes cobrindo transicoes criticas.

### Batch De Submit Real

Status: fora do caminho critico.

Riscos:

- multiplica impacto de um erro de classificacao;
- reduz oportunidade de revisao humana por candidatura;
- aumenta chance de envio com artefatos errados;
- dificulta rollback.

Motivo da decisao:

- batch pode ser util para extracao, scoring e relatorios;
- submit real deve continuar unitario, revisado e explicitamente autorizado.

Condicao minima para reavaliar:

- aprovacao humana por item;
- limites muito conservadores;
- logs e artifacts por candidatura;
- dry-run obrigatorio antes de qualquer envio real.

### CV/PDF, Cover Letter Ou Respostas Enviados Automaticamente

Status: fora do caminho critico.

Riscos:

- envio de conteudo impreciso;
- alucinacao de experiencia, senioridade ou metricas;
- uso de dados pessoais sem revisao;
- associacao de documento errado a vaga errada.

Motivo da decisao:

- artefatos gerados devem ser revisaveis;
- `docs/DATA_CONTRACT.md` define que dados do usuario nao devem ser sobrescritos sem confirmacao;
- outputs de LLM sao sugestoes, nao fonte de verdade final.

Condicao minima para reavaliar:

- artefatos versionados por candidatura;
- revisao humana obrigatoria;
- marcacao de incertezas;
- testes para nao sobrescrever curriculo original;
- associacao clara entre artefato e candidatura.

## Relacao Com A V1

A v1 continua permitindo:

- coleta local;
- ranking/matching;
- revisao humana;
- persistencia SQLite;
- Telegram/CLI como interfaces;
- preflight;
- diagnostico operacional;
- submit controlado apos autorizacao explicita.

A v1 nao deve depender de:

- broker externo;
- Postgres;
- dashboard/TUI;
- batch de submit;
- automacao sem revisao;
- envio automatico de documentos gerados.

## Checklist De Revisao Para Novas Propostas

Antes de promover uma feature pos-MVP para implementacao, responda:

- a feature executa acao externa de alto impacto?
- existe gate humano explicito?
- existe `--dry-run` quando aplicavel?
- o estado fica persistido em SQLite?
- existe trilha de auditoria ou domain-event?
- existe diagnostico CLI para explicar falhas?
- existe fallback manual?
- a feature pode sobrescrever dados do usuario?
- existe teste de regressao para o gate principal?

Se qualquer resposta critica for negativa, a feature deve permanecer estacionada.

## Criterio De Saida Do Estacionamento

Um item estacionado so deve voltar ao roadmap ativo quando houver:

- especificacao documentada;
- contrato de dados ou eventos;
- estrategia de teste;
- plano de rollback ou fallback;
- owner claro;
- criterio de aceite que preserve revisao humana e rastreabilidade.
