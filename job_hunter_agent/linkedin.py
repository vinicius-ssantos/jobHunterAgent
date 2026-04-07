"""Compatibility alias for LinkedIn collection helpers."""

import sys

from job_hunter_agent.collectors import linkedin as _impl

sys.modules[__name__] = _impl
