# AGENTS.md

## Objective

This repository implements a local-first assistant for job discovery and triage.

The active product scope is:

- collect job postings from configured sources
- normalize and score them against a local professional profile
- persist relevant postings locally
- send postings to Telegram for human review
- record approval or rejection decisions

Out of scope by default:

- autonomous job application
- multi-user support
- SaaS concerns
- cloud persistence
- generic agent platform features

## Product Constraints

- This is a personal-use system.
- Human approval is mandatory before any high-impact action.
- Candidate data stays local by default.
- Reliability is more important than breadth.
- A narrow, stable flow is preferable to broad unstable automation.

## Source of Truth

- The active application lives under `job_hunter_agent/`.
- `main.py` is a thin entrypoint only.
- Legacy prototypes must not be used as runtime dependencies.
- Do not recreate `files/` or any equivalent shadow architecture.

## Architectural Boundaries

Keep responsibilities separated and directional:

- `job_hunter_agent/domain.py`
  Domain entities, immutable models, shared vocabulary, status values.
- `job_hunter_agent/settings.py`
  Application settings and startup validation.
- `job_hunter_agent/repository.py`
  Persistence contracts and SQLite implementation.
- `job_hunter_agent/collector.py`
  Source collection, normalization, scoring orchestration.
- `job_hunter_agent/notifier.py`
  Review transport and Telegram-specific interaction handling.
- `job_hunter_agent/app.py`
  Process composition, lifecycle, scheduling, top-level orchestration.

Dependency rule:

- outer layers may depend on inner layers
- domain must not depend on infrastructure
- repository, notifier, and external collectors are infrastructure
- application wiring happens in `app.py`, not spread across modules

## SOLID Rules

### Single Responsibility Principle

- Each module must have one reason to change.
- Do not mix domain logic, persistence, transport, and process wiring in the same class.
- If a class is doing parsing, scoring, storage, and messaging, it is too large.

### Open/Closed Principle

- Extend behavior through interfaces and new implementations, not by adding branching everywhere.
- New job portals must be added behind collector abstractions.
- New notifiers must be additive, not require rewriting the collection flow.

### Liskov Substitution Principle

- Implementations of repository, scorer, collector, and notifier contracts must preserve expected behavior.
- Test doubles must behave like production contracts, not rely on hidden shortcuts.

### Interface Segregation Principle

- Keep interfaces small and task-oriented.
- Do not force implementations to depend on methods they do not use.
- Prefer focused protocols over large multi-purpose base classes.

### Dependency Inversion Principle

- High-level business flow must depend on abstractions, not concrete infrastructure details.
- Application services should receive repositories, collectors, scorers, and notifiers through constructor injection.
- Avoid constructing infrastructure deep inside business logic unless composition requires it at the edge.

## Domain and State Rules

Jobs must use explicit, stable states only.

Current valid statuses:

- `collected`
- `approved`
- `rejected`
- `error_collect`

Rules:

- status names must stay semantically narrow
- do not overload one status with multiple meanings
- do not add transient or UI-only statuses without clear operational value
- every state transition must be explicit and traceable

## Collection and Scoring Rules

- Treat external portals as unstable systems.
- Collectors are I/O adapters and should fail independently by source.
- A single source failure must not abort the whole cycle.
- Normalize raw source data before persistence.
- Deduplication must happen before saving or dispatching notifications.
- Prefer a two-step strategy:
  - source extraction
  - relevance scoring
- Use rule-based rejection first when exclusion criteria are obvious.
- Use the LLM as an assistive scorer, not as an unquestioned authority.
- Positive scoring must produce a concise rationale.
- Never allow the model to invent candidate data absent from settings.

## Telegram and Review Rules

- Telegram is the human review interface.
- Notifications must be short, structured, and action-oriented.
- A job card should include:
  - title
  - company
  - location
  - work mode
  - salary text when available
  - relevance score
  - rationale
  - source link
- Callback handlers must map to a single state transition.
- Handlers should be idempotent where practical.
- Review actions must not trigger unrelated side effects.

## Configuration Rules

- Configuration must fail fast when invalid.
- Placeholder secrets must never be accepted silently.
- Required settings must be validated at startup.
- Default values should be safe for development and obviously invalid for real secrets.
- Do not spread configuration lookups across the codebase.
- Access settings through a validated settings object.

## Persistence Rules

- Repository code owns SQL and schema details.
- Domain objects must not contain SQLite-specific concerns.
- Keep schema simple until the product proves a stronger need.
- Persist enough metadata to debug operational failures.
- Avoid leaking database row shapes into higher layers.

## Error Handling and Observability

- Failures must be visible, not swallowed.
- Log at source boundaries with enough context to debug later.
- Prefer controlled degradation over full failure.
- User-facing messages should be concise.
- Internal logs should preserve source, action, and failure reason.

## Testing Standards

Every non-trivial change should preserve or improve verification.

Minimum expectations:

- repository tests for persistence, deduplication, and state summaries
- collector tests for normalization, filtering, and scoring decisions
- settings validation tests when configuration rules change
- notifier tests when callback or review behavior changes

Testing guidelines:

- prefer unit tests for business rules
- add integration tests only around critical seams
- test behavior, not implementation details
- use local temporary paths inside the workspace for sandbox-safe tests

## Code Quality Rules

- Use Python 3.11+ compatible code.
- Prefer explicit names over short clever names.
- Keep functions and classes small.
- Prefer immutable dataclasses for domain models.
- Avoid hidden shared state.
- Avoid premature abstraction, but refactor once duplication becomes structural.
- Use ASCII unless the file already justifies otherwise.
- Comments should explain intent or a non-obvious tradeoff, not restate code.

## Change Control

Before changing code, verify:

- does this improve the core loop
- does this preserve architectural boundaries
- does this reduce or increase coupling
- does this introduce hidden runtime behavior
- does this require README or AGENTS updates

Do not add features just because they are technically possible.

## Branching Policy

Use feature branches when the change is substantial enough to put the stable MVP loop at risk.

Typical cases where a branch is recommended:

- new product capabilities outside the current validated loop
- architectural refactors spanning multiple modules
- new automation flows with external side effects
- changes that introduce new states, persistence rules, or review flows
- portal-specific application flows

Typical cases where a branch is usually not necessary:

- small fixes
- localized parser cleanup
- test-only changes
- documentation-only updates
- checklist alignment without runtime impact

Recommended branch naming:

- `feature/<tema-curto>`
- `fix/<tema-curto>`
- `refactor/<tema-curto>`
- `docs/<tema-curto>`

Examples:

- `feature/candidatura-assistida-arquitetura`
- `fix/linkedin-parser-residual`
- `refactor/separa-modulo-applicant`
- `docs/fluxo-candidatura-v1`

Rule of thumb:

- if the work can destabilize `coletar -> normalizar -> ranquear -> persistir -> notificar -> revisar`, prefer a branch
- if the work is narrow and easily reversible, committing directly on the current branch is acceptable

- Sempre que houver modificacoes significativas ainda nao commitadas, preparar e criar commits no padrao adotado no repositorio.
- As mensagens de commit devem ser escritas em portugues.

## Anti-Patterns

- giant prompts that browse, reason, score, and act all at once
- business rules embedded in Telegram handlers
- infrastructure instantiated across random modules
- direct SQL outside the repository layer
- domain models aware of transport or storage details
- reintroducing autonomous application into the main loop without explicit product approval
- using the repo as a playground for generic agent experiments unrelated to the product

## Definition of Done

A change is complete only when:

- the collect -> score -> persist -> notify -> review loop still works
- responsibilities remain correctly separated
- state transitions remain valid
- failure behavior is explicit
- tests cover changed behavior or a concrete gap is documented
- documentation is updated when runtime or setup changes
