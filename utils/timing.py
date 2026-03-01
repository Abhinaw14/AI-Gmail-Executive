"""
utils/timing.py — Simple timing instrumentation for pipeline stages.
"""
import time
import logging

log = logging.getLogger("timing")


class Timer:
    """Context manager for timing pipeline stages.

    Usage:
        with Timer("gmail_metadata_fetch"):
            emails = fetch_metadata_only()
    """
    def __init__(self, name: str):
        self.name = name
        self.elapsed_ms = 0

    def __enter__(self):
        self.t0 = time.time()
        return self

    def __exit__(self, *_):
        self.elapsed_ms = (time.time() - self.t0) * 1000
        log.info(f"[TIMING] {self.name}: {self.elapsed_ms:.0f}ms")
        print(f"[TIMING] {self.name}: {self.elapsed_ms:.0f}ms")


def timed(name: str):
    """Decorator for timing functions.

    Usage:
        @timed("classify_email")
        def classify_email(...): ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with Timer(name):
                return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator
