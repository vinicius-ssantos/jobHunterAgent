"""Compatibility alias for review rationale formatting."""

import sys

from job_hunter_agent.llm import review_rationale as _impl

sys.modules[__name__] = _impl
