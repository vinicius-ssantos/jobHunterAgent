from __future__ import annotations

from job_hunter_agent.application.application_preflight import (
    ApplicationPreflightResult,
    ApplicationPreflightService,
)
from job_hunter_agent.application.application_ports import (
    InspectionPort,
    PreparationPort,
    SubmitPort,
    normalize_application_flow_inspection,
    normalize_application_submission_result,
)
from job_hunter_agent.application.application_preparation import ApplicationPreparationService
from job_hunter_agent.application.application_submission import (
    ApplicationSubmitResult,
    ApplicationSubmissionService,
)
from job_hunter_agent.application.application_support import (
    ApplicationSupportAssessment,
    ApplicationSupportAssessor,
    OllamaApplicationSupportAssessor,
    classify_job_application_support,
    parse_application_support_response,
)

ApplicationFlowInspector = InspectionPort
ApplicationPreparation = PreparationPort
JobApplicant = SubmitPort
