"""
Stash entrypoint.

Boot sequence:
  1. Load config.toml
  2. Setup logging
  3. Connect SQLite, run migrations
  4. Load TinyDB rules
  5. Health check → ping Ollama
       - No model configured  → TUI model picker → save to config.toml
       - Model gone           → TUI model picker → save to config.toml
       - Ollama not running   → hard exit with clear message
  6. Register APScheduler jobs from enabled rules
  7. Launch Textual TUI
"""

import logging
import tomllib
from pathlib import Path

from stash.log import setup_logging

log = logging.getLogger(__name__)


def load_config(path: Path = Path("config.toml")) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def main() -> None:
    config = load_config()
    log_path = Path(config["data"]["dir"]).expanduser() / "stash.log"
    setup_logging(log_path)
    log.info("stash starting", extra={"config": config})
    raise NotImplementedError


if __name__ == "__main__":
    main()
