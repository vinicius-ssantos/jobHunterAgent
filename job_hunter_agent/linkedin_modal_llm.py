"""Compatibility alias for LinkedIn modal LLM helpers."""

import sys

from job_hunter_agent.collectors import linkedin_modal_llm as _impl

sys.modules[__name__] = _impl
