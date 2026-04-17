# Structured Matching Fallback Exit Criteria

## Objetivo

Definir quando o fallback legado de matching pode ser desligado com segurança.

## Estado Atual

Hoje o runtime principal:

- prefere `JOB_HUNTER_STRUCTURED_MATCHING_CONFIG_PATH`
- cai no legado apenas quando o arquivo estruturado nao existir e o fallback estiver habilitado

## Critérios Para Desligar O Fallback

O fallback legado só deve ser desligado por padrão quando todos os pontos abaixo forem verdadeiros:

- existe formato estruturado estável e versionado
- `.env.example` e `README.md` já tratam a fonte estruturada como padrão oficial
- o runtime principal usa a fonte estruturada como caminho dominante
- prefiltro e scorer respeitam a mesma policy no caminho estruturado
- a política de senioridade desconhecida está modelada no caminho novo
- existe cobertura de testes do loader estruturado, fallback e fail-fast
- existe cobertura do fluxo principal preferindo a fonte estruturada
- o uso residual de `JOB_HUNTER_PROFILE_TEXT` está restrito a compatibilidade explícita

## Sinais De Que Ainda Não É Hora

Não desligar o fallback por padrão se ainda houver qualquer um destes sinais:

- documentação ainda descreve o legado como caminho principal
- módulos centrais ainda dependem do shape legado como contrato dominante
- faltam testes de regressão do caminho principal novo
- mudanças de scoring/prefiltro ainda exigem tocar prioritariamente no contrato legado

## Passo Recomendado De Transição

1. manter `JOB_HUNTER_STRUCTURED_MATCHING_FALLBACK_ENABLED=true` por compatibilidade
2. concluir a migração do centro de gravidade do runtime
3. medir se ainda existem ambientes sem `job_target.json`
4. inverter o padrão para `false`
5. só depois planejar remoção mais agressiva do legado
