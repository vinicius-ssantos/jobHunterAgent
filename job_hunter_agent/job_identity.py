"""Compatibility alias for job identity helpers."""

import sys

from job_hunter_agent.core import job_identity as _impl

sys.modules[__name__] = _impl
