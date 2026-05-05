# Safety Gates Matrix

## Objetivo

Esta matriz define quais ações externas o Job Hunter Agent pode executar automaticamente, quais exigem aprovação humana explícita e quais são bloqueadas por design.

Ela é a referência obrigatória para novas features, integrações, workers e comandos que possam tocar portais externos, dados pessoais, credenciais, mensagens ou envio real de candidaturas.

## Categorias

| Categoria | Significado |
|---|---|
| `permitida` | Pode executar automaticamente sem aprovação humana adicional, desde que respeite configuração, limites e observabilidade existentes. |
| `exige_aprovacao` | Deve permanecer bloqueada até um gate humano explícito, audível e intencional. |
| `bloqueada` | Fora do escopo do produto; não deve ser implementada nem executada. |

## Matriz de ações

| Ação | Categoria | Gate correspondente | Observações |
|---|---|---|---|
| Coleta de vagas por fonte pública ou scraping read-only | `permitida` | Configuração da fonte, limites operacionais e catálogo de fontes | Permitida somente para leitura de vagas. Deve respeitar prioridade, método e risco definidos em `source_catalog.json`. |
| Escrita em banco local | `permitida` | Repositório local / SQLite | Permitida para persistir vagas, candidaturas, eventos, diagnósticos e estado operacional local. Não envia dados para terceiros. |
| Leitura de configurações locais | `permitida` | Configuração carregada pelo runtime | Permitida para inicializar runtime, comandos e políticas locais. |
| Leitura de segredos locais | `permitida` | Ambiente local controlado pelo operador | Permitida apenas para uso local necessário ao runtime, como Telegram, banco, browser e modelos. Nunca deve ser impressa em logs ou relatórios. |
| Execução de dry-run | `permitida` | `--dry-run` | Permitida e recomendada para validar ações sem tocar o portal externo de forma irreversível. |
| Notificação via Telegram | `permitida` | Configuração de Telegram e callbacks humanos | Permitida para pedir revisão humana, reportar status e receber decisões. Não deve substituir gates de autorização para submit. |
| Login / autenticação em portal | `exige_aprovacao` | Bootstrap/intervenção humana explícita | Login é ação sensível. Deve ocorrer com supervisão humana e sem automação de credenciais além do uso local de sessão previamente autorizada. |
| Abertura de fluxo de candidatura / preflight | `exige_aprovacao` | Candidatura em estado revisado/confirmado e comando explícito | Deve começar por dry-run quando houver risco alto ou portal instável. Não equivale a submit. |
| Preenchimento de campos de candidatura | `exige_aprovacao` | Revisão humana da candidatura e fluxo assistido | Pode preparar dados ou preencher campos somente depois de intenção humana clara. Deve preservar possibilidade de revisão antes de envio. |
| Envio de CV anexado | `exige_aprovacao` | Revisão humana + autorização de fluxo de candidatura | CV contém dados pessoais. Anexar ou preparar anexo exige intenção humana e deve permanecer auditável. |
| Submit real de candidatura | `exige_aprovacao` | `authorized_submit` | Nunca deve ocorrer apenas por matching, coleta, score ou estado intermediário. Exige autorização explícita após revisão/preflight. |
| Ações externas em fonte com risco `high` | `exige_aprovacao` | Dry-run obrigatório + gate humano aplicável | Qualquer ação em fonte high-risk deve passar por dry-run antes de execução real, e a decisão humana deve ser registrada. |
| Envio de mensagens via LinkedIn / InMail | `bloqueada` | Nenhum | Fora do escopo atual. Não implementar envio automático de mensagens, convites ou InMail. |
| Scraping de dados pessoais de terceiros | `bloqueada` | Nenhum | Fora do escopo. O sistema deve focar vagas e candidaturas do operador, não coleta de perfis ou dados pessoais de terceiros. |
| Bypass de captcha, rate limit ou bloqueio do portal | `bloqueada` | Nenhum | Nunca contornar mecanismos de proteção. Em caso de bloqueio, parar, registrar diagnóstico e exigir intervenção humana. |
| Submit real sem autorização humana | `bloqueada` | Nenhum | Mesmo com feature flag ativa, submissão real sem `authorized_submit` é proibida. |

## Regras obrigatórias para novas ações externas

1. Toda nova ação externa deve ser adicionada nesta matriz antes da implementação.
2. Se a ação tocar portal externo, candidatura, CV, mensagem, autenticação ou dados pessoais, ela começa como `exige_aprovacao` até revisão explícita.
3. Ações com risco `high` exigem dry-run obrigatório antes de qualquer execução real.
4. A ação deve ter observabilidade suficiente para diagnóstico posterior: logs, estado local, evento ou artefato operacional.
5. Nenhuma feature flag pode transformar ação `bloqueada` em ação executável.

## Relação com outros documentos

- `source_catalog.json` classifica fontes por método, risco e prioridade.
- `docs/APPLICATION_OPERATIONS.md` descreve o runbook operacional para candidaturas.
- `docs/TELEGRAM_HUMAN_REVIEW_GATES.md` descreve os gates humanos via Telegram.
- `docs/POST_MVP_SAFETY_BOUNDARIES.md` documenta limites de segurança pós-MVP.

## Checklist de revisão

Antes de aprovar PRs que adicionem ou alterem ação externa, confirme:

- [ ] A ação existe nesta matriz.
- [ ] A categoria está correta.
- [ ] O gate correspondente está documentado.
- [ ] Ação `high` tem dry-run obrigatório.
- [ ] Não há bypass de autorização humana para submit real.
- [ ] Logs, eventos ou artefatos permitem auditoria suficiente.
