"""Compatibility alias for LinkedIn application automation."""

import sys

from job_hunter_agent.collectors import linkedin_application as _impl

sys.modules[__name__] = _impl
