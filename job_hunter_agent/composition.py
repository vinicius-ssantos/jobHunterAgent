"""Compatibility alias for composition helpers."""

import sys

from job_hunter_agent.application import composition as _impl

sys.modules[__name__] = _impl
