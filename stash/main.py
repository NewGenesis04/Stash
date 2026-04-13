"""
Stash entrypoint — composition root.

Boot sequence:
  1. Load config.toml  (generate default on first run)
  2. Setup logging
  3. Ensure data directory exists
  4. Connect SQLite, run migrations
  5. Open TinyDB rules store
  6. Health check — ping Ollama
       OllamaUnavailableError → hard exit with clear message
       NO_MODEL_SELECTED / MODEL_MISSING → proceed, model picker shown in TUI
  7. Build object graph (ToolRegistry, AgentFactory, StashScheduler)
  8. Build StashApp
  9. Wire circular dep: scheduler.set_app(app)
 10. Launch Textual TUI
"""

import asyncio
import logging
import sys
import tomllib
import tomli_w
from pathlib import Path

from stash.log import setup_logging

log = logging.getLogger(__name__)

_DEFAULT_CONFIG = {
    "data": {"dir": "~/.stash"},
    "ollama": {"host": "http://localhost:11434", "max_steps": 20},
}

_DEFAULT_CONFIG_TOML = """\
[data]
dir = "~/.stash"

[ollama]
host = "http://localhost:11434"
max_steps = 20

# model is set via the model picker on first run
# model = "gemma4:4b"
"""


def load_config(path: Path) -> dict:
    if not path.exists():
        path.write_text(_DEFAULT_CONFIG_TOML, encoding="utf-8")
        return dict(_DEFAULT_CONFIG)
    with path.open("rb") as f:
        return tomllib.load(f)


def _hard_exit(message: str) -> None:
    print(f"\n  ✗ {message}\n", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    config_path = Path("config.toml")
    config = load_config(config_path)

    data_dir = Path(config["data"]["dir"]).expanduser()
    log_path = data_dir / "stash.log"
    setup_logging(log_path)
    log.info("stash.starting", extra={"config_path": str(config_path), "data_dir": str(data_dir)})

    data_dir.mkdir(parents=True, exist_ok=True)

    # --- persistence ---
    import stash.persistence.sqlite as db
    from stash.persistence.tinydb import RulesDB

    sqlite_conn = db.connect(data_dir / "stash.db")
    rules_db = RulesDB(data_dir / "rules.json")
    log.info("stash.persistence_ready")

    # --- health check ---
    from stash.health.ollama import check, OllamaUnavailableError

    endpoint = config.get("ollama", {}).get("host", "http://localhost:11434")

    # On first run config.toml has no model key — selected_model is None.
    # check() returns NO_MODEL_SELECTED, which causes LoadingScreen to push
    # ModelPickerScreen after the splash. Once the user picks a model it is
    # written to config["ollama"]["model"] and saved back to config.toml.
    # On subsequent runs the key is present and the picker is not shown.
    # The picker is also accessible at any time via ctrl+o (action_change_model).
    selected_model = config.get("ollama", {}).get("model")

    try:
        health_result = asyncio.run(check(endpoint, selected_model))
        log.info("stash.health_ok", extra={"status": health_result.status.value, "model": selected_model})
    except OllamaUnavailableError:
        _hard_exit(
            "Ollama is not running.\n\n"
            "  Start it with: ollama serve\n"
            "  Then relaunch stash."
        )
    except Exception as e:
        # Unexpected error during health check — proceed without result
        health_result = None
        log.warning("stash.health_error", extra={"error": str(e)})

    # --- object graph ---
    from stash.core.agent import AgentFactory
    from stash.core.registry import ToolRegistry
    from stash.scheduler.runner import StashScheduler
    from stash.tui.app import StashApp
    from stash.tools import ALL_TOOLS, ALL_SCHEMAS

    tool_registry = ToolRegistry(ALL_TOOLS)
    agent_factory = AgentFactory(config, tool_registry, ALL_SCHEMAS)
    scheduler = StashScheduler(rules_db, tool_registry, ALL_SCHEMAS)

    app = StashApp(
        config=config,
        config_path=config_path,
        scheduler=scheduler,
        rules_db=rules_db,
        sqlite_conn=sqlite_conn,
        agent_factory=agent_factory,
        health_result=health_result,
    )
    scheduler.set_app(app)

    log.info("stash.launching")
    app.run()
    log.info("stash.exited")


if __name__ == "__main__":
    main()
