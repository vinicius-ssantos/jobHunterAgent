"""Compatibility alias for review workflow rules."""

import sys

from job_hunter_agent.application import review_workflow as _impl

sys.modules[__name__] = _impl
