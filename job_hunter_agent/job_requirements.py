"""Compatibility alias for job requirements helpers."""

import sys

from job_hunter_agent.llm import job_requirements as _impl

sys.modules[__name__] = _impl
