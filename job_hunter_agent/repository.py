"""Compatibility alias for repository interfaces and implementations."""

import sys

from job_hunter_agent.infrastructure import repository as _impl

sys.modules[__name__] = _impl
