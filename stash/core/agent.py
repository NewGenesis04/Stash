"""
Agent core — pure, stateless ReAct loop.

Each run is independent: takes a task + session registry + callbacks,
runs tool calls until the model responds without calling a tool,
and returns the full step log.
"""

import logging
import sqlite3
import uuid
from datetime import datetime, UTC
from typing import Literal

import ollama
from pydantic import BaseModel, Field

from stash.core.registry import SessionRegistry, ToolRegistry, UnauthorisedToolError
from stash.core.callbacks import Callback
from stash.prompts.prompt import build_system_prompt

log = logging.getLogger(__name__)


def _ollama_tools(schemas: list[dict], available: list[str]) -> list[dict]:
    """Return Ollama-compatible tool schemas, filtered to the approved tool list."""
    return [
        {"type": t["type"], "function": t["function"]}
        for t in schemas
        if t.get("function", {}).get("name") in available
    ]


class ReActStep(BaseModel):
    type: Literal["thought", "action", "observation", "response", "error"]
    content: str
    tool: str | None = None
    args: dict | None = None
    result: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class Agent:
    """Runs a single ReAct loop for a given task."""

    def __init__(self, config: dict, callbacks: list[Callback], tools: list[dict]) -> None:
        self.config = config
        self.callbacks = callbacks
        self.tools = tools  # list of SCHEMA dicts from each tool module
        ollama_config = config.get("ollama", {})
        self._client = ollama.Client(host=ollama_config.get("host", "http://localhost:11434"))
        self._model = ollama_config.get("model")
        if not self._model:
            raise ValueError("No model selected. Launch the app and pick a model first.")
        self._max_steps = ollama_config.get("max_steps", 20)

    def plan(self, task: str, registry: SessionRegistry, run_id: str | None = None) -> tuple[list[ReActStep], list[dict]]:
        """Dry-run the ReAct loop — tools are not executed. Used for HITL approval."""
        return self._loop(task, registry, dry_run=True, run_id=run_id)

    def run(self, task: str, registry: SessionRegistry, run_id: str | None = None, initial_messages: list[dict] | None = None) -> list[ReActStep]:
        """Execute the ReAct loop against an approved session registry."""
        steps, _ = self._loop(task, registry, dry_run=False, run_id=run_id, initial_messages=initial_messages)
        return steps

    # ------------------------------------------------------------------

    def _loop(self, task: str, registry: SessionRegistry, dry_run: bool, run_id: str | None = None, initial_messages: list[dict] | None = None) -> tuple[list[ReActStep], list[dict]]:
        run_id = run_id or str(uuid.uuid4())
        ctx = {"run_id": run_id, "model": self._model, "dry_run": dry_run}

        log.info("agent.run_start", extra={**ctx, "task": task, "tools": registry.available})

        tools = _ollama_tools(self.tools, registry.available)

        if initial_messages:
            messages = list(initial_messages)
            log.debug("agent.resuming_from_cache", extra={**ctx, "message_count": len(messages)})
        else:
            preferences = self._load_preferences()
            messages = [{"role": "system", "content": build_system_prompt(preferences)}]
            messages.extend(self._load_session_history())
            messages.append({"role": "user", "content": task})

        steps: list[ReActStep] = []

        for step_num in range(self._max_steps):
            # Phase 2: Token-count estimation
            # Heuristic: char count / 4
            total_chars = sum(len(str(m.get("content", ""))) for m in messages)
            # Add estimated chars for tool definitions too
            total_chars += len(str(tools))
            estimated_tokens = total_chars // 4
            
            context_window = self.config.get("ollama", {}).get("context_window", 32768)
            if estimated_tokens > context_window * 0.8:
                log.warning("agent.context_pressure", extra={**ctx, "estimated_tokens": estimated_tokens, "window": context_window})

            response = self._client.chat(model=self._model, messages=messages, tools=tools)
            message = response["message"]
            content = (message.get("content") or "").strip()
            tool_calls = message.get("tool_calls") or []

            if content and tool_calls:
                log.info("agent.thought", extra={**ctx, "step": step_num, "thought": content})
                steps.append(ReActStep(type="thought", content=content))

            if not tool_calls:
                log.info("agent.response", extra={**ctx, "step": step_num, "content": content})
                steps.append(ReActStep(type="response", content=content))
                break

            messages.append(message)

            for tool_call in tool_calls:
                fn_name = tool_call["function"]["name"]
                fn_args = tool_call["function"]["arguments"]

                log.info("agent.action", extra={**ctx, "step": step_num, "tool": fn_name, "args": fn_args})
                steps.append(ReActStep(type="action", content=fn_name, tool=fn_name, args=fn_args))

                tool_schema = next((t for t in self.tools if t.get("function", {}).get("name") == fn_name), None)
                is_readonly = tool_schema.get("readonly", False) if tool_schema else False

                if dry_run and not is_readonly:
                    observation = "[plan mode — not executed]"
                    log.debug("agent.observation_skipped", extra={**ctx, "step": step_num, "tool": fn_name})
                else:
                    try:
                        observation = self._call_tool(fn_name, fn_args, registry)
                        log.info("agent.observation", extra={**ctx, "step": step_num, "tool": fn_name, "result": observation})
                    except UnauthorisedToolError as e:
                        log.error("agent.unauthorised_tool", extra={**ctx, "step": step_num, "tool": fn_name, "reason": str(e)})
                        steps.append(ReActStep(type="error", content=str(e)))
                        return steps, messages

                steps.append(ReActStep(
                    type="observation",
                    content=observation,
                    tool=fn_name,
                    args=fn_args,
                    result=observation,
                ))
                messages.append({
                    "role": "tool",
                    "content": observation,
                    "name": fn_name,
                })

        else:
            msg = f"max_steps ({self._max_steps}) reached without Final Answer"
            log.warning("agent.max_steps_reached", extra={**ctx, "max_steps": self._max_steps})
            steps.append(ReActStep(type="error", content=msg))

        log.info("agent.run_complete", extra={**ctx, "total_steps": len(steps)})
        return steps, messages

    def _call_tool(self, tool: str, args: dict, registry: SessionRegistry) -> str:
        for cb in self.callbacks:
            cb.on_before(tool, args)
        try:
            result = registry.call(tool, args)
            for cb in self.callbacks:
                cb.on_after(tool, args, result)
            return result
        except UnauthorisedToolError:
            raise
        except Exception as e:
            for cb in self.callbacks:
                cb.on_error(tool, args, e)
            return f"error: {e}"

    def _load_preferences(self) -> str | None:
        path = self.config.get("_preferences_path")
        if not path:
            return None
        from pathlib import Path
        content = Path(path).read_text(encoding="utf-8").strip()
        if not content:
            return None
        
        # Phase 2: Preference length cap
        if len(content) > 2000:
            log.warning("agent.preferences_truncated", extra={"path": path, "original_length": len(content)})
            content = content[:2000] + "\n\n[preferences truncated for length]"
            
        return content

    def _load_session_history(self) -> list[dict]:
        import stash.persistence.sqlite as db
        conn = self.config.get("_db_conn")
        if conn is None:
            return []
        
        # Phase 2: Configurable history limit
        limit = self.config.get("ollama", {}).get("history_limit", 20)
        
        return db.get_history(
            conn,
            rule_id=self.config.get("_rule_id"),
            session_id=self.config.get("_session_id"),
            limit=limit,
        )


class AgentFactory:
    """
    Builds configured Agent instances. Injected into StashApp so the app
    never touches tool internals directly.
    """

    def __init__(self, config: dict, tool_registry: ToolRegistry, tool_schemas: list[dict]) -> None:
        self._config = config
        self._tool_registry = tool_registry
        self._tool_schemas = tool_schemas

    def build(
        self,
        conn: sqlite3.Connection,
        callbacks: list[Callback],
        rule_id: str | None = None,
    ) -> tuple[Agent, SessionRegistry]:
        """
        Build an Agent and a full-access SessionRegistry for manual chat sessions.
        For scheduled rule runs, use the scheduler's own construction path.
        """
        config = {**self._config, "_db_conn": conn, "_rule_id": rule_id}
        registry = self._tool_registry.session(self._tool_registry.all_tools)
        agent = Agent(config, callbacks, self._tool_schemas)
        return agent, registry
