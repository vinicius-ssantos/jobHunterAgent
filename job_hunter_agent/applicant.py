"""Compatibility alias for the application services module."""

import sys

from job_hunter_agent.application import applicant as _impl

sys.modules[__name__] = _impl
