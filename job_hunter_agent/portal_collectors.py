"""Compatibility alias for portal collector adapters."""

import sys

from job_hunter_agent.collectors import portal_collectors as _impl

sys.modules[__name__] = _impl
