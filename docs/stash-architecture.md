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
| Message bus | `StashApp.post_message` (Textual native) | No physical event bus — StashApp is the hub. All cross-layer messages are Textual `Message` subclasses posted to or bubbled up through `StashApp`. |
| Plan approval UI | Inline `ApproveBar` in `ChatWidget` | Keeps the approval flow co-located with the stream it approves. No separate modal or panel. |
| `ReActStep` schema | Pydantic `BaseModel` | Consistent with the rest of the data layer; validates step type at construction. |
| `PaneHeader` duplication | Co-located in `chat.py` and `sidebar.py` | Six lines of logic; import indirection costs more than it saves at this scale. |
| `display: none` vs `visible: hidden` | `display: none` everywhere | Collapses layout space. Hidden badges and the approve bar should not leave a gap. |
| `RichLog` for audit log | `RichLog` over `ScrollableContainer + Labels` | Native Rich markup, auto-scroll, append-optimised. DOM nodes don't accumulate. |
| `FolderRulesSection.load_rules` | Full replace, not diff | List is small (< 20 entries). Simpler than diffing, correctness is the same. |
| `LoadingScreen` dismiss | `dismiss(value)` not `pop_screen()` | `dismiss` both pops the screen and delivers the typed `HealthResult` return value to the registered callback. `pop_screen` has no return value mechanism. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Textual TUI                        │
│                                                         │
│  ┌──────────────────────────────┐  ┌──────────────────┐ │
│  │         ChatWidget           │  │  SidebarWidget   │ │
│  │  PaneHeader                  │  │  FolderRules     │ │
│  │  MessageBubble (ReAct stream)│  │  Section         │ │
│  │  PlanMessage + ApproveBar    │  │  AuditLog        │ │
│  │  InputArea                   │  │  Section         │ │
│  └──────────────────────────────┘  └──────────────────┘ │
│                                                         │
│  TitleBar: [Ollama ●] [model-badge] [rules-badge]       │
│                                                         │
│  Screens: LoadingScreen · ModelPickerScreen ·           │
│           RuleEditorScreen (all modal, pushed on stack) │
└────────────────────┬────────────────────────────────────┘
                     │
              ┌──────▼──────────┐
              │    StashApp     │  ← message hub; all cross-layer
              │  (post_message) │    communication routes through here
              └──────┬──────────┘
                     │
       ┌─────────────┼──────────────┐
       ▼             ▼              ▼
┌────────────┐ ┌──────────┐ ┌─────────────┐
│ Agent Core │ │  Sched-  │ │   Health    │
│ (ReAct     │ │  uler    │ │   Monitor   │
│  loop)     │ └────┬─────┘ └─────────────┘
└──────┬─────┘      │
       │             │ fires agent runs
┌──────▼─────┐       │
│    Tool    │◄──────┘
│  Registry  │
│ (session-  │
│  scoped)   │
└──────┬─────┘
       │
┌──────▼───────────────────────┐
│        Callback Chain        │
│  on_before → on_after        │
│  AuditLogger · TUIUpdater    │
│  StatusTracker               │
└──────┬───────────────────────┘
       │
  ┌────┴──────────────┐
  ▼                   ▼
SQLite              TinyDB
(audit log,         (folder rules,
 task history,       intervals,
 conversation)       tool grants)
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
  → StashApp.on_task_submitted fires (TaskSubmitted message posted by InputArea)
  → State: IDLE → PLANNING
  → Agent.plan() runs in thread executor (read-only tools only, no writes)
  → Steps returned → PlanMessage + ApproveBar shown inline in ChatWidget
  → State: PLANNING → AWAITING_APPROVAL
  → You click Approve / Reject
      Approve → PlanApproved message bubbles to StashApp
        → State: AWAITING_APPROVAL → RUNNING
        → Agent.run() executes in thread executor
            → Each tool call hits the callback chain
                → AuditLogger writes step to SQLite
                → TUIUpdater posts ReactStepReady → chat stream updates live
        → Final answer emitted, run logged
        → State: RUNNING → IDLE
      Reject → PlanRejected message bubbles to StashApp
        → Run marked failed in SQLite
        → State: AWAITING_APPROVAL → IDLE
```

### Scheduled Rule

```
APScheduler fires rule at defined interval (e.g. every 6 hours)
  → StashScheduler._run_rule() (async, on event loop)
  → Loads rule from TinyDB (instructions, allowed tools, target path)
  → Tool scope pre-approved from rule definition — no approval step
  → Opens its own SQLite connection
  → Builds Agent with callbacks: AuditLogger + TUIUpdater + StatusTracker
  → agent.run() in thread executor
      → Callbacks fire as normal
      → SQLite audit log written
      → last_run + last_run_status updated in TinyDB
  → RuleCompleted message posted to StashApp via post_message
  → StashApp updates sidebar rule status badge
```

### Thread boundary note

The agent loop (`Agent._loop`) is synchronous and runs in `asyncio.run_in_executor`. Callbacks also run in that thread. `TUIUpdater.on_after` uses `call_from_thread` to safely post `ReactStepReady` back to the Textual event loop. The scheduler's `_run_rule` is `async` — after `await run_in_executor` returns, it is back on the event loop and calls `post_message` directly (no `call_from_thread` needed there).

---

## Startup Sequence

```
main.py
 ├── Load config.toml (generate default on first run)
 ├── Setup logging → ~/.stash/stash.log
 ├── Ensure data directory (~/.stash) exists
 ├── Connect SQLite, run migrations
 ├── Open TinyDB rules store
 ├── Health check — ping Ollama (runs before TUI launches)
 │     ├── Unreachable           → hard exit, clear message, no TUI
 │     ├── OK                    → HealthResult(OK, available_models)
 │     ├── Model missing         → HealthResult(MODEL_MISSING, available_models)
 │     └── No model configured   → HealthResult(NO_MODEL_SELECTED, available_models)
 ├── Build object graph: ToolRegistry, AgentFactory, StashScheduler
 ├── Build StashApp (receives pre-computed HealthResult)
 ├── Wire circular dep: scheduler.set_app(app)
 └── app.run()

StashApp.on_mount
 └── push_screen(LoadingScreen(health_result), callback=_on_loading_done)
       ↓ (5-second animated splash)
     LoadingScreen.dismiss(health_result)
       ↓
     _on_loading_done(health_result)
       ├── scheduler.start() — registers APScheduler jobs from enabled rules
       ├── set_interval(30s, _poll_ollama) — live Ollama status polling
       ├── sidebar.load_rules(...)
       ├── if NO_MODEL_SELECTED or MODEL_MISSING:
       │     push_screen(ModelPickerScreen, callback=_on_model_selected)
       └── call_after_refresh(_restore_main_focus) — enable chat input
```

---

## Message Types

All cross-layer messages are Textual `Message` subclasses. `StashApp` is the handler for all of them — nothing in `tui/` talks to `core/` or `scheduler/` directly.

| Message | Posted by | Handled by | Meaning |
|---|---|---|---|
| `TaskSubmitted` | `InputArea` (in ChatWidget) | `StashApp` | User submitted a task |
| `PlanApproved` | `ApproveBar` (in ChatWidget) | `StashApp` | User approved the plan |
| `PlanRejected` | `ApproveBar` (in ChatWidget) | `StashApp` | User rejected the plan |
| `ReactStepReady` | `TUIUpdater` callback | `StashApp` | One ReAct step completed during execution |
| `RuleCompleted` | `StashScheduler` | `StashApp` | A scheduled rule finished (pass/fail) |
| `OllamaStatusChanged` | `StashApp._poll_ollama` | `StashApp` | Ollama reachability changed |

`TaskSubmitted`, `PlanApproved`, and `PlanRejected` live in `stash/tui/messages.py` (not `app.py`) to avoid a circular import: `ChatWidget` posts them and `StashApp` handles them, so neither can import the other.

---

## State Machine

`StashApp` manages a `RunState` enum. Only one task can run at a time.

```
IDLE
  │  TaskSubmitted
  ▼
PLANNING  (agent.plan() in executor)
  │  plan steps returned
  ▼
AWAITING_APPROVAL  (PlanMessage + ApproveBar visible)
  │  PlanApproved          │  PlanRejected
  ▼                        ▼
RUNNING                  IDLE
(agent.run() in executor)
  │
  ▼
IDLE
```

Any `TaskSubmitted` received while not in `IDLE` is silently dropped (logged as a warning).

---

## Folder Rule Schema (TinyDB)

Each rule is a JSON document stored in TinyDB:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Downloads Cleanup",
  "target_path": "/home/ogie/Downloads",
  "instructions": "Move video files to /Media/Videos. Delete anything older than 30 days that isn't a document.",
  "allowed_tools": ["ls", "mv", "rm", "glob"],
  "interval_hours": 6,
  "enabled": true,
  "created_at": "2025-01-01T00:00:00",
  "last_run": "2025-01-03T06:00:00",
  "last_run_status": "completed"
}
```

Rules are created and edited through the TUI (`RuleEditorScreen`). The scheduler reads `interval_hours` and `enabled` on boot and registers APScheduler jobs accordingly. Changing an interval in the TUI reschedules the job live — no restart needed. Rule IDs are UUIDs generated at creation time.

---

## Config Structure (TOML)

```toml
[data]
dir = "~/.stash"

[ollama]
host = "http://localhost:11434"
max_steps = 20
# model is set via the model picker on first run and written back here
# model = "gemma4:4b"
```

In memory the config is a nested dict:

```python
{
    "data": {"dir": "~/.stash"},
    "ollama": {
        "host": "http://localhost:11434",
        "max_steps": 20,
        "model": "gemma4:4b",   # written after model picker
    }
}
```

`Agent.__init__` reads `config.get("ollama", {}).get(...)` for all values. `_save_config()` in `StashApp` writes the entire dict back to `config.toml` via `tomli_w` whenever the model is changed.

---

## Tool Registry

Tools are atomic, pure functions. Each module exports a callable and a schema dict. The schema (name, description, typed args, `readonly` flag) is passed to the model so it knows what's available, and rendered in the plan card so you can see exactly what each step intends to call.

```python
class ToolRegistry:
    def __init__(self, tools: dict[str, Callable]) -> None:
        self._all = tools  # {"ls": ls_fn, "mv": mv_fn, ...}

    def session(self, approved: list[str]) -> SessionRegistry:
        # Agent can only see and call tools in this dict
        return SessionRegistry({k: self._all[k] for k in approved if k in self._all})
```

`SessionRegistry.call(tool, args)` raises `UnauthorisedToolError` if the tool isn't in the approved set — not a warning, a hard stop that terminates the run.

In plan mode (`dry_run=True`), tools marked `readonly: True` in their schema are still executed. Write tools are skipped and replaced with `"[plan mode — not executed]"` as the observation.

---

## Callback Chain

Every tool call passes through the callback chain before and after execution:

```python
class Callback(Protocol):
    def on_before(self, tool: str, args: dict) -> None: ...
    def on_after(self, tool: str, args: dict, result: str) -> None: ...
    def on_error(self, tool: str, args: dict, error: Exception) -> None: ...
```

Default callbacks:

| Callback | Responsibility |
|---|---|
| `AuditLogger` | Writes observation steps to SQLite after every call |
| `TUIUpdater` | Posts `ReactStepReady` to `StashApp` via `call_from_thread` (bridges sync executor → async event loop) |
| `StatusTracker` | Updates `last_run_status` to `"failed"` in TinyDB on tool errors (rule runs only) |

---

## ReAct Step Schema

Every step the agent takes is a structured Pydantic model:

```python
class ReActStep(BaseModel):
    type: Literal["thought", "action", "observation", "final", "error"]
    content: str
    tool: str | None = None
    args: dict | None = None
    result: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
```

Steps are written to SQLite as they happen and streamed to the TUI chat pane in real time via `ReactStepReady` messages. The `error` type covers both parse failures and unauthorised tool calls.

---

## TUI Layer

### Screen Stack

Textual's screen stack is used for all modal flows. `StashApp.on_mount` pushes screens on top of `MainScreen`.

| Screen | Type | Purpose |
|---|---|---|
| `MainScreen` | base | Three-pane layout (TitleBar + ChatWidget + SidebarWidget + Footer) |
| `LoadingScreen` | `Screen[HealthResult \| None]` | Animated boot splash; dismisses with `HealthResult` after 5s |
| `ModelPickerScreen` | `ModalScreen[str \| None]` | ListView of pulled models (or manual input if none); dismisses with model name |
| `RuleEditorScreen` | `ModalScreen[FolderRule \| None]` | Form for creating / editing folder rules; dismisses with `FolderRule` or `None` |

### Widget Hierarchy (MainScreen)

```
MainScreen
├── TitleBar (docked top)
│   ├── #ollama-badge  (green/red/amber pill, animated pulse)
│   ├── #model-badge   (hidden until model selected)
│   └── #rules-badge   (hidden until rules exist)
├── Horizontal
│   ├── ChatWidget (1fr)
│   │   ├── PaneHeader
│   │   ├── ScrollableContainer #stream
│   │   │   ├── MessageBubble* (type: user/thought/action/observation/final/error/system)
│   │   │   └── PlanMessage (inline plan card, shown after planning)
│   │   │       └── PlanStepRow* (one per action step)
│   │   ├── ApproveBar (display:none by default)
│   │   └── InputArea
│   └── SidebarWidget (44 cells fixed)
│       ├── PaneHeader
│       ├── FolderRulesSection
│       │   └── RuleItem* (one per rule)
│       └── AuditLogSection (RichLog)
└── Footer
```

### Query scoping

`StashApp` has no `compose()` tree of its own — `MainScreen` is a pushed screen. All widget queries from `StashApp` must use `self.screen.query_one(...)`, not `self.query_one(...)`. `App.query_one` only searches `App._default_screen`, which is empty.

### Focus restoration

`ChatWidget.on_mount` calls `set_enabled(True)` as a default, but this fires while `LoadingScreen` is the active screen — Textual discards the `focus()` call silently. The focus the user actually gets comes from `StashApp._restore_main_focus()`, called via `call_after_refresh` after `LoadingScreen` and `ModelPickerScreen` dismiss. `on_mount` is kept as a belt-and-suspenders default in case the startup order ever changes.

---

## Project Structure

```
stash/
├── config.toml                  # Ollama endpoint, model name, data dir
├── main.py                      # Entrypoint — composition root, boots everything
│
├── core/
│   ├── agent.py                 # ReAct loop (Agent, AgentFactory, ReActStep)
│   ├── registry.py              # ToolRegistry, SessionRegistry, UnauthorisedToolError
│   └── callbacks.py             # Callback protocol + AuditLogger, TUIUpdater, StatusTracker
│
├── tools/
│   ├── __init__.py              # Exports ALL_TOOLS (dict) and ALL_SCHEMAS (list)
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
│   └── tinydb.py                # Folder rules CRUD (FolderRule, RulesDB)
│
├── health/
│   └── ollama.py                # check(), fetch_models(), pull_model()
│
├── log.py                       # Logging setup
│
└── tui/
    ├── app.py                   # StashApp — state machine + all cross-layer message handlers
    ├── messages.py              # Shared message types (TaskSubmitted, PlanApproved, PlanRejected)
    ├── app.tcss                 # Global CSS
    ├── screens/
    │   ├── main.py              # MainScreen — three-pane layout
    │   ├── loading.py           # LoadingScreen — animated boot splash
    │   ├── model_picker.py      # ModelPickerScreen — model selection modal
    │   └── rule_editor.py       # RuleEditorScreen — create / edit folder rules
    └── widgets/
        ├── title_bar.py         # TitleBar — Ollama/model/rules badges with pulse
        ├── chat.py              # ChatWidget — task input, ReAct stream, plan approval
        └── sidebar.py           # SidebarWidget — rules list + audit log
```

**Rule:** nothing in `tui/` touches the filesystem directly. It only talks to `core/` and `persistence/` by posting Textual messages through `StashApp`.

---

## V1 Scope Boundary

**In scope:**
- Manual tasks via chat interface
- Folder rules with recurrent interval scheduling
- Per-task HITL plan approval with locked tool scope
- Full audit log (SQLite)
- Ollama health check on startup + live 30-second polling
- Rule editor in TUI
- Model picker on first run and on-demand via `ctrl+o`

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
| `textual >= 8.2.3` | TUI framework |
| `ollama >= 0.6.1` | Talk to local Ollama endpoint |
| `apscheduler >= 3.11.2` | In-process interval scheduling |
| `tinydb >= 4.8.2` | JSON document store for folder rules |
| `pydantic >= 2.12.5` | Data validation — `ReActStep`, `FolderRule`, `PendingRun` |
| `tomli-w >= 1.2.0` | Write config.toml back after model selection |
| `httpx >= 0.28.1` | HTTP client (available for health checks / future use) |
| `sqlite3` | Stdlib — audit log and history |
| `tomllib` | Stdlib (3.11+) — config parsing |

No agent framework. No LangChain. No LlamaIndex. The ReAct loop is ours.
