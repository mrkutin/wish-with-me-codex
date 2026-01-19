from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from .middleware import get_request_id


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = get_request_id()
        if request_id:
            log_entry["trace_id"] = request_id

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def configure_logging() -> None:
    log_format = (os.environ.get("LOG_FORMAT") or "json").strip().lower()
    level_str = (os.environ.get("LOG_LEVEL") or "INFO").strip().upper()
    level = getattr(logging, level_str, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )

    root.addHandler(handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
