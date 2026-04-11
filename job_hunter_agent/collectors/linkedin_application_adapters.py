from __future__ import annotations


class LinkedInPreflightInspectorAdapter:
    def __init__(self, inspector) -> None:
        self._inspector = inspector

    def inspect(self, job):
        return self._inspector.inspect(job)


class LinkedInSubmissionApplicantAdapter:
    def __init__(self, inspector) -> None:
        self._inspector = inspector

    def submit(self, application, job):
        return self._inspector.submit(application, job)
