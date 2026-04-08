from __future__ import annotations

from dataclasses import dataclass

from job_hunter_agent.core.domain import JobPosting


@dataclass(frozen=True)
class PortalCapabilities:
    portal_name: str
    collect_supported: bool
    preflight_supported: bool
    submit_supported: bool
    requires_login: bool
    supports_easy_apply: bool
    supports_failure_artifacts: bool


def get_portal_capabilities(job: JobPosting) -> PortalCapabilities:
    normalized_url = job.url.lower()
    normalized_site = job.source_site.lower()

    if "linkedin.com/jobs/" in normalized_url or normalized_site == "linkedin":
        return PortalCapabilities(
            portal_name="LinkedIn",
            collect_supported=True,
            preflight_supported=True,
            submit_supported=True,
            requires_login=True,
            supports_easy_apply=True,
            supports_failure_artifacts=True,
        )

    portal_name = job.source_site or "Portal"
    return PortalCapabilities(
        portal_name=portal_name,
        collect_supported=True,
        preflight_supported=False,
        submit_supported=False,
        requires_login=False,
        supports_easy_apply=False,
        supports_failure_artifacts=False,
    )
