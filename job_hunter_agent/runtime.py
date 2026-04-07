"""Compatibility alias for runtime helpers."""

import sys

from job_hunter_agent.core import runtime as _impl

sys.modules[__name__] = _impl
