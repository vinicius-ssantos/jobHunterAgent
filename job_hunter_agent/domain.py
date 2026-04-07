"""Compatibility alias for domain models."""

import sys

from job_hunter_agent.core import domain as _impl

sys.modules[__name__] = _impl
