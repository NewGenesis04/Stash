"""
Logging setup — JSON to file, configured once at startup.

Usage:
    from stash.log import setup_logging
    setup_logging(log_path)

Then anywhere in the codebase:
    import logging
    log = logging.getLogger(__name__)
    log.info("something happened", extra={"rule_id": "rule_001"})
"""

import json
import logging
import traceback
from datetime import datetime, UTC
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "file": record.filename,
            "line": record.lineno,
            "func": record.funcName,
            "msg": record.getMessage(),
        }

        if record.exc_info:
            entry["exc"] = traceback.format_exception(*record.exc_info)

        # Merge any extra fields passed via extra={}
        skip = logging.LogRecord.__dict__.keys() | {
            "message", "asctime", "args", "msg",
            "exc_info", "exc_text", "stack_info",
        }
        for k, v in record.__dict__.items():
            if k not in skip and not k.startswith("_"):
                entry[k] = v

        return json.dumps(entry)


def setup_logging(log_path: Path, level: int = logging.DEBUG) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
