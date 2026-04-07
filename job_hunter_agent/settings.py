"""Compatibility alias for validated settings."""

import sys

from job_hunter_agent.core import settings as _impl

sys.modules[__name__] = _impl
