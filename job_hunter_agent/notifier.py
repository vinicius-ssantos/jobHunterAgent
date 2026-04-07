"""Compatibility alias for notifier transport."""

import sys

from job_hunter_agent.infrastructure import notifier as _impl

sys.modules[__name__] = _impl
