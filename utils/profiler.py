"""
utils/profiler.py — Lightweight timing decorator and structured logger.
Measures cost of each pipeline stage and logs to console + file.
"""
import time
import logging
import functools
from contextlib import contextmanager

log = logging.getLogger("assistant.profiler")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)

# ── Simple file handler for timeline log ──────────────────────
_timeline_handler = logging.FileHandler("pipeline_timing.log")
_timeline_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
log.addHandler(_timeline_handler)


def timed(stage_name: str):
    """
    Decorator — logs wall-clock time for a function call.

    Usage:
        @timed("gmail_fetch")
        def fetch_new_emails(...):
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed = (time.perf_counter() - t0) * 1000
                log.info(f"⏱  [{stage_name}] {elapsed:.1f}ms  OK")
                return result
            except Exception as e:
                elapsed = (time.perf_counter() - t0) * 1000
                log.error(f"⏱  [{stage_name}] {elapsed:.1f}ms  ERROR: {e}")
                raise
        return wrapper
    return decorator


@contextmanager
def timer(stage_name: str):
    """
    Context manager for ad-hoc timing.

    Usage:
        with timer("chroma_query"):
            results = vs.query(...)
    """
    t0 = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - t0) * 1000
        log.info(f"⏱  [{stage_name}] {elapsed:.1f}ms")


class PipelineTrace:
    """
    Accumulates timing for a multi-stage pipeline and prints summary.

    Usage:
        trace = PipelineTrace("email_processing")
        with trace.stage("classify"):
            ...
        with trace.stage("retrieve"):
            ...
        trace.report()
    """
    def __init__(self, pipeline_name: str):
        self.name = pipeline_name
        self.stages: list[tuple[str, float]] = []

    @contextmanager
    def stage(self, name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            ms = (time.perf_counter() - t0) * 1000
            self.stages.append((name, ms))

    def report(self) -> dict:
        total = sum(ms for _, ms in self.stages)
        lines = [f"\n📊 Pipeline [{self.name}] — Total: {total:.0f}ms"]
        for stage, ms in self.stages:
            pct = (ms / total * 100) if total else 0
            bar = "█" * int(pct / 5)
            lines.append(f"   {stage:<25} {ms:>7.1f}ms  {bar} {pct:.0f}%")
        report_str = "\n".join(lines)
        log.info(report_str)
        return {s: ms for s, ms in self.stages}
