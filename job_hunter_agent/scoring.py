"""Compatibility alias for scoring helpers."""

import sys

from job_hunter_agent.llm import scoring as _impl

sys.modules[__name__] = _impl
