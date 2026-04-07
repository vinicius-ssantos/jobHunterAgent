"""Compatibility alias for the application priority module."""

import sys

from job_hunter_agent.llm import application_priority as _impl

sys.modules[__name__] = _impl
