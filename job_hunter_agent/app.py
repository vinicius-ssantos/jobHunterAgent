"""Compatibility alias for the application entrypoint module."""

import sys

from job_hunter_agent.application import app as _impl

sys.modules[__name__] = _impl
