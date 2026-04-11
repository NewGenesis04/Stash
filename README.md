# Stash

I built this because Google announced Gemma 4 and my brain wouldn't stop.

Not because of the benchmarks — because of what the benchmarks *meant*. A model that capable, running on a laptop, with no cloud, no API key, no monthly bill quietly climbing in the background. That's not a product announcement. That's a shift. And once you see it, you start looking at your machine differently.

I looked at my downloads folder.

I'm not going to describe what I saw. You know what you saw when you looked at yours.

---

## The idea

Files are not a solved problem. We have folders, and we have the vague intention to organise them someday. Someday lives in the downloads folder alongside three versions of the same PDF, a zip file from 2022, and a screenshot with a name like `Screen Shot 2024-08-11 at 14.32.07.png`.

What if something just... handled it? Quietly. On a schedule. Without asking.

That's Stash. You describe what you want done — in plain English — point it at a folder, and it figures out the rest. Move these. Rename those. Create this structure. It runs locally, thinks for itself, and never touches anything without showing you the plan first.

I also realised the downloads folder wasn't the only offender. My documents folder. My movies directory — file names so inconsistent that my media player's auto-playlist feature just gives up. Stash handles those too. Any folder, any instruction, any cadence.

---

## How it thinks

Stash uses a ReAct loop — Reason, Act, Observe, repeat. The agent doesn't just execute a script. It thinks through the task, picks a tool, sees what happened, and decides what to do next. It's the difference between a macro and a mind.

Before anything touches your filesystem, Stash shows you the full plan. Every step, every tool call, every file it intends to move. You approve it. Then it runs. This isn't a safety theatre checkbox — it's a hard boundary. A tool that wasn't in the approved list cannot be called. Not "probably won't". Cannot.

---

## How it's built

A few decisions I'm proud of:

**The agent remembers.** Conversation history persists across runs, so preferences you express once — how you like files named, folder structures you prefer, things you've told it to leave alone — carry forward. You talk to it in plain English, and it builds up a picture of how you like things done.

**The tool set is explicit and minimal.** `ls`, `glob`, `mv`, `rename`, `mkdir`, `rm`. That's it. The agent can only use tools the rule permits. This isn't minimalism for its own sake — it's the thing that makes it safe to run unsupervised.

**The TUI is the message bus.** Rather than a separate pub/sub layer, everything routes through the Textual app via its native message-passing. The scheduler, the agent callbacks, the health checks — they all speak to one hub. Simple to reason about, easy to extend.

**Folder rules are how you delegate trust.** A rule is a standing contract — a folder, a plain-English instruction, a set of permitted tools, and a schedule. Stash runs it on the interval you set, every time, without prompting. Want your downloads sorted every six hours? Your media folder renamed for clean playlist ordering every night? Write it once, set the cadence, and forget the folder exists. Each rule carries its own tool allowlist too — a rule that organises can't delete, a rule that renames can't move things out of the folder. The scope is narrow by design, because unsupervised access should always be earned, not assumed.

**Model choice is yours.** Gemma 4 was the spark, but Stash runs on any model you have pulled in Ollama. First launch, it asks you to pick. After that, it remembers. Change your mind? One line in `config.toml`.

---

## The stack

```
┌─────────────────────────────────────────────────────────────┐
│                        Textual TUI                          │
│  ┌─ Chat ────────┐  ┌─ Plan Approval ─┐  ┌─ Sidebar ─────┐ │
│  │ task input    │  │ step preview    │  │ rules list    │ │
│  │ ReAct stream  │  │ approve/reject  │  │ audit log     │ │
│  └───────────────┘  └─────────────────┘  └───────────────┘ │
└────────────────────────────┬────────────────────────────────┘
                             │ post_message / call_from_thread
              ┌──────────────┼──────────────┐
              │              │              │
       ┌──────▼──────┐  ┌────▼────┐  ┌─────▼──────┐
       │    Agent    │  │Scheduler│  │   Health   │
       │  ReAct loop │  │  jobs   │  │   check    │
       │  + callbacks│  │         │  │            │
       └──────┬──────┘  └────┬────┘  └─────┬──────┘
              │              │              │
       ┌──────▼──────┐  ┌────▼────┐  ┌─────▼──────┐
       │    Tools    │  │ TinyDB  │  │   Ollama   │
       │ ls mv rm .. │  │  rules  │  │ (any model)│
       └─────────────┘  └─────────┘  └────────────┘
                              │
                        ┌─────▼──────┐
                        │   SQLite   │
                        │ audit log  │
                        └────────────┘
```

- **Ollama** — local inference, any model you like
- **APScheduler** — runs your rules on the interval you set
- **Textual** — the TUI, and the nervous system
- **TinyDB** — lightweight rule storage, human-readable JSON
- **SQLite** — audit log, task history, conversation context
- **Pydantic** — data shapes, all the way down

No cloud dependencies. Nothing phoning home. Your files stay yours.

---

## A note on trust

Stash is built to earn it gradually. It won't run a rule without your approval the first time. It logs every action. It refuses to operate outside the tool set you gave it. The approval step isn't a formality — it's the whole point.

The goal is a tool you forget is running, because it just does what you asked and nothing else.

If that sounds like something your filesystem deserves, you're in the right place.
