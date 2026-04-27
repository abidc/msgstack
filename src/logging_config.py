"""Configure structured logging for MsgStack."""

import logging
import sys
from src.config import settings


class _JSONFormatter(logging.Formatter):
    """Minimal JSON log formatter — no extra deps required."""

    def format(self, record: logging.LogRecord) -> str:
        import json, traceback
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = traceback.format_exception(*record.exc_info)
        # Extra fields injected via logger.info("...", extra={...})
        for key in ("request_id", "workspace_id", "endpoint", "latency_ms", "status"):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        return json.dumps(payload)


def configure_logging() -> None:
    level = getattr(logging, settings.log_level, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
        handler.setFormatter(_JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s — %(message)s"
        ))

    root.handlers.clear()
    root.addHandler(handler)
