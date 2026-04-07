"""Compatibility alias for notifier rendering."""

import sys

from job_hunter_agent.infrastructure import notifier_rendering as _impl

sys.modules[__name__] = _impl
