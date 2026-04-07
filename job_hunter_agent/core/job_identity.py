from __future__ import annotations

import re
from typing import Protocol


class JobIdentityStrategy(Protocol):
    def url_lookup_patterns(self, url: str) -> list[str]:
        raise NotImplementedError


class PortalAwareJobIdentityStrategy:
    @staticmethod
    def _extract_linkedin_job_id(url: str) -> str:
        match = re.search(r"linkedin\.com/jobs/view/(\d+)", url, flags=re.IGNORECASE)
        return match.group(1) if match else ""

    def url_lookup_patterns(self, url: str) -> list[str]:
        patterns = [url]
        linkedin_job_id = self._extract_linkedin_job_id(url)
        if linkedin_job_id:
            patterns.append(f"%/jobs/view/{linkedin_job_id}%")
        return patterns
