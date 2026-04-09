# Stash — Project Architecture

> A local-first, agent-powered file management TUI. Self-contained, auditable, and built around human-in-the-loop control.

---

## Overview

Stash is a TUI application that runs a local agent to help you manage your filesystem. You give it tasks in natural language, it plans what it's going to do and which tools it needs, you approve the plan, and it executes. Everything is powered by a local model (Gemma 4 via Ollama) — no cloud, no telemetry, no nonsense.

Folder rules let you define how a directory should be managed on a recurring schedule. The agent runs those rules automatically at whatever interval you set, using only the tools you pre-approved when you defined the rule.

---

## Core Design Principles

- **Human-in-the-loop, per task** — the agent surfaces its full plan before executing anything. You approve the plan and the tool set. Only then does it run.
- **Atomic, scoped tool access** — tools are session-scoped. If you didn't approve it, the agent literally cannot call it. No soft warnings, hard boundary.
- **Full auditability** — every ReAct step, every tool call, every result is written to SQLite immediately. Nothing happens off the record.
- **Local-first** — Ollama runs on your machine. Your files never leave.
- **Pure ReAct** — no framework magic. The agent loop is hand-rolled: Thought → Action → Observation → repeat until final answer.

---

## Decisions Log

| Decision | Choice | Reason |
|---|---|---|
| HITL granularity | Per-task | No micro-managing mid-execution |
| Scheduled rule approval | Pre-signed at rule definition time | Tool scope locked when you write the rule |
| Scheduled rule execution | Fully automatic (recurrent interval) | Set it and forget it |
| Model runtime | Ollama (local) | Self-contained, no cloud dependency |
| Model | Gemma 4 (4B or 12B) | Lightweight, built for edge compute |
| Agent pattern | Pure ReAct, hand-rolled | Full control, no framework overhead |
| Persistence — structured | SQLite | Audit log, task history, conversation history |
| Persistence — documents | TinyDB | Folder rules, JSON-shaped, easy to edit |
| Scheduler | APScheduler (in-process, interval-based) | Shares state with app, no IPC headaches |
| TUI framework | Textual | Mature, reactive, well-documented |
| Config | TOML | Set-once infrastructure config |
| V1 tool set | `ls`, `mv`, `mkdir`, `rm`, `rename`, `glob` | Atomic file ops, nothing more |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Textual TUI                      │
│                                                     │
│  ┌──────────────┐ ┌─────────────┐ ┌──────────────┐ │
│  │  Chat/Task   │ │   Plan      │ │  Audit Log / │ │
│  │  + ReAct     │ │  Approval   │ │  Rules       │ │
│  │  Stream      │ │  Panel      │ │  Sidebar     │ │
│  └──────────────┘ └─────────────┘ └──────────────┘ │
│                                                     │
│  [Ollama Status]  [Scheduler Status]  [Active Rule] │
└───────────────────────┬─────────────────────────────┘
                        │
              ┌─────────▼──────────┐
              │    Event Bus       │  ← All layers communicate here
              └─────────┬──────────┘
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
  ┌─────────────┐ ┌──────────┐ ┌─────────────┐
  │ Agent Core  │ │  Sched-  │ │   Health    │
  │ (ReAct loop)│ │  uler    │ │   Monitor   │
  └──────┬──────┘ └────┬─────┘ └─────────────┘
         │             │
  ┌──────▼──────┐      │ fires agent runs
  │    Tool     │◄─────┘
  │   Registry  │
  │ (session-   │
  │  scoped)    │
  └──────┬──────┘
         │
  ┌──────▼──────────────────────┐
  │       Callback Chain        │
  │   on_before → on_after      │
  └──────┬──────────────────────┘
         │
    ┌────┴──────────────┐
    ▼                   ▼
 SQLite              TinyDB
 (audit log,         (folder rules,
  history,            intervals,
  task runs)          tool grants)
         │
         ▼
       Ollama
    (Gemma 4 local)
```

---

## Data Flows

### Manual Task

```
You type a task
  → Agent Core generates full ReAct plan (no execution yet)
  → Plan surfaces in TUI approval panel
  → You review plan + approve allowed tools
  → Session registry is locked to approved tools only
  → Agent Core executes step by step
      → Each tool call hits the callback chain
          → SQLite write (before + after)
          → TUI live update
  → Final answer emitted
  → Task closed, full log queryable
```

### Scheduled Rule

```
APScheduler fires rule at defined interval (e.g. every 6 hours)
  → Loads rule document from TinyDB
      (instructions, allowed tools, target path)
  → Tool scope is already pre-approved from rule definition
  → Spins up Agent Core with rule context
  → Executes — callbacks fire as normal
      → SQLite audit log written
      → last_run + last_run_status updated in TinyDB
  → TUI shows notification + log entry next time you open it
```

---

## Startup Sequence

```
Boot
 ├── Load config.toml
 ├── Connect SQLite, run migrations if needed
 ├── Load TinyDB rules
 ├── Health check → ping Ollama
 │     ├── Running + model pulled   → green, fully operational
 │     ├── Running + model missing  → warn, offer to pull inline
 │     └── Ollama not running       → hard block with clear message
 ├── Register APScheduler interval jobs from enabled rules
 └── Launch Textual TUI
```

---

## Folder Rule Schema (TinyDB)

Each rule is a JSON document stored in TinyDB:

```json
{
  "id": "rule_001",
  "name": "Downloads Cleanup",
  "target_path": "/home/ogie/Downloads",
  "instructions": "Move video files to /Media/Videos. Delete anything older than 30 days that isn't a document.",
  "allowed_tools": ["ls", "mv", "rm", "glob"],
  "interval_hours": 6,
  "enabled": true,
  "created_at": "2025-01-01T00:00:00",
  "last_run": "2025-01-03T06:00:00",
  "last_run_status": "success"
}
```

Rules are created and edited through the TUI. The scheduler reads `interval_hours` and `enabled` on boot and registers jobs accordingly. Changing an interval in the TUI reschedules the job live — no restart needed.

---

## Tool Registry

Tools are atomic, pure functions. Each has a schema (name, description, typed args) that is passed to the model so it knows what's available, and also rendered in the plan approval panel so you can see exactly what each step intends to call.

```python
class ToolRegistry:
    def __init__(self):
        self._all_tools = {
            "ls":     ls_tool,
            "mkdir":  mkdir_tool,
            "rm":     rm_tool,
            "mv":     mv_tool,
            "rename": rename_tool,
            "glob":   glob_tool,
        }

    def get_session_registry(self, approved: list[str]) -> dict:
        # Agent can only see and call tools in this dict
        return {k: self._all_tools[k] for k in approved if k in self._all_tools}
```

The agent's execute loop dispatches only from the session registry returned for that task or rule. Calling anything outside it raises `UnauthorisedToolError` — not a warning, a hard stop.

---

## Callback Chain

Every tool call, before and after execution, passes through the callback chain:

```python
def execute_tool(name, args, session_registry, callbacks):
    if name not in session_registry:
        raise UnauthorisedToolError(f"{name} was not approved for this task")

    for cb in callbacks:
        cb.on_before(name, args)

    result = session_registry[name](**args)

    for cb in callbacks:
        cb.on_after(name, args, result)

    return result
```

Default callbacks:
- **AuditLogger** — writes to SQLite before and after every call
- **TUIUpdater** — pushes a live event to the Textual app
- **StatusTracker** — updates `last_run` and `last_run_status` on rule runs

You can add more callbacks without touching any other layer.

---

## ReAct Step Schema

Every step the agent takes is a structured event — not raw text:

```python
@dataclass
class ReActStep:
    type: Literal["thought", "action", "observation", "final"]
    content: str
    tool: str | None = None
    args: dict | None = None
    result: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
```

Steps are written to SQLite as they happen and streamed to the TUI chat pane in real time. You watch it think.

---

## Project Structure

```
stash/
├── config.toml                  # Ollama endpoint, model name, data dir
├── main.py                      # Entrypoint — boots everything in order
│
├── core/
│   ├── agent.py                 # ReAct loop — pure, stateless per run
│   ├── registry.py              # ToolRegistry, session scoping
│   ├── callbacks.py             # Callback chain definitions
│   └── events.py                # Event bus
│
├── tools/
│   ├── __init__.py
│   ├── ls.py
│   ├── mv.py
│   ├── mkdir.py
│   ├── rm.py
│   ├── rename.py
│   └── glob.py
│
├── scheduler/
│   └── runner.py                # APScheduler setup, job registration, live rescheduling
│
├── persistence/
│   ├── sqlite.py                # Audit log, task history, conversation history
│   └── tinydb.py                # Folder rules CRUD
│
├── health/
│   └── ollama.py                # Startup ping, model check, pull offer
│
└── tui/
    ├── app.py                   # Textual app root
    ├── screens/
    │   ├── main.py              # Main screen layout
    │   └── rule_editor.py       # Create / edit folder rules
    └── widgets/
        ├── chat.py              # Task input + live ReAct stream
        ├── plan_approval.py     # Plan review + tool approval panel
        └── sidebar.py           # Audit log, rules list, status indicators
```

**Rule:** nothing in `tui/` touches the filesystem directly. It only talks to `core/` and `persistence/` through the event bus.

---

## V1 Scope Boundary

**In scope:**
- Manual tasks via chat interface
- Folder rules with recurrent interval scheduling
- Per-task HITL plan approval with locked tool scope
- Full audit log (SQLite)
- Ollama health check on startup
- Rule editor in TUI

**Explicitly out of scope for V1:**
- Multi-agent orchestration
- Cloud sync or remote access
- Docker packaging
- Tools beyond the core six (`ls`, `mv`, `mkdir`, `rm`, `rename`, `glob`)
- Auth or multi-user support
- Any frontend

---

## Dependencies

| Package | Purpose |
|---|---|
| `textual` | TUI framework |
| `ollama` or `httpx` | Talk to local Ollama endpoint |
| `apscheduler` | In-process interval scheduling |
| `tinydb` | JSON document store for folder rules |
| `sqlite3` | Stdlib — audit log and history |
| `tomllib` | Stdlib (3.11+) — config parsing |
| `pydantic` | Data validation for tool args and ReAct steps |

No agent framework. No LangChain. No LlamaIndex. The ReAct loop is ours.
