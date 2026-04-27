"""Infrastructure adapters such as persistence and transport."""

from job_hunter_agent.infrastructure.repository_schema_bootstrap import install_schema_migration_bootstrap

install_schema_migration_bootstrap()
