from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Protocol


_TRACKING_QUERY_PREFIXES = ("utm_",)
_TRACKING_QUERY_PARAMS = {
    "currentJobId",
    "eBP",
    "keywords",
    "origin",
    "position",
    "refId",
    "refresh",
    "start",
    "trackingId",
    "trk",
}
_TRACKING_QUERY_PARAMS_LOWER = {param.lower() for param in _TRACKING_QUERY_PARAMS}


class JobIdentityStrategy(Protocol):
    def url_lookup_patterns(self, url: str) -> list[str]:
        raise NotImplementedError


def normalize_job_url(url: str) -> str:
    """Return a stable URL for identity lookups without volatile tracking params."""
    stripped_url = url.strip()
    if not stripped_url:
        return ""

    parsed = urlsplit(stripped_url)
    if not parsed.scheme or not parsed.netloc:
        return stripped_url

    hostname = parsed.netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    path = re.sub(r"/+", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")

    stable_params = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower.startswith(_TRACKING_QUERY_PREFIXES):
            continue
        if key in _TRACKING_QUERY_PARAMS or key_lower in _TRACKING_QUERY_PARAMS_LOWER:
            continue
        stable_params.append((key, value))

    stable_query = urlencode(stable_params, doseq=True)
    return urlunsplit((parsed.scheme.lower(), hostname, path, stable_query, ""))


def normalize_identity_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_value.casefold()).strip()


@dataclass(frozen=True)
class JobTextIdentity:
    company: str
    title: str
    location: str

    @property
    def lookup_key(self) -> str:
        return "|".join(
            (
                normalize_identity_text(self.company),
                normalize_identity_text(self.title),
                normalize_identity_text(self.location),
            )
        )

    @property
    def complete(self) -> bool:
        return all(part for part in self.lookup_key.split("|"))


class PortalAwareJobIdentityStrategy:
    @staticmethod
    def _extract_linkedin_job_id(url: str) -> str:
        match = re.search(r"linkedin\.com/jobs/view/(\d+)", url, flags=re.IGNORECASE)
        if match:
            return match.group(1)

        parsed = urlsplit(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        current_job_id = query.get("currentJobId") or query.get("currentjobid")
        return current_job_id if current_job_id and current_job_id.isdigit() else ""

    def url_lookup_patterns(self, url: str) -> list[str]:
        normalized_url = normalize_job_url(url)
        linkedin_job_id = self._extract_linkedin_job_id(url) or self._extract_linkedin_job_id(normalized_url)

        patterns = []
        for pattern in (
            url,
            f"%/jobs/view/{linkedin_job_id}%" if linkedin_job_id else "",
            normalized_url,
        ):
            if pattern and pattern not in patterns:
                patterns.append(pattern)
        return patterns
