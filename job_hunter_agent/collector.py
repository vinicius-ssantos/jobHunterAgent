"""Compatibility alias for collection services."""

import sys

from job_hunter_agent.collectors import collector as _impl

sys.modules[__name__] = _impl
