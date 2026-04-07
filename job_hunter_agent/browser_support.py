"""Compatibility alias for browser support helpers."""

import sys

from job_hunter_agent.core import browser_support as _impl

sys.modules[__name__] = _impl
