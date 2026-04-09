# stash — UI Design Specification
**v0.1 · Local-first File Management Agent**

> A local-first, agent-powered file management TUI. Self-contained, auditable, and built around human-in-the-loop control. Powered by Gemma 4 via Ollama. Your files never leave your machine.

---

## 01 Design Philosophy

stash is a developer tool, not a consumer app. The aesthetic should feel like a terminal that went to design school — dark, monospaced, structured, and calm. Every element earns its place. Nothing decorative.

- Dark background at all times — no light mode default
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
| 🟫 | Panel | `#161B22` | Pane headers, title bar, footer bar |
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
2. **Main Layout** — two-column: chat pane (flex: 1) + sidebar (fixed 240px)
3. **Approve Bar** — appears above input when a plan is pending, disappears after
4. **Status Bar** — always visible at bottom, keybindings + idle/active state

```
┌─────────────────────────────────────────────────────┐
│  Title Bar — stash  ● ollama running  gemma4:4b     │
├────────────────────────────────────┬────────────────┤
│                                    │  Folder Rules  │
│         Chat / Task Pane           ├────────────────┤
│           (flex: 1)                │  Audit Log     │
│                                    │  (240px fixed) │
├────────────────────────────────────┴────────────────┤
│  Approve Bar (conditional)                          │
├─────────────────────────────────────────────────────┤
│  Status Bar — ctrl+t  ctrl+n  ctrl+l  ctrl+q       │
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

### 4.4 Sidebar (right, 240px fixed)

Split into two sections separated by a border:

- **Folder Rules** (top) — each rule shows name, interval + tools, status dot
  - ● green = last run OK
  - ◷ blue = scheduled, next run countdown
  - dim / grey = paused
- **Audit Log** (bottom, scrollable) — each entry: timestamp, tool chip, path/result

Sidebar pane headers follow the same pattern as the chat pane header — muted uppercase label + keybinding chip right-aligned.

---

## 05 Components

### 5.1 Keybinding Chips

Used in pane headers and the status bar. Background `#21262D`, 1px border `#30363D`, Accent Blue text. 3px border radius. 10px font.

```
  ctrl+t    ctrl+n    ctrl+l    ctrl+q  
```

### 5.2 Tool Chips

Inline labels showing which tool is being or will be called. Tinted bg matching semantic colour (green for file ops). Border slightly darker than bg. 4px border radius. 10–11px font.

```
  glob    ls    mv    rename    mkdir    rm  
```

Colours per tool type (all file ops share green):

- bg `#0D2B1A`, border `#238636`, text `#3FB950`

### 5.3 Buttons

Two button types only:

- **Approve** — bg `#0D2B1A`, text `#3FB950`, border `#238636`
- **Reject** — bg `#2B0D0D`, text `#F85149`, border `#6E2B2B`

Monospace font, 11px, 4px border radius, 4px 12px padding.

### 5.4 Status Dots

6px circle, filled with accent colour. For Ollama online, the dot pulses (CSS animation) to show it is live. Used in title bar badges and sidebar rule list.

### 5.5 Pane Headers

Consistent across all panes: bg `#161B22`, 1px bottom border `#30363D`, 11px muted uppercase label left, keybinding chip right. Padding 5px 12px.

---

## 06 Keybindings

All keybindings are shown in the status bar at all times. `ctrl+t` is listed first — it is intentional, front-and-centre UX.

| Binding | Action |
|---|---|
| `ctrl+t` | Cycle Textual built-in themes |
| `ctrl+n` | New folder rule — opens rule editor screen |
| `ctrl+l` | Focus audit log sidebar |
| `ctrl+r` | Focus folder rules sidebar |
| `ctrl+q` | Quit stash |
| `Enter` | Send task / approve plan |
| `Esc` | Reject plan |

---

## 07 Ollama Health States

The Ollama status badge in the title bar has three states, checked on startup and visible at all times.

| State | Badge | Behaviour |
|---|---|---|
| Running + model pulled | `● ollama running` (green) | Full operation. All features available. |
| Running + model missing | `⚠ model not found` (amber) | Warn user, offer to pull model inline in chat. |
| Ollama not running | `✗ ollama offline` (red) | Hard block. Show message, no agent features until resolved. |

---

## 08 Agent UI Instructions

Rules the agent must follow when surfacing reasoning and actions in the chat pane.

### 8.1 ReAct Step Rendering

- Every step must appear in the chat stream immediately as it happens — do not batch
- **Thought steps** — Accent Purple left border, italic text, label `stash — thinking`
- **Action steps** — Accent Green left border, label `stash — executing`, prefix with `▶`
- **Observation steps** — Accent Amber left border, label `stash — observed`
- **Final answer** — Accent Blue left border, label `stash — done`

### 8.2 Plan Surface

- Before any execution, the full plan must render as a system message with Amber border
- Each plan step must show: step number, tool chip, plain-English description, status circle (○)
- All requested tools must be shown as chips above the plan table
- The approve bar must block input until the user acts on it
- Once approved, status circles update to ✓ as each step completes

### 8.3 Tool Calls

- Every tool call must render its name as a coloured chip, never plain text
- Tool call results must show outcome inline: e.g. `glob(...) → 11 files found`
- Unauthorised tool calls must never happen — if attempted, render a red error message immediately

### 8.4 Scheduler Messages

- When a scheduled rule fires, show a notification in the audit log sidebar immediately
- Do not interrupt an active chat session with scheduler output — queue it to the sidebar
- On next open (if TUI was closed), show a summary of what ran and the outcome

---

## 09 Architecture Decisions

Locked decisions from planning phase. Do not revisit without strong reason.

| Decision | Choice | Reason |
|---|---|---|
| HITL granularity | Per-task | No micro-managing mid-execution |
| Scheduled approval | Pre-signed at rule definition | Tool scope locked when rule is written |
| Scheduled execution | Fully automatic, recurrent | Set it and forget it |
| Model runtime | Ollama (local) | Self-contained, no cloud dependency |
| Model | Gemma 4 (4B or 12B) | Lightweight, built for edge compute |
| Agent pattern | Pure ReAct, hand-rolled | Full control, no framework overhead |
| Audit store | SQLite | Structured, queryable, stdlib |
| Rules store | TinyDB | JSON-shaped, easy to edit |
| Scheduler | APScheduler in-process | Shares state, no IPC headaches |
| TUI framework | Textual | Mature, reactive, theme support built-in |
| Config | TOML | Set-once infrastructure config |
| V1 tool set | `ls mv mkdir rm rename glob` | Atomic file ops, nothing more |

---

*stash design spec · v0.1 · confidential*
