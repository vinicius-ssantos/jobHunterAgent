from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from job_hunter_agent.collectors.linkedin_application_state import (
    LinkedInApplicationPageState,
    LinkedInJobPageReadiness,
)


def extract_linkedin_job_id(url: str) -> str:
    match = re.search(r"/jobs/view/(\d+)", url, re.IGNORECASE)
    if match:
        return match.group(1)
    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
    except Exception:
        return ""
    current_job_id = query.get("currentJobId", [""])
    if current_job_id and current_job_id[0].isdigit():
        return current_job_id[0]
    reference_job_id = query.get("referenceJobId", [""])
    if reference_job_id and reference_job_id[0].isdigit():
        return reference_job_id[0]
    return ""


def canonical_linkedin_job_url(url: str) -> str:
    job_id = extract_linkedin_job_id(url)
    if not job_id:
        return ""
    return f"https://www.linkedin.com/jobs/view/{job_id}/"


def build_linkedin_direct_apply_url(url: str) -> str:
    job_id = extract_linkedin_job_id(url)
    if not job_id:
        return ""
    return f"https://www.linkedin.com/jobs/view/{job_id}/apply/?openSDUIApplyFlow=true"


def needs_canonical_job_navigation(current_url: str, target_url: str) -> bool:
    target_job_id = extract_linkedin_job_id(target_url)
    if not target_job_id:
        return False
    normalized_current_url = current_url.lower()
    if "/jobs/collections/" in normalized_current_url:
        return True
    if "/apply/" in normalized_current_url:
        return False
    current_job_id = extract_linkedin_job_id(current_url)
    if current_job_id and current_job_id != target_job_id:
        return True
    return False


def classify_linkedin_job_page_readiness(
    *,
    job_url: str,
    state: LinkedInApplicationPageState,
) -> LinkedInJobPageReadiness:
    current_url = state.current_url or ""
    current_job_id = extract_linkedin_job_id(current_url)
    target_job_id = extract_linkedin_job_id(job_url)
    normalized_url = current_url.lower()
    normalized_sample = state.sample.lower()

    expired_patterns = (
        r"job (is )?no longer available",
        r"job.*no longer open",
        r"this job has expired",
        r"job posting has expired",
        r"this (position|role|job) (is )?no longer",
        r"this job (listing )?is closed",
        r"job (listing )?not found",
        r"pagina que voce esta procurando nao existe",
        r"vaga (nao|nÃ£o) esta mais disponivel",
        r"vaga encerrada",
        r"n(a|Ã£|ÃƒÂ£)o aceita mais candidaturas",
        r"nÃ£o aceita mais candidaturas",
        r"no longer accepting applications",
    )

    if "/jobs/collections/" in normalized_url or "/jobs/search/" in normalized_url:
        return LinkedInJobPageReadiness(
            result="listing_redirect",
            reason="a navegacao caiu em listagem ou colecao do LinkedIn",
            sample=state.sample,
        )
    if current_job_id and target_job_id and current_job_id != target_job_id:
        return LinkedInJobPageReadiness(
            result="wrong_page",
            reason="a pagina aberta nao corresponde a vaga autorizada",
            sample=state.sample,
        )
    if any(re.search(pattern, normalized_sample, re.IGNORECASE) for pattern in expired_patterns):
        return LinkedInJobPageReadiness(
            result="expired",
            reason="a vaga parece encerrada ou indisponivel",
            sample=state.sample,
        )
    if state.easy_apply or state.submit_visible:
        return LinkedInJobPageReadiness(
            result="ready",
            reason="cta de candidatura detectado na pagina alvo",
            sample=state.sample,
        )
    if state.external_apply:
        return LinkedInJobPageReadiness(
            result="no_apply_cta",
            reason="a vaga so oferece candidatura externa no site da empresa",
            sample=state.sample,
        )
    if "/apply/" in normalized_url:
        return LinkedInJobPageReadiness(
            result="ready",
            reason="fluxo de candidatura do LinkedIn ja esta aberto na vaga alvo",
            sample=state.sample,
        )
    return LinkedInJobPageReadiness(
        result="no_apply_cta",
        reason="nenhum cta de candidatura foi encontrado na pagina alvo",
        sample=state.sample,
    )


def recover_linkedin_direct_apply_url_from_html(content: str, job_url: str) -> str:
    if not content:
        return ""
    lowered = content.lower()
    target_job_id = extract_linkedin_job_id(job_url)
    if not target_job_id:
        return ""
    has_internal_apply = (
        f"https://www.linkedin.com/job-apply/{target_job_id}".lower() in lowered
        or f"/jobs/view/{target_job_id}/apply/".lower() in lowered
        or (
            "applyctatext" in lowered
            and ("candidatura simplificada" in lowered or "easy apply" in lowered)
        )
    )
    if not has_internal_apply:
        return ""
    return build_linkedin_direct_apply_url(job_url)
