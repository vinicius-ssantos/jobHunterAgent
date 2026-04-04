from __future__ import annotations

import logging
import re
from pathlib import Path

from job_hunter_agent.browser_support import extract_json_object, load_playwright_storage_state, resolve_local_chromium
from job_hunter_agent.domain import RawJob, SiteConfig


logger = logging.getLogger(__name__)


def normalize_linkedin_card(card: dict[str, str]) -> dict[str, str]:
    title = clean_linkedin_title(card.get("title", ""))
    raw_company = str(card.get("company", ""))
    raw_location = str(card.get("location", ""))
    raw_summary = str(card.get("summary", ""))
    company = clean_linkedin_company(raw_company)
    location = preserve_explicit_linkedin_location(raw_location) or clean_linkedin_location(raw_location)
    company = strip_title_suffix_from_company(company, title)
    location = strip_linkedin_location_noise(location, title, company)
    if not company:
        location_as_company = clean_linkedin_company(raw_location)
        if location_as_company and not looks_like_linkedin_location(location_as_company):
            company = location_as_company
    if not location:
        location = clean_linkedin_location(raw_summary)
    location = strip_linkedin_location_noise(location, title, company)
    inferred_company = infer_linkedin_company_from_summary(raw_summary, title, location)
    if inferred_company and is_suspicious_linkedin_company(company, location, title):
        company = inferred_company
    elif not company:
        company = inferred_company
    company = strip_title_suffix_from_company(company, title)
    location = strip_linkedin_location_noise(location, title, company)
    work_mode = normalize_linkedin_work_mode(card.get("work_mode", ""), location)
    salary_text = clean_linkedin_salary(card.get("salary_text", ""))
    summary = clean_linkedin_summary(card.get("summary", ""))
    description = clean_linkedin_description(card.get("description", ""))
    return {
        "title": title,
        "company": company,
        "location": location,
        "work_mode": work_mode,
        "salary_text": salary_text,
        "url": str(card.get("url", "")).strip(),
        "summary": summary,
        "description": description,
    }


def should_repair_linkedin_fields(card: dict[str, str]) -> bool:
    return is_suspicious_linkedin_company(
        card.get("company", ""), card.get("location", ""), card.get("title", "")
    ) or is_suspicious_linkedin_location(
        card.get("location", ""), card.get("title", ""), card.get("company", "")
    )


def apply_linkedin_field_repair(card: dict[str, str], repaired_fields: dict[str, str]) -> dict[str, str]:
    merged = dict(card)
    repaired_company = strip_title_suffix_from_company(
        clean_linkedin_company(repaired_fields.get("company", "")),
        card.get("title", ""),
    )
    repaired_location = strip_linkedin_location_noise(
        clean_linkedin_location(repaired_fields.get("location", "")) or repaired_fields.get("location", ""),
        card.get("title", ""),
        repaired_company or merged.get("company", ""),
    )
    if repaired_company and is_suspicious_linkedin_company(
        merged.get("company", ""), merged.get("location", ""), merged.get("title", "")
    ):
        merged["company"] = repaired_company
    if repaired_location and is_suspicious_linkedin_location(
        merged.get("location", ""), merged.get("title", ""), merged.get("company", "")
    ):
        merged["location"] = repaired_location
    return merged


def should_enrich_linkedin_card(card: dict[str, str]) -> bool:
    return not card.get("company", "").strip() or not card.get("location", "").strip()


def merge_linkedin_card_with_detail(card: dict[str, str], detail: dict[str, str]) -> dict[str, str]:
    merged = dict(card)
    title = detail.get("title", "").strip()
    company = detail.get("company", "").strip()
    location = detail.get("location", "").strip()
    summary = detail.get("summary", "").strip()
    if title and len(title) > len(str(merged.get("title", "")).strip()):
        merged["title"] = title
    if company:
        merged["company"] = company
    if location:
        merged["location"] = location
    existing_summary = str(merged.get("summary", "")).strip()
    if summary and len(summary) > len(existing_summary):
        merged["summary"] = summary
    if detail.get("raw_company_candidates"):
        merged["detail_company_candidates"] = detail["raw_company_candidates"]
    if detail.get("raw_metadata_candidates"):
        merged["detail_metadata_candidates"] = detail["raw_metadata_candidates"]
    if summary:
        merged["detail_summary"] = summary
    return merged


def strip_title_prefix_from_location(location: str, title: str) -> str:
    normalized_location = _normalize_whitespace(location)
    normalized_title = _normalize_whitespace(title)
    if not normalized_location or not normalized_title:
        return normalized_location
    lowered_location = normalized_location.lower()
    lowered_title = normalized_title.lower()
    if lowered_location.startswith(lowered_title + " "):
        normalized_location = _normalize_whitespace(normalized_location[len(normalized_title) :])
        return clean_linkedin_location(normalized_location) or normalized_location
    return normalized_location


def strip_title_suffix_from_company(company: str, title: str) -> str:
    normalized_company = _normalize_whitespace(company)
    normalized_title = _normalize_whitespace(title)
    if not normalized_company or not normalized_title:
        return normalized_company
    lowered_company = normalized_company.lower()
    lowered_title = normalized_title.lower()
    if lowered_company.endswith(" " + lowered_title):
        normalized_company = _normalize_whitespace(normalized_company[: -len(normalized_title)])
    return clean_linkedin_company(normalized_company)


def strip_linkedin_location_noise(location: str, title: str, company: str) -> str:
    normalized_location = strip_linkedin_chrome_prefix(_normalize_whitespace(location))
    normalized_title = _normalize_whitespace(title)
    normalized_company = _normalize_whitespace(company)
    if not normalized_location:
        return normalized_location
    normalized_location = re.sub(r"^\d+%\s+de\s+desconto\s+", "", normalized_location, flags=re.IGNORECASE)
    normalized_location = re.sub(r"^de\s+desconto\s+", "", normalized_location, flags=re.IGNORECASE)
    normalized_location = strip_title_prefix_from_location(normalized_location, normalized_title)
    if normalized_company:
        normalized_location = re.sub(
            rf"^{re.escape(normalized_company)}\s+",
            "",
            normalized_location,
            flags=re.IGNORECASE,
        )
    if normalized_title:
        normalized_location = re.sub(
            rf"^{re.escape(normalized_title)}\s+",
            "",
            normalized_location,
            flags=re.IGNORECASE,
        )
    if re.match(
        r"^[^,()|]{1,60},\s*[^,()|]{1,60},\s*Brasil(?:\s+\((?:Híbrido|Hibrido|Remoto|Presencial)\))?$",
        normalized_location,
        flags=re.IGNORECASE,
    ):
        return normalized_location
    return clean_linkedin_location(normalized_location) or normalized_location


def infer_linkedin_company_from_summary(summary: str, title: str, location: str) -> str:
    normalized_summary = strip_linkedin_chrome_prefix(_normalize_whitespace(summary))
    normalized_title = _normalize_whitespace(title)
    normalized_location = _normalize_whitespace(location)
    if not normalized_summary:
        return ""
    candidate = normalized_summary
    if normalized_title:
        candidate = re.sub(rf"^{re.escape(normalized_title)}\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(rf"\s*{re.escape(normalized_title)}$", "", candidate, flags=re.IGNORECASE)
    if normalized_location:
        candidate = re.sub(rf"\s*{re.escape(normalized_location)}.*$", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(
        r"\s+[^,()|]{1,60},\s*[^,()|]{1,60},\s*Brasil(?:\s+\((?:Híbrido|Hibrido|Remoto|Presencial)\))?.*$",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    if normalized_title:
        candidate = re.sub(rf"\s*{re.escape(normalized_title)}$", "", candidate, flags=re.IGNORECASE)
    return clean_linkedin_company(candidate)


def is_suspicious_linkedin_company(company: str, location: str, title: str = "") -> bool:
    normalized_company = _normalize_whitespace(company)
    normalized_title = _normalize_whitespace(title)
    if not normalized_company:
        return True
    lower_company = normalized_company.lower()
    if normalized_company.endswith(",") and len(normalized_company.split()) <= 2:
        return True
    if lower_company in {
        "empresa nao informada",
        "local nao informado",
        "osasco",
        "osasco,",
        "sÃƒÂ£o paulo",
        "sao paulo",
        "brasil",
    }:
        return True
    normalized_location = _normalize_whitespace(location)
    if normalized_location:
        first_segment = normalized_location.split(",", maxsplit=1)[0].strip().lower()
        if first_segment and lower_company == first_segment:
            return True
        if first_segment and lower_company == f"{first_segment},":
            return True
    if normalized_title:
        lower_title = normalized_title.lower()
        if lower_company == lower_title:
            return True
        if lower_company.endswith(" " + lower_title) or lower_company.startswith(lower_title + " "):
            return True
    return False


def is_suspicious_linkedin_location(location: str, title: str, company: str = "") -> bool:
    normalized_location = _normalize_whitespace(location)
    normalized_title = _normalize_whitespace(title)
    normalized_company = _normalize_whitespace(company)
    if not normalized_location:
        return True
    lower_location = normalized_location.lower()
    if lower_location in {"local nao informado", "não informado", "nao informado"}:
        return True
    if "desconto" in lower_location:
        return True
    if normalized_title and lower_location.startswith(normalized_title.lower() + " "):
        return True
    if normalized_company and lower_location.startswith(normalized_company.lower() + " "):
        return True
    return not looks_like_linkedin_location(normalized_location)


def strip_linkedin_chrome_prefix(value: str) -> str:
    cleaned = _normalize_whitespace(value)
    chrome_markers = (
        "Reative Premium:",
        "Para negócios",
        "Notificações",
        "Mensagens",
        "Minha rede",
        "Pular para conteúdo principal",
    )
    for marker in chrome_markers:
        marker_index = cleaned.lower().rfind(marker.lower())
        if marker_index != -1:
            cleaned = _normalize_whitespace(cleaned[marker_index + len(marker) :])
            break
    cleaned = re.sub(r"^\d+%\s+de\s+desconto\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def clean_linkedin_title(value: str) -> str:
    cleaned = _normalize_whitespace(value)
    repeated_prefix = re.match(r"^(.{5,120}?)\s+\1$", cleaned, flags=re.IGNORECASE)
    if repeated_prefix:
        cleaned = repeated_prefix.group(1).strip()
    else:
        collapsed_repeat = _collapse_repeated_title(cleaned)
        if collapsed_repeat:
            cleaned = collapsed_repeat
    cleaned = re.sub(r"\s+with verification\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bwith verification\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bPromovida\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bCandidatura simplificada\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bAvaliando candidaturas\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bVisualizado\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = _normalize_whitespace(cleaned)
    if "\n" in value:
        first_line = _normalize_whitespace(value.splitlines()[0])
        if first_line:
            return clean_linkedin_title(first_line)
    parts = [part.strip() for part in cleaned.split("  ") if part.strip()]
    if parts:
        return parts[0]
    return cleaned


def clean_linkedin_company(value: str) -> str:
    cleaned = _normalize_whitespace(value)
    repeated_prefix = re.match(r"^(.{10,80}?)\s+\1\s+(.+)$", cleaned, flags=re.IGNORECASE)
    if repeated_prefix:
        cleaned = repeated_prefix.group(2).strip()
    cleaned = re.sub(r"^with verification\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(Desenvolvedor|Engenheiro|Software Engineer|Backend|Fullstack)\b.*?\bwith verification\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+with verification\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(São Paulo|Sao Paulo|Rio de Janeiro).*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = _normalize_whitespace(cleaned)
    noise_phrases = (
        "Promovida",
        "Candidatura simplificada",
        "Avaliando candidaturas",
        "Visualizado",
        "1 conexão trabalha aqui",
        "há ",
    )
    segments = _split_linkedin_segments(cleaned)
    kept: list[str] = []
    for segment in segments:
        normalized_segment = _normalize_whitespace(segment)
        lower_segment = normalized_segment.lower()
        if any(phrase.lower() in segment.lower() for phrase in noise_phrases):
            continue
        if "brasil (" in lower_segment or "brasil (" in lower_segment.replace("í", "i"):
            continue
        if looks_like_linkedin_location(normalized_segment):
            continue
        if lower_segment in {"hibrido", "híbrido", "remoto", "presencial", "hybrid", "onsite"}:
            continue
        if normalized_segment.endswith(",") and len(normalized_segment.split()) <= 1:
            continue
        if lower_segment in {
            "osasco",
            "são paulo",
            "sao paulo",
            "rio de janeiro",
            "curitiba",
            "campinas",
            "porto alegre",
            "belo horizonte",
            "brasil",
            "brazil",
        }:
            continue
        if len(normalized_segment.split()) <= 1:
            continue
        kept.append(normalized_segment)
        break
    if kept:
        return kept[0]
    if (
        looks_like_linkedin_location(cleaned)
        or (cleaned.endswith(",") and len(cleaned.split()) <= 1)
        or cleaned.lower()
        in {
            "osasco",
            "osasco,",
            "são paulo",
            "sao paulo",
            "rio de janeiro",
            "curitiba",
            "campinas",
            "porto alegre",
            "belo horizonte",
            "brasil",
            "brazil",
        }
    ):
        return ""
    return cleaned


def clean_linkedin_location(value: str) -> str:
    cleaned = _normalize_whitespace(value)
    preserved = preserve_explicit_linkedin_location(cleaned)
    if preserved:
        return preserved
    snippet = _extract_linkedin_location_snippet(cleaned)
    if snippet:
        return snippet
    segments = _split_linkedin_segments(cleaned)
    for segment in segments:
        lower_segment = segment.lower()
        if len(segment) > 80:
            continue
        if any(
            marker in lower_segment
            for marker in (
                "with verification",
                "promovida",
                "candidatura simplificada",
                "avaliando candidaturas",
                "visualizado",
            )
        ):
            continue
        if looks_like_linkedin_location(segment):
            return segment
    return ""


def normalize_linkedin_work_mode(raw_work_mode: str, location: str) -> str:
    combined = f"{raw_work_mode} {location}".lower()
    if "remoto" in combined or "remote" in combined:
        return "remoto"
    if "híbrido" in combined or "hibrido" in combined or "hybrid" in combined:
        return "hibrido"
    if "presencial" in combined or "onsite" in combined:
        return "presencial"
    return _normalize_whitespace(raw_work_mode)


def clean_linkedin_salary(value: str) -> str:
    cleaned = _normalize_whitespace(value)
    return cleaned if cleaned else "Nao informado"


def clean_linkedin_summary(value: str) -> str:
    return _clean_linkedin_text_block(value, limit=240)


def clean_linkedin_description(value: str) -> str:
    return _clean_linkedin_text_block(value, limit=1000)


def _clean_linkedin_text_block(value: str, *, limit: int) -> str:
    cleaned = _normalize_whitespace(value)
    noise_patterns = (
        r"\bPromovida\b",
        r"\bCandidatura simplificada\b",
        r"\bAvaliando candidaturas\b",
        r"\bVisualizado\b",
        r"\bwith verification\b",
        r"\b\d+\s+candidaturas\b",
        r"\bhá\s+\d+\s+\w+\b",
    )
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = _normalize_whitespace(cleaned)
    return cleaned[:limit]


def _split_linkedin_segments(value: str) -> list[str]:
    return [segment.strip() for segment in re.split(r"[·•|]", value) if segment.strip()]


def looks_like_linkedin_location(value: str) -> bool:
    normalized = _normalize_whitespace(value)
    if not normalized:
        return False
    lower = normalized.lower()
    if any(
        marker in lower
        for marker in (
            "(híbrido)",
            "(hibrido)",
            "(remoto)",
            "(presencial)",
            " hybrid",
            " remoto",
            " presencial",
        )
    ):
        return True
    if "," in normalized and "brasil" in lower:
        return True
    return lower in {"brasil", "brazil"}


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def preserve_explicit_linkedin_location(value: str) -> str:
    normalized = _normalize_whitespace(value)
    match = re.search(
        r"([^,()|]{1,60},\s*[^,()|]{1,60},\s*Brasil(?:\s+\((?:Híbrido|Hibrido|Remoto|Presencial)\))?)",
        normalized,
        flags=re.IGNORECASE,
    )
    if match:
        candidate = _normalize_whitespace(match.group(1))
        first_segment = candidate.split(",", maxsplit=1)[0].strip()
        if first_segment and not re.search(
            r"\b(desenvolvedor|engenheiro|software|backend|fullstack|java|kotlin|agent|desconto)\b",
            first_segment,
            flags=re.IGNORECASE,
        ):
            return candidate
    return ""


def _extract_linkedin_location_snippet(value: str) -> str:
    lower_value = value.lower()
    brasil_index = lower_value.rfind("brasil")
    if brasil_index == -1:
        return ""
    window_start = max(0, brasil_index - 80)
    window_end = min(len(value), brasil_index + 40)
    tail = value[window_start:window_end]
    match = re.search(
        r"([^,()|]+(?: [^,()|]+){0,3},\s*"
        r"[^,()|]+(?: [^,()|]+){0,3},\s*"
        r"Brasil(?:\s+\((?:Híbrido|Hibrido|Remoto|Presencial)\))?)",
        tail,
        flags=re.IGNORECASE,
    )
    if match:
        candidate = _normalize_whitespace(match.group(1))
        first_segment = candidate.split(",", maxsplit=1)[0].lower()
        if "brasil" in first_segment or "verification" in first_segment:
            candidate = _normalize_whitespace(
                re.sub(r"^.*?\bbrasil\s+", "", candidate, count=1, flags=re.IGNORECASE)
            )
        return candidate
    return ""


def _collapse_repeated_title(value: str) -> str | None:
    cleaned = _normalize_whitespace(value)
    if not cleaned:
        return None
    length = len(cleaned)
    if length % 2 == 0:
        midpoint = length // 2
        left = cleaned[:midpoint].strip()
        right = cleaned[midpoint:].strip()
        if left and left == right:
            return left
    return None


def summarize_linkedin_raw_card(card: dict[str, str]) -> str:
    debug_fields = (
        "title",
        "company",
        "location",
        "work_mode",
        "raw_company_candidates",
        "raw_metadata_candidates",
        "detail_company_candidates",
        "detail_metadata_candidates",
        "detail_summary",
        "raw_lines",
        "anchor_text",
        "summary",
    )
    parts: list[str] = []
    for field in debug_fields:
        value = _normalize_whitespace(str(card.get(field, "")))
        if value:
            parts.append(f"{field}={value[:160]!r}")
    return " | ".join(parts)


def parse_linkedin_field_repair_response(response_text: str) -> dict[str, str]:
    payload = extract_json_object(response_text)
    if not payload:
        return {}
    company = _normalize_whitespace(str(payload.get("company", "")))
    location = _normalize_whitespace(str(payload.get("location", "")))
    confidence = payload.get("confidence")
    if isinstance(confidence, str) and confidence.isdigit():
        confidence = int(confidence)
    if not isinstance(confidence, int):
        confidence = 0
    if confidence < 7:
        return {}
    return {
        "company": company,
        "location": location,
        "rationale": _normalize_whitespace(str(payload.get("rationale", ""))),
    }


class LinkedInDeterministicCollector:
    def __init__(
        self,
        *,
        storage_state_path: str | Path,
        headless: bool,
        field_repairer: object | None = None,
    ) -> None:
        self.storage_state_path = Path(storage_state_path).resolve()
        self.headless = headless
        self.field_repairer = field_repairer

    async def collect(self, site: SiteConfig, max_jobs: int) -> list[RawJob]:
        if not self.storage_state_path.exists():
            raise RuntimeError(
                "Sessao autenticada do LinkedIn nao encontrada. Rode --bootstrap-linkedin-session."
            )

        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias de coleta nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc

        executable_path = resolve_local_chromium()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                executable_path=str(executable_path),
                headless=self.headless,
                args=["--start-maximized"],
            )
            context = await browser.new_context(storage_state=load_playwright_storage_state(self.storage_state_path))
            page = await context.new_page()
            try:
                await page.goto(site.search_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                await self._dismiss_sign_in_modal(page)
                try:
                    await page.wait_for_selector("a[href*='/jobs/view/']", timeout=10000)
                except PlaywrightTimeoutError as exc:
                    raise RuntimeError(
                        "nenhum card de vaga do LinkedIn ficou visivel apos carregar a busca"
                    ) from exc
                raw_cards = await self._extract_visible_cards(page, max_jobs)
                enriched_cards = await self._enrich_residual_cards(context, raw_cards)
            finally:
                await context.close()
                await browser.close()

        jobs: list[RawJob] = []
        seen_urls: set[str] = set()
        for card in enriched_cards:
            normalized_card = normalize_linkedin_card(card)
            if self.field_repairer and should_repair_linkedin_fields(normalized_card):
                repaired_fields = self.field_repairer.repair(card, normalized_card)
                repaired_card = apply_linkedin_field_repair(normalized_card, repaired_fields)
                if repaired_card != normalized_card:
                    logger.info(
                        "LinkedIn card reparado por LLM local | title=%r company=%r location=%r",
                        repaired_card["title"].strip(),
                        repaired_card["company"].strip() or "Empresa nao informada",
                        repaired_card["location"].strip() or "Local nao informado",
                    )
                normalized_card = repaired_card
            url = normalized_card["url"].strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            company = normalized_card["company"].strip() or "Empresa nao informada"
            location = normalized_card["location"].strip() or "Local nao informado"
            if company == "Empresa nao informada" or location == "Local nao informado":
                logger.warning(
                    "LinkedIn card residual sem company/location | title=%r company=%r location=%r raw=%s",
                    normalized_card["title"].strip(),
                    company,
                    location,
                    summarize_linkedin_raw_card(card),
                )
            jobs.append(
                RawJob(
                    title=normalized_card["title"].strip(),
                    company=company,
                    location=location,
                    work_mode=normalized_card["work_mode"].strip() or "Nao informado",
                    salary_text=normalized_card["salary_text"].strip() or "Nao informado",
                    url=url,
                    source_site=site.name,
                    summary=normalized_card["summary"].strip(),
                    description=normalized_card["description"].strip(),
                )
            )
        return jobs

    async def _enrich_residual_cards(self, context: object, cards: list[dict[str, str]]) -> list[dict[str, str]]:
        enriched_cards: list[dict[str, str]] = []
        for card in cards:
            normalized_card = normalize_linkedin_card(card)
            if not should_enrich_linkedin_card(normalized_card):
                enriched_cards.append(card)
                continue
            detail = await self._extract_job_detail_snapshot(context, normalized_card["url"].strip())
            if not detail:
                enriched_cards.append(card)
                continue
            merged_card = merge_linkedin_card_with_detail(card, detail)
            merged_normalized = normalize_linkedin_card(merged_card)
            logger.info(
                "LinkedIn card enriquecido pelo detalhe | title=%r company=%r location=%r",
                merged_normalized["title"].strip(),
                merged_normalized["company"].strip() or "Empresa nao informada",
                merged_normalized["location"].strip() or "Local nao informado",
            )
            enriched_cards.append(merged_card)
        return enriched_cards

    async def _extract_job_detail_snapshot(self, context: object, url: str) -> dict[str, str]:
        if not url.startswith("https://"):
            return {}
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
            return await page.evaluate(
                """
                () => {
                  const normalizeText = (value) => (value || "").replace(/\\s+/g, " ").trim();
                  const textsForSelectors = (selectors) => {
                    const values = [];
                    for (const selector of selectors) {
                      for (const node of Array.from(document.querySelectorAll(selector))) {
                        const text = normalizeText(node.textContent || "");
                        if (text && !values.includes(text)) {
                          values.push(text);
                        }
                      }
                    }
                    return values;
                  };
                  const companyCandidates = textsForSelectors([
                    ".job-details-jobs-unified-top-card__company-name a",
                    ".job-details-jobs-unified-top-card__company-name",
                    ".jobs-unified-top-card__company-name a",
                    ".jobs-unified-top-card__company-name",
                    ".job-details-jobs-unified-top-card__primary-description a",
                    ".job-details-jobs-unified-top-card__primary-description-container a",
                  ]);
                  const metadataCandidates = textsForSelectors([
                    ".job-details-jobs-unified-top-card__tertiary-description",
                    ".job-details-jobs-unified-top-card__tertiary-description-container",
                    ".job-details-jobs-unified-top-card__primary-description-container",
                    ".jobs-unified-top-card__subtitle-primary-grouping",
                    ".jobs-unified-top-card__bullet",
                  ]);
                  const title = normalizeText(
                    document.querySelector("h1")?.textContent ||
                    document.querySelector(".job-details-jobs-unified-top-card__job-title")?.textContent ||
                    ""
                  );
                  const summary = normalizeText(document.body?.innerText || "").slice(0, 400);
                  return {
                    title,
                    company: companyCandidates.join(" | "),
                    location: metadataCandidates.join(" | "),
                    summary,
                    raw_company_candidates: companyCandidates.join(" | "),
                    raw_metadata_candidates: metadataCandidates.join(" | "),
                  };
                }
                """
            )
        except Exception as exc:
            logger.warning("LinkedIn detail enrichment falhou | url=%r detalhe=%s", url, exc)
            return {}
        finally:
            await page.close()

    async def _dismiss_sign_in_modal(self, page: object) -> None:
        modal_button_selectors = (
            "button[aria-label='Fechar']",
            "button.contextual-sign-in-modal__modal-dismiss",
            "button.modal__dismiss",
        )
        for selector in modal_button_selectors:
            locator = page.locator(selector)
            if await locator.count():
                try:
                    await locator.first.click(timeout=1000)
                    await page.wait_for_timeout(500)
                    return
                except Exception:
                    continue

    async def _extract_visible_cards(self, page: object, max_jobs: int) -> list[dict[str, str]]:
        return await page.evaluate(
            """
            ({ maxJobs }) => {
              const anchors = Array.from(document.querySelectorAll("a[href*='/jobs/view/']"));
              const normalized = [];
              const seen = new Set();
              const normalizeHref = (href) => {
                if (!href) return "";
                try {
                  return new URL(href, window.location.origin).toString();
                } catch {
                  return "";
                }
              };
              for (const anchor of anchors) {
                const href = normalizeHref(anchor.getAttribute("href") || anchor.href || "");
                if (!href || !href.startsWith("https://") || seen.has(href)) {
                  continue;
                }
                const card = anchor.closest("li, .job-card-container, .jobs-search-results__list-item, .job-card-list");
                const rawText = (card?.innerText || anchor.innerText || "").trim();
                const cardText = rawText.replace(/\\s+/g, " ").trim();
                if (!cardText) {
                  continue;
                }
                const normalizeLine = (line) => (line || "").replace(/\\s+/g, " ").trim();
                const noiseMarkers = ["promovida", "candidatura simplificada", "avaliando candidaturas", "visualizado", "with verification"];
                const isNoiseLine = (line) => {
                  const lower = line.toLowerCase();
                  return noiseMarkers.some((marker) => lower.includes(marker)) || /\\b\\d+\\s+candidaturas\\b/i.test(lower);
                };
                const isLocationLine = (line) => {
                  const lower = line.toLowerCase();
                  return (
                    lower.includes("brasil") ||
                    lower.includes("sÃƒÂ£o paulo") ||
                    lower.includes("sao paulo") ||
                    lower.includes("rio de janeiro") ||
                    lower.includes("(hÃƒÂ­brido)") ||
                    lower.includes("(hibrido)") ||
                    lower.includes("(remoto)") ||
                    lower.includes("(presencial)") ||
                    lower.includes(" hybrid") ||
                    lower.includes(" remoto") ||
                    lower.includes(" presencial")
                  );
                };
                const lines = rawText.split(/\\n+/).map((line) => normalizeLine(line)).filter(Boolean);
                const selectorTexts = (selectors) => {
                  const values = [];
                  for (const selector of selectors) {
                    for (const node of Array.from(card?.querySelectorAll(selector) || [])) {
                      const text = normalizeLine(node.textContent || "");
                      if (text && !values.includes(text)) {
                        values.push(text);
                      }
                    }
                  }
                  return values;
                };
                const companyCandidates = selectorTexts([
                  ".job-card-container__primary-description",
                  ".artdeco-entity-lockup__subtitle",
                  ".artdeco-entity-lockup__subtitle span",
                ]);
                const metadataCandidates = selectorTexts([
                  ".job-card-container__metadata-item",
                  ".artdeco-entity-lockup__caption",
                  ".artdeco-entity-lockup__metadata",
                ]);
                const title = normalizeLine(lines[0] || anchor.textContent || "");
                if (!title) {
                  continue;
                }
                const filteredLines = lines.filter((line) => line !== title && !isNoiseLine(line));
                const company = (
                  companyCandidates.find((line) => line !== title && !isNoiseLine(line) && !isLocationLine(line)) ||
                  filteredLines.find((line) => line !== title && !isLocationLine(line)) ||
                  ""
                );
                const location = (
                  metadataCandidates.find((line) => isLocationLine(line)) ||
                  filteredLines.find((line) => isLocationLine(line)) ||
                  ""
                );
                const lowerText = cardText.toLowerCase();
                let workMode = "";
                if (lowerText.includes("remoto")) workMode = "remoto";
                else if (lowerText.includes("hÃƒÂ­brido") || lowerText.includes("hibrido") || lowerText.includes("hybrid")) workMode = "hibrido";
                else if (lowerText.includes("presencial") || lowerText.includes("onsite")) workMode = "presencial";
                const salaryMatch = cardText.match(/R\\$\\s?[\\d\\.]+(?:\\s*[-a]\\s*R\\$?\\s?[\\d\\.]+)?/i);
                seen.add(href);
                normalized.push({
                  title,
                  company,
                  location,
                  work_mode: workMode,
                  salary_text: salaryMatch ? salaryMatch[0] : "",
                  url: href,
                  summary: cardText.slice(0, 240),
                  description: cardText.slice(0, 1000),
                  raw_lines: lines.join(" | "),
                  raw_company_candidates: companyCandidates.join(" | "),
                  raw_metadata_candidates: metadataCandidates.join(" | "),
                  anchor_text: normalizeLine(anchor.textContent || ""),
                });
                if (normalized.length >= maxJobs) {
                  break;
                }
              }
              return normalized;
            }
            """,
            {"maxJobs": max_jobs},
        )


class OllamaLinkedInFieldRepairer:
    def __init__(self, model_name: str, base_url: str) -> None:
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise RuntimeError(
                "Dependencias de repair do LinkedIn nao estao instaladas. Rode pip install -r requirements.txt."
            ) from exc
        self._llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.0)

    def repair(self, card: dict[str, str], normalized_card: dict[str, str]) -> dict[str, str]:
        prompt = f"""
        Corrija apenas campos de uma vaga do LinkedIn que parecem ausentes ou suspeitos.

        Regras:
        - Nunca invente dados que nao estejam no texto.
        - Se nao tiver confianca, retorne string vazia no campo.
        - Empresa deve ser o nome da empresa, nao cidade, nao texto de navegacao, nao titulo da vaga.
        - Local deve ser somente a localizacao da vaga.
        - Retorne apenas JSON.

        Campos atuais:
        title: {normalized_card.get("title", "")}
        company: {normalized_card.get("company", "")}
        location: {normalized_card.get("location", "")}
        work_mode: {normalized_card.get("work_mode", "")}
        summary: {normalized_card.get("summary", "")}

        Evidencias brutas:
        raw_company_candidates: {card.get("raw_company_candidates", "")}
        raw_metadata_candidates: {card.get("raw_metadata_candidates", "")}
        detail_company_candidates: {card.get("detail_company_candidates", "")}
        detail_metadata_candidates: {card.get("detail_metadata_candidates", "")}
        detail_summary: {card.get("detail_summary", "")}
        raw_lines: {card.get("raw_lines", "")}

        Retorne:
        {{
          "company": "nome ou vazio",
          "location": "local ou vazio",
          "confidence": 8,
          "rationale": "motivo curto"
        }}
        """
        response = self._llm.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)
        return parse_linkedin_field_repair_response(response_text)
