from __future__ import annotations

import contextlib
import logging
import time
from dataclasses import dataclass, field
from typing import Iterator

try:
    import structlog  # type: ignore
    HAS_STRUCTLOG = True
except Exception:  # pragma: no cover
    HAS_STRUCTLOG = False


def configure_logging(level: str = "INFO") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    if HAS_STRUCTLOG:
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            cache_logger_on_first_use=True,
        )


logger = logging.getLogger("athena")


@dataclass
class Span:
    name: str
    start: float = field(default_factory=time.perf_counter)
    attributes: dict[str, object] = field(default_factory=dict)

    def end(self) -> float:
        return time.perf_counter() - self.start


@contextlib.contextmanager
def trace(name: str, **attrs: object) -> Iterator[Span]:
    span = Span(name=name, attributes=attrs)
    logger.info("span.start %s %s", name, attrs)
    try:
        yield span
    except Exception:
        logger.exception("span.error %s", name)
        raise
    finally:
        logger.info("span.end %s duration=%.3fs", name, span.end())
