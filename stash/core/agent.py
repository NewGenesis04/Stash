"""
Agent core — pure, stateless ReAct loop.

Each run is independent: takes a task + session registry + callbacks,
runs Thought → Action → Observation until a final answer is reached,
and returns the full step log.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, UTC
from typing import Literal

import ollama
from pydantic import BaseModel, Field

from stash.core.registry import SessionRegistry, ToolRegistry, UnauthorisedToolError
from stash.core.callbacks import Callback

log = logging.getLogger(__name__)

_REACT_FORMAT = """
Use ONLY the following format — no deviations:

Thought: <your reasoning>
Action: <tool name>
Action Input: <valid JSON object matching the tool's args>

When you have finished the task, use:

Thought: <your reasoning>
Final Answer: <summary of what was done>

Rules:
- Only call tools that are listed below.
- Action Input must be a valid JSON object.
- Never invent tool names.
- One action per response.
""".strip()


def _build_system_prompt(registry: SessionRegistry, tools: list[dict]) -> str:
    available = {t["name"]: t for t in tools if t["name"] in registry.available}
    tool_lines = "\n".join(
        f"- {t['name']}: {t['description']}"
        for t in available.values()
    )
    return f"You are Stash, a local file organisation agent.\n\n{_REACT_FORMAT}\n\nAvailable tools:\n{tool_lines}"


def _parse_response(text: str) -> tuple[str, str | None, dict | None, str | None]:
    """
    Parse a model response into (thought, action, action_input, final_answer).
    Returns (thought, None, None, final_answer) or (thought, action, args, None).
    Raises ValueError if the response is malformed.
    """
    thought = action = action_input_raw = final_answer = None

    for line in text.splitlines():
        match line.strip().split(":", 1):
            case ["Thought", value]:
                thought = value.strip()
            case ["Action Input", value]:
                action_input_raw = value.strip()
            case ["Action", value]:
                action = value.strip()
            case ["Final Answer", value]:
                final_answer = value.strip()

    if thought is None:
        raise ValueError(f"no Thought in response: {text!r}")

    if final_answer is not None:
        return thought, None, None, final_answer

    if action is None:
        raise ValueError(f"no Action or Final Answer in response: {text!r}")

    try:
        args = json.loads(action_input_raw or "{}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Action Input is not valid JSON: {action_input_raw!r}") from e

    return thought, action, args, None


class ReActStep(BaseModel):
    type: Literal["thought", "action", "observation", "final", "error"]
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
        self._client = ollama.Client(host=ollama_config.get("endpoint", "http://localhost:11434"))
        self._model = ollama_config.get("model")
        if not self._model:
            raise ValueError("No model selected. Launch the app and pick a model first.")
        self._max_steps = ollama_config.get("max_steps", 20)

    def plan(self, task: str, registry: SessionRegistry, run_id: str | None = None) -> list[ReActStep]:
        """Dry-run the ReAct loop — tools are not executed. Used for HITL approval."""
        return self._loop(task, registry, dry_run=True, run_id=run_id)

    def run(self, task: str, registry: SessionRegistry, run_id: str | None = None) -> list[ReActStep]:
        """Execute the ReAct loop against an approved session registry."""
        return self._loop(task, registry, dry_run=False, run_id=run_id)

    # ------------------------------------------------------------------

    def _loop(self, task: str, registry: SessionRegistry, dry_run: bool, run_id: str | None = None) -> list[ReActStep]:
        run_id = run_id or str(uuid.uuid4())
        ctx = {"run_id": run_id, "model": self._model, "dry_run": dry_run}

        log.info("agent.run_start", extra={**ctx, "task": task, "tools": registry.available})

        system = _build_system_prompt(registry, self.tools)
        messages = [{"role": "system", "content": system}]

        if not dry_run:
            messages.extend(self._load_history())

        messages.append({"role": "user", "content": task})

        steps: list[ReActStep] = []

        for step_num in range(self._max_steps):
            response = self._client.chat(model=self._model, messages=messages)
            text = response["message"]["content"]

            try:
                thought, action, args, final_answer = _parse_response(text)
            except ValueError as e:
                log.error("agent.parse_error", extra={**ctx, "step": step_num, "reason": str(e), "raw": text})
                steps.append(ReActStep(type="error", content=str(e)))
                break

            log.info("agent.thought", extra={**ctx, "step": step_num, "thought": thought})
            steps.append(ReActStep(type="thought", content=thought))

            if final_answer is not None:
                log.info("agent.final", extra={**ctx, "step": step_num, "answer": final_answer})
                steps.append(ReActStep(type="final", content=final_answer))
                break

            log.info("agent.action", extra={**ctx, "step": step_num, "tool": action, "args": args})
            steps.append(ReActStep(type="action", content=action, tool=action, args=args))
            messages.append({"role": "assistant", "content": text})

            tool_schema = next((t for t in self.tools if t["name"] == action), None)
            is_readonly = tool_schema.get("readonly", False) if tool_schema else False

            if dry_run and not is_readonly:
                observation = "[plan mode — not executed]"
                log.debug("agent.observation_skipped", extra={**ctx, "step": step_num, "tool": action})
            else:
                try:
                    observation = self._call_tool(action, args, registry)
                    log.info("agent.observation", extra={**ctx, "step": step_num, "tool": action, "result": observation})
                except UnauthorisedToolError as e:
                    log.error("agent.unauthorised_tool", extra={**ctx, "step": step_num, "tool": action, "reason": str(e)})
                    steps.append(ReActStep(type="error", content=str(e)))
                    break

            steps.append(ReActStep(
                type="observation",
                content=observation,
                tool=action,
                args=args,
                result=observation,
            ))
            messages.append({"role": "user", "content": f"Observation: {observation}"})

        else:
            msg = f"max_steps ({self._max_steps}) reached without Final Answer"
            log.warning("agent.max_steps_reached", extra={**ctx, "max_steps": self._max_steps})
            steps.append(ReActStep(type="error", content=msg))

        log.info("agent.run_complete", extra={**ctx, "total_steps": len(steps)})
        return steps

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

    def _load_history(self) -> list[dict]:
        import stash.persistence.sqlite as db
        conn = self.config.get("_db_conn")
        rule_id = self.config.get("_rule_id")
        if conn is None:
            return []
        return db.get_history(conn, rule_id=rule_id)


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
