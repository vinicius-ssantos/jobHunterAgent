"""Compatibility alias for LinkedIn authentication helpers."""

import sys

from job_hunter_agent.collectors import linkedin_auth as _impl

sys.modules[__name__] = _impl
