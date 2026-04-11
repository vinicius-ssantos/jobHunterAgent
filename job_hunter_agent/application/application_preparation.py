from __future__ import annotations

from job_hunter_agent.application.application_notes import append_note
from job_hunter_agent.application.application_support import (
    ApplicationSupportAssessment,
    ApplicationSupportAssessor,
    classify_job_application_support,
)
from job_hunter_agent.core.domain import JobApplication, JobPosting
from job_hunter_agent.infrastructure.repository import JobRepository
from job_hunter_agent.llm.application_priority import (
    ApplicationPriorityAssessor,
    DeterministicApplicationPriorityAssessor,
    format_application_priority_note,
)
from job_hunter_agent.llm.job_requirements import (
    DeterministicJobRequirementsExtractor,
    JobRequirementSignals,
    JobRequirementsExtractor,
    format_job_requirement_signals,
)


class ApplicationPreparationService:
    def __init__(
        self,
        repository: JobRepository,
        support_assessor: ApplicationSupportAssessor | None = None,
        requirements_extractor: JobRequirementsExtractor | None = None,
        priority_assessor: ApplicationPriorityAssessor | None = None,
    ) -> None:
        self.repository = repository
        self.support_assessor = support_assessor
        self.requirements_extractor = requirements_extractor
        self.priority_assessor = priority_assessor

    def create_drafts_for_approved_jobs(self, job_ids: list[int], notes: str = "") -> list[JobApplication]:
        drafts: list[JobApplication] = []
        for job_id in job_ids:
            job = self.repository.get_job(job_id)
            if not job or job.status != "approved":
                continue
            assessment = self._assess_support(job)
            note_bundle = self._build_requirement_notes(job)
            priority_note = self._build_priority_note(job)
            draft_notes = notes
            if note_bundle:
                draft_notes = append_note(draft_notes, note_bundle)
            if priority_note:
                draft_notes = append_note(draft_notes, priority_note)
            drafts.append(
                self.repository.create_application_draft(
                    job_id,
                    notes=draft_notes,
                    support_level=assessment.support_level,
                    support_rationale=assessment.rationale,
                )
            )
        return drafts

    def _assess_support(self, job: JobPosting) -> ApplicationSupportAssessment:
        fallback = classify_job_application_support(job)
        if self.support_assessor is None:
            return fallback
        try:
            assessed = self.support_assessor.assess(job)
        except Exception:
            return fallback
        if assessed.support_level not in {"auto_supported", "manual_review", "unsupported"}:
            return fallback
        rationale = assessed.rationale.strip()
        if not rationale:
            return fallback
        return ApplicationSupportAssessment(
            support_level=assessed.support_level,
            rationale=rationale,
        )

    def _build_requirement_notes(self, job: JobPosting) -> str:
        fallback = DeterministicJobRequirementsExtractor().extract(job)
        if self.requirements_extractor is None:
            return format_job_requirement_signals(fallback)
        try:
            extracted = self.requirements_extractor.extract(job)
        except Exception:
            extracted = fallback
        return format_job_requirement_signals(self._merge_requirement_signals(fallback, extracted))

    @staticmethod
    def _merge_requirement_signals(
        fallback: JobRequirementSignals,
        extracted: JobRequirementSignals,
    ) -> JobRequirementSignals:
        return JobRequirementSignals(
            seniority=extracted.seniority if extracted.seniority != "nao_informada" else fallback.seniority,
            primary_stack=extracted.primary_stack or fallback.primary_stack,
            secondary_stack=extracted.secondary_stack or fallback.secondary_stack,
            english_level=(
                extracted.english_level
                if extracted.english_level != "nao_informado"
                else fallback.english_level
            ),
            leadership_signals=extracted.leadership_signals or fallback.leadership_signals,
            rationale=extracted.rationale or fallback.rationale,
        )

    def _build_priority_note(self, job: JobPosting) -> str:
        fallback = DeterministicApplicationPriorityAssessor().assess(job)
        if self.priority_assessor is None:
            return format_application_priority_note(fallback)
        try:
            assessed = self.priority_assessor.assess(job)
        except Exception:
            assessed = fallback
        if assessed.level not in {"alta", "media", "baixa"}:
            assessed = fallback
        if not assessed.rationale.strip():
            assessed = fallback
        return format_application_priority_note(assessed)
