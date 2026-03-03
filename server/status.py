"""
Thread-local status callback for search progress reporting.

Processors call set_status() during slow operations (e.g., loading a 3B model).
The search endpoint sets a callback via set_callback() before invoking the
text encoder, then clears it after. The callback streams SSE events to the
frontend so users see "Loading GVE model..." instead of a blank spinner.

No circular imports — this module depends on nothing in the project.
"""

import threading

_status_local = threading.local()


def set_callback(cb):
    """
    Register a status callback for the current thread.
    cb(msg: str) will be called by processors during slow operations.
    Pass None to clear.

    Pure side effect (sets thread-local state).
    """
    _status_local.callback = cb


def set_status(msg):
    """
    Report a status message from the current thread.
    No-op if no callback is registered (e.g., during batch processing).

    >>> set_status("test")  # no callback set, no-op
    """
    cb = getattr(_status_local, 'callback', None)
    if cb is not None:
        cb(msg)
