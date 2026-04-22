# Externalizar Politica Operacional Minima

## Objetivo

Externalizar apenas os hardcodes operacionais de ordenacao e sumarizacao de fila, sem alterar estado de dominio nem gates de seguranca.

## Checklist

- [x] Mapear hardcodes de ordenacao e sumarizacao operacional
- [x] Criar arquivo versionado de politica operacional
- [x] Adicionar loader/validacao de politica operacional no runtime
- [x] Aplicar politica na ordenacao da fila do notifier
- [x] Aplicar politica na ordenacao do resumo operacional da CLI
- [x] Expor caminho da politica em `Settings`, `.env.example` e `README`
- [x] Validar testes relevantes e suite completa
