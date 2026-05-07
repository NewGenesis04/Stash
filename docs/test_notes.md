# Stash — Early Test Setup

## Ollama

Make sure the API is running before launching Stash:

```
ollama serve
```

Pull a model if you haven't already. Tool calling works best in the 4–7B range — recommended:

```
ollama pull qwen2.5:7b
```

Other solid options: `gemma3:4b`, `mistral:7b`, `llama3.2:3b`.

---

## Running Stash

From the project directory:

```
uv run stash
```

To install it globally so you can run `stash` from anywhere:

```
uv tool install .
```

---

## Configuration (optional — defaults are fine to start)

Config lives at `~/.stash/config.toml`. You don't need to touch this before first launch, but if you want to tune things:

```toml
[ollama]
model = "qwen2.5:7b"            # must match exactly what `ollama list` shows
host = "http://localhost:11434"  # only change if Ollama isn't on the default port
max_steps = 20                   # max tool-call iterations per task
history_limit = 20               # conversation turns fed back into context
context_window = 32768           # see note below

[data]
dir = "~/.stash"                 # DB, rules, preferences, and location registry
```

**`context_window` note:** Ollama often allocates less than a model's training maximum. On startup, look for this line in Ollama's output:

```
llama_context: n_ctx_seq = XXXX
```

Set `context_window` to that number. If you don't set it, the pressure warning is uncalibrated — not a showstopper, just less useful.

---

## First Launch

The first screen is a model picker. **Select your model before doing anything else** — skipping without selecting will cause an immediate error. The picker lists everything currently available in Ollama.

---

## Keybindings

**Main interface:**

| Key | Action |
|-----|--------|
| `enter` | Submit a task |
| `ctrl+k` | Location registry |
| `ctrl+n` | New automation rule |
| `ctrl+r` | Focus the rules panel |
| `ctrl+l` | Focus the audit log |
| `ctrl+o` | Change model |
| `ctrl+t` | Toggle theme |
| `ctrl+q` | Quit |

`ctrl+k` is how the agent learns your filesystem — register folder aliases here before running tasks that reference folders by name, otherwise it will prompt you to pick them at runtime.

**Inside any screen:**

| Key | Action |
|-----|--------|
| `enter` | Approve plan |
| `esc` | Reject plan / close screen |
| `ctrl+s` | Save (location picker, rule editor) |

---

## Things to Test

**Basic tasks**
- `"What's in my downloads folder?"` — tests `resolve_location` → `ls` chain
- `"Move all PDFs from Downloads to Documents"` — tests `glob` + `mv` + plan approval
- `"Find all .log files under [some path]"` — tests `glob` with an explicit path
- `"Rename report.pdf to report-final.pdf in my documents"` — tests `rename`
- `"Create a folder called Archive inside Downloads"` — tests `mkdir`

**Location registry**
- Register a couple of aliases via `ctrl+k`, then ask the agent to act on them by name — verify it resolves correctly without prompting
- Ask for a folder you haven't registered — the folder picker should appear during the execute phase (not before the plan is shown)

**Plan approval**
- Any file-moving task — verify the plan appears with the proposed steps listed, and that nothing happens on disk until you approve

**Conversation memory**
- Multi-turn: `"What's in my projects folder?"` then `"Move the zip files there to Archives"` — the agent should use the prior listing without calling `ls` again

**Automation rules** (`ctrl+n`)
- Create a simple rule and verify it appears in the sidebar with correct status
- If you have patience, let it trigger once and check the audit log

**Guardrails**
- Off-topic: `"Write me a Python script"` — should get a one-line refusal
- Ambiguous: `"Sort my downloads"` — should ask a clarifying question, not guess
- Deletion: `"Delete everything in my temp folder"` — should state exactly what will be deleted before doing it
