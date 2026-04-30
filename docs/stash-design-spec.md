# stash — UI Design Specification
**v0.2 · Local-first File Management Agent**

> A local-first, agent-powered file management TUI. Self-contained, auditable, and built around human-in-the-loop control. Powered by Gemma 4 via Ollama. Your files never leave your machine.

---

## 00 Changelog

| Version | Date | Changes |
|---|---|---|
| v0.1 | 2026-04-09 | Initial spec |
| v0.2 | 2026-04-30 | Added loading screen, model picker, location registry screens, folder picker; updated keybindings, tool set, architecture decisions; corrected sidebar width; added boot flow and run state machine |

---

## 01 Design Philosophy

stash is a developer tool, not a consumer app. The aesthetic should feel like a terminal that went to design school — dark, monospaced, structured, and calm. Every element earns its place. Nothing decorative.

- Dark background at all times — no light mode default
- Default theme: **nord** (Textual built-in); user can cycle with `ctrl+t`
- Monospace font throughout — Courier New or JetBrains Mono
- Accent colours carry semantic meaning, not decoration
- Borders are subtle — they define space, not shout
- The agent should feel like a colleague, not a chatbot
- Status is always visible — the user should never wonder what is happening

---

## 02 Colour Palette

All colours are defined for dark mode. stash supports Textual's built-in theme cycling (`ctrl+t`) — accent roles shift per theme but the palette below defines the default.

### 2.1 Base Surfaces

| Swatch | Name | Hex | Role |
|---|---|---|---|
| 🟫 | Background | `#0E0E0F` | App root, deepest surface |
| 🟫 | Panel | `#161B22` | Pane headers, title bar, modal dialogs |
| 🟫 | Surface | `#21262D` | Message bubbles, code blocks, inputs |
| 🟫 | Border | `#30363D` | All structural borders and dividers |

### 2.2 Text

| Name | Hex | Role |
|---|---|---|
| Text Primary | `#C9D1D9` | Main body text, message content |
| Text Muted | `#8B949E` | Labels, timestamps, hints, secondary info |

### 2.3 Accent Colours

Each accent colour carries a fixed semantic meaning across the entire app. Never swap them.

| Name | Hex | Semantic Role |
|---|---|---|
| Accent Blue | `#58A6FF` | User input, keybindings, app name, info badges |
| Accent Green | `#3FB950` | Agent actions, tool calls, success states, Ollama online |
| Accent Purple | `#8957E5` | Agent thought / reasoning steps (italic) |
| Accent Amber | `#D29922` | Observations, warnings, scheduler status |
| Accent Red | `#F85149` | Reject actions, errors, destructive confirmations |

### 2.4 Badge Backgrounds

Status badges use a tinted background + matching border + accent text. Never use solid fills.

| Badge Type | Background | Border | Text colour |
|---|---|---|---|
| Ollama Online | `#0D2B1A` | `#238636` | `#3FB950` |
| Active Model | `#0D1F38` | `#1F6FEB` | `#58A6FF` |
| Warning / Scheduler | `#2B1D0A` | `#9E6A03` | `#D29922` |
| Error / Offline | `#2B0D0D` | `#6E2B2B` | `#F85149` |

---

## 03 Typography

stash uses a single font family throughout: Courier New (or JetBrains Mono as a drop-in). No serif. No sans-serif body text. Everything is monospace — this is a terminal app.

| Element | Size | Weight | Colour |
|---|---|---|---|
| App name / logo | 13px | Bold | `#58A6FF` |
| Pane headers | 11px | Regular | `#8B949E`, uppercase |
| Message content | 12px | Regular | `#C9D1D9` |
| Agent thought | 12px | Regular italic | `#8957E5` |
| Tool chips / keys | 10–11px | Regular | Semantic accent per role |
| Timestamps / meta | 10px | Regular | `#8B949E` |
| Status bar | 10px | Regular | `#8B949E` |
| Plan step description | 11px | Regular | `#8B949E` |

---

## 04 Layout

### 4.1 Overall Structure

The app is divided into four horizontal zones stacked vertically:

1. **Title Bar** — app name, Ollama status badge, model badge, active rules count
2. **Main Layout** — two-column: chat pane (flex: 1) + sidebar (fixed 44 columns)
3. **Approve Bar** — appears above input when a plan is pending, disappears after
4. **Footer** — Textual `Footer` widget; always visible, shows all active keybindings

```
┌─────────────────────────────────────────────────────┐
│  Title Bar — stash  ● ollama running  gemma4:4b     │
├────────────────────────────────────┬────────────────┤
│                                    │  Folder Rules  │
│         Chat / Task Pane           ├────────────────┤
│           (flex: 1)                │  Audit Log     │
│                                    │  (44 cols)     │
├────────────────────────────────────┴────────────────┤
│  Approve Bar (conditional)                          │
├─────────────────────────────────────────────────────┤
│  Footer — ctrl+t  ctrl+n  ctrl+l  ctrl+r  ctrl+q   │
└─────────────────────────────────────────────────────┘
```

### 4.2 Chat Pane (left, flex: 1)

The primary interaction surface. Three sub-zones stacked:

- **Pane header** — label `task / chat`, keybinding hint right-aligned
- **Message stream** — scrollable, messages render top to bottom as they arrive
- **Input area** — prompt prefix (`›`), text input, enter hint

Message types and their left border accent:

| Message Type | Left Border | Label |
|---|---|---|
| User message | 2px `#58A6FF` | `you` |
| Agent thought | 2px `#8957E5` | `stash — thinking` (italic) |
| Agent action | 2px `#3FB950` | `stash — executing` |
| Observation | 2px `#D29922` | `stash — observed` |
| System / plan pending | 2px `#D29922` | `stash — plan ready · awaiting approval` |
| Final answer | 2px `#58A6FF` | `stash — done` |

### 4.3 Plan Approval Panel

Renders inside the chat pane as a system message when a plan is ready. Contains:

- **Tool chip row** — all requested tools listed as tinted chips above the plan
- **Plan steps table** — step number, tool chip, description, status circle (○ pending / ✓ done)
- **Approve bar** — `approve plan?` label + Approve button (green) + Reject button (red)

The approve bar is a separate fixed zone above the chat input. It disappears once the plan is approved or rejected. Keybindings: Enter to approve, Esc to reject.

### 4.4 Sidebar (right, 44 columns fixed)

Split into two sections separated by a border:

- **Folder Rules** (top) — each rule shows name, interval + tools, status dot
  - ● green = last run OK
  - ◷ blue = scheduled, next run countdown
  - dim / grey = paused
- **Audit Log** (bottom, scrollable) — each entry: timestamp, tool chip, path/result

Sidebar pane headers follow the same pattern as the chat pane header — muted uppercase label + keybinding chip right-aligned.

---

## 05 Boot Flow

### 5.1 Sequence

On launch the app runs this sequence:

1. **LoadingScreen** pushes over MainScreen — 5-second animated splash
   - STASH ASCII art with a sweeping blue → purple → green colour gradient (20 fps)
   - Fading status messages: `Connecting to Ollama…` → `Loading rules…` → `Warming up…` → `Ready`
   - Fill progress bar tracking the four phases
   - Dismisses automatically after 5 seconds, passing the `HealthResult` to the app
2. **ModelPickerScreen** (conditional) — pushed if Ollama is running but no model is selected or the configured model is missing. Skipped on normal runs.
3. **MainScreen** — revealed when loading screen dismisses

### 5.2 Run State Machine

The app enforces a strict state machine for the chat → plan → approve → execute flow. Only one run can be active at a time.

```
IDLE → PLANNING → AWAITING_APPROVAL → RUNNING → IDLE
```

| State | Chat input | Description |
|---|---|---|
| `IDLE` | Enabled | Ready for user input |
| `PLANNING` | Disabled | Agent is generating a plan in executor thread |
| `AWAITING_APPROVAL` | Disabled | Plan shown, waiting for user to approve or reject |
| `RUNNING` | Disabled | Agent is executing approved steps |

---

## 06 Screens

### 6.1 MainScreen

The persistent base screen. Always on the bottom of the stack. Composes `TitleBar`, `ChatWidget`, `SidebarWidget`, and Textual `Footer`. Modal screens push on top of it.

### 6.2 LoadingScreen

Boot splash. Non-modal `Screen`, pushed on top of `MainScreen` on startup. Auto-dismisses after 5 seconds.

### 6.3 ModelPickerScreen

`ModalScreen[str | None]`. Two states:

- **Models found** — scrollable `ListView` of available Ollama model names, arrow-key navigation, Enter to confirm
- **No models** — manual text `Input` with a hint to run `ollama pull <name>` first

Triggered automatically on first run or when the configured model is not installed. Also accessible at any time via `ctrl+o`. Saves the selection to `config.toml` on confirm.

### 6.4 RuleEditorScreen

`ModalScreen[FolderRule | None]`. Form for creating and editing folder rules. Fields:

- **Name** — text input
- **Target path** — text input + **Browse** button → opens `FolderPickerScreen`; the selected path is written back into the field. Manual typing also accepted.
- **Instructions** — text input; natural-language prompt for the scheduled agent
- **Run every** — `Select` widget with preset intervals (1h / 6h / 12h / 24h / 72h / 168h)
- **Allowed tools** — checkboxes for each tool in the set; all checked by default on new rules
- **Enabled** — checkbox

`resolve_location` is intentionally excluded from the rule editor's tool allowlist. Scheduled rules run unattended; they must use absolute paths authored at rule-creation time, not live picker interactions.

### 6.5 FolderPickerScreen

`ModalScreen[str | None]`. Minimal directory picker — `DirectoryTree` rooted at home, selected-path label, Select / Cancel buttons. Returns an absolute path string, or `None` on cancel. Used by `RuleEditorScreen` to populate the target path field. Not a location registration screen — it does not write to the location registry.

Bindings: `ctrl+s` to confirm (silent no-op if nothing selected), `esc` to cancel.

### 6.6 LocationPickerScreen

`ModalScreen[LocationEntry | None]`. Registers a named folder in the location registry. Composes:

- **DirectoryTree** — rooted at home, for visual folder selection
- **Selected path label** — updates live as the user navigates
- **Name input** — canonical name (e.g. `Movies`)
- **Aliases input** — comma-separated aliases (e.g. `films, cinema`)

Returns a `LocationEntry` on save, or `None` on cancel. The entry is immediately persisted to the registry by the caller. In the lazy registration flow (triggered by `resolve_location` during an agent run), the `suggested_name` field is pre-filled from the unresolved name the agent passed.

Bindings: `ctrl+s` to save, `esc` to cancel.

### 6.7 LocationRegistryScreen

`ModalScreen[None]`. Full management interface for the location registry. Opens via `ctrl+p`. Renders a `DataTable` with columns: Name, Aliases, Path, Verified.

Actions via footer buttons:

| Button | Behaviour |
|---|---|
| **+ Add** | Pushes `LocationPickerScreen` with no pre-fill |
| **✎ Edit** | Pushes `LocationPickerScreen` pre-filled with selected entry. If the user renames the entry, the old record is deleted before the new one is upserted (prevents duplicates) |
| **↻ Verify** | Checks that the registered path still exists on disk; updates `last_verified` timestamp if it does |
| **✗ Remove** | Deletes the selected entry from the registry |
| **Close** | Dismisses |

Binding: `ctrl+n` to add, `esc` to close.

---

## 07 Components

### 7.1 TitleBar

Fixed top bar. Three badge slots, all right-aligned:

| Badge | Trigger | Style |
|---|---|---|
| Ollama status | Always visible | Alternates `●` / `◉` at 0.8s interval when online (pulse effect) |
| Active model | Visible when a model is configured | Blue tinted badge |
| Active rules | Visible when ≥ 1 rule exists | Amber tinted badge with `◷` prefix |

Badges use the tinted background pattern from §2.4. The pulse animation on the Ollama badge is implemented by toggling between `●` and `◉` on a timer — no CSS animation required.

### 7.2 Keybinding Chips

Used in pane headers and the footer. Background `#21262D`, 1px border `#30363D`, Accent Blue text. 10px font.

```
  ctrl+t    ctrl+n    ctrl+l    ctrl+q  
```

### 7.3 Tool Chips

Inline labels showing which tool is being or will be called. Tinted bg matching semantic colour (green for file ops). Border slightly darker than bg. 10–11px font.

```
  glob    ls    mv    rename    mkdir    rm    resolve_location  
```

Colours per tool type (all file ops share green):

- bg `#0D2B1A`, border `#238636`, text `#3FB950`

### 7.4 Buttons

Two primary button types:

- **Approve / Save** — bg `#0D2B1A`, text `#3FB950`
- **Reject / Cancel** — bg `#21262D`, text `#8B949E`; hover shifts to bg `#2B0D0D`, text `#F85149`

Monospace font, 11px, 4px border radius, 4px 12px padding.

### 7.5 Status Dots

Used in title bar badges and sidebar rule list:

- `●` / `◉` — Ollama status (alternates to create pulse)
- `●` green — rule last run OK
- `◷` blue — rule scheduled
- dim grey — rule paused

### 7.6 Pane Headers

Consistent across all panes: bg `#161B22`, 1px bottom border `#30363D`, 11px muted uppercase label left, keybinding chip right. Padding 5px 12px.

---

## 08 Keybindings

All keybindings shown in the Textual `Footer` at all times.

| Binding | Action |
|---|---|
| `ctrl+t` | Cycle Textual built-in themes |
| `ctrl+n` | New folder rule — opens rule editor screen |
| `ctrl+l` | Focus audit log sidebar |
| `ctrl+r` | Focus folder rules sidebar |
| `ctrl+o` | Change model — opens model picker screen |
| `ctrl+p` | Location registry — opens location registry screen |
| `ctrl+q` | Quit stash |
| `Enter` | Send task / approve plan |
| `Esc` | Reject plan |

---

## 09 Location Registry

### 9.1 Concept

The agent has no ability to infer or construct filesystem paths from informal names. Every path it uses must come from a tool call. The location registry is the mechanism that grounds informal folder references ("my downloads folder", "the movies folder") to real, user-confirmed absolute paths.

### 9.2 LocationEntry

Each entry has: `name` (canonical), `aliases` (list of alternate names), `path` (absolute), `added` (ISO timestamp), `last_verified` (ISO timestamp).

Resolution is exact string match after lowercasing and stripping — no fuzzy matching. Aliases extend vocabulary explicitly; the user teaches the agent their naming conventions incrementally.

### 9.3 resolve_location Tool

The `resolve_location` tool is the agent's only way to turn a name into a path. It:

1. Looks up the name (and aliases) in the registry
2. If found: verifies the path still exists on disk; returns the path or an error asking the user to re-register
3. If not found: blocks the executor thread (via `threading.Event`) and opens `LocationPickerScreen` in the TUI; the user picks and names the folder; the entry is persisted; the path is returned to the agent

The blocking wait has a 120-second timeout as a safety net against the callback never firing (e.g. screen forcibly removed by an exception). On timeout, `None` is returned and the agent receives an error string.

`resolve_location` is marked `readonly: True` in its schema, meaning it also executes during the plan (dry-run) phase so the plan shows real resolved paths rather than placeholder strings.

---

## 10 Ollama Health States

The Ollama status badge in the title bar has three states, checked on startup and polled every 30 seconds.

| State | Badge | Behaviour |
|---|---|---|
| Running + model pulled | `● ollama running` (green, pulsing) | Full operation. All features available. |
| Running + model missing | `⚠ model not found` (amber) | Warn user, offer to pull model inline in chat. |
| Ollama not running | `✗ ollama offline` (red) | Hard block on startup. Poll continues; badge updates if Ollama comes back. |

---

## 11 Agent UI Instructions

Rules the agent must follow when surfacing reasoning and actions in the chat pane.

### 11.1 ReAct Step Rendering

- Every step must appear in the chat stream immediately as it happens — do not batch
- **Thought steps** — Accent Purple left border, italic text, label `stash — thinking`
- **Action steps** — Accent Green left border, label `stash — executing`, prefix with `▶`
- **Observation steps** — Accent Amber left border, label `stash — observed`
- **Final answer** — Accent Blue left border, label `stash — done`

### 11.2 Plan Surface

- Before any execution, the full plan must render as a system message with Amber border
- Each plan step must show: step number, tool chip, plain-English description, status circle (○)
- All requested tools must be shown as chips above the plan table
- The approve bar must block input until the user acts on it
- Once approved, status circles update to ✓ as each step completes

### 11.3 Tool Calls

- Every tool call must render its name as a coloured chip, never plain text
- Tool call results must show outcome inline: e.g. `glob(...) → 11 files found`
- Unauthorised tool calls must never happen — if attempted, render a red error message immediately

### 11.4 Scheduler Messages

- When a scheduled rule fires, show a notification in the audit log sidebar immediately
- Do not interrupt an active chat session with scheduler output — queue it to the sidebar
- On next open (if TUI was closed), show a summary of what ran and the outcome

---

## 12 Architecture Decisions

Locked decisions from planning and implementation. Do not revisit without strong reason.

| Decision | Choice | Reason |
|---|---|---|
| HITL granularity | Per-task | No micro-managing mid-execution |
| Scheduled approval | Pre-signed at rule definition | Tool scope locked when rule is written |
| Scheduled execution | Fully automatic, recurrent | Set it and forget it |
| Model runtime | Ollama (local) | Self-contained, no cloud dependency |
| Model | Gemma 4 (4B or 12B) | Lightweight, built for edge compute |
| Agent pattern | Pure ReAct, hand-rolled | Full control, no framework overhead |
| Audit store | SQLite | Structured, queryable, stdlib |
| Rules store | TinyDB (`rules.json`) | JSON-shaped, easy to edit |
| Locations store | TinyDB (`locations.json`) | Separate file from rules; fully independent |
| Scheduler | APScheduler in-process | Shares state, no IPC headaches |
| TUI framework | Textual | Mature, reactive, theme support built-in |
| Default theme | Nord | Ships with Textual; dark, calm, developer-focused |
| Config | TOML | Set-once infrastructure config |
| Tool set | `ls mv mkdir rm rename glob resolve_location` | Atomic file ops + location grounding |
| Path resolution | Registry-first, picker fallback | Model never guesses or constructs paths |
| Picker cross-thread | `threading.Event` with 120s timeout | Executor thread blocks; asyncio thread signals on dismiss |
| resolve_location in rules | Excluded from rule tool allowlist | Scheduled rules run unattended; picker cannot fire without a user present |

---

*stash design spec · v0.2 · confidential*
