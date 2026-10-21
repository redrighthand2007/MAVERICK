# MAVERICK — Vision & Roadmap

## What it is
An **offline AI agent for Windows**. You type a request in plain English; a
**central agent** (the orchestrator) decides which **sub-agent** owns that kind
of task, and the sub-agent runs it safely with Python — no shell strings, no
internet, no cloud API keys.

Inspired by the Linux *Smart Archive Agent* (`E:\VIT-OS-SMART-ARCHIVE-AGENT`),
which was one standalone agent. MAVERICK is the same idea scaled out: many
specialist agents under one coordinator.

## How a request flows

```
You type: copy notes.txt to D:\backup
        │
        ▼
 main.py ── REPL / one-shot command
        │
        ▼
 Orchestrator (core/orchestrator.py)
   asks each registered sub-agent: "can you parse this?"
        │  first one that says yes wins
        ▼
 FileAgent (agents/files/agent.py)
   parse  → Intent(operation="copy", args={source, destination})
   handle → ops.copy(...)  ── safety checks first (core/safety.py)
        │
        ▼
 Result(success, message, data) → printed back to you
```

## Key design rules
1. **Every sub-agent has the same shape** (`core/agent_base.py`): a `name`,
   a `parse(text)` that returns an `Intent` or `None`, and a `handle(intent)`
   that returns a `Result`. Adding a new agent = one new folder + one line of
   registration.
2. **Understanding is separate from doing.** `parse` only reads text; `ops`
   only touch the disk. This is what lets us swap in a smarter "brain" later
   without rewriting any operations.
3. **Safe by default.** Never overwrite, never touch system folders, never run
   shell commands, never permanently delete.

## Open decision: the "brain"
How requests get understood is **on hold**. Today each agent uses simple
keyword rules. Options for later (all offline):
- keep rules only,
- rules first + a small local LLM (via Ollama) as fallback,
- local LLM for everything.

Because of rule 2, this is a later swap, not a rewrite.

## Roadmap
| Stage | What | Status |
| --- | --- | --- |
| v0.1 | Core skeleton + File agent: **copy, move, size** | in progress |
| v0.2 | File agent: rename, list folder, find files | idea |
| v0.3 | Second sub-agent (archive port from Linux project, or system monitor) | idea |
| later | Decide the brain; confirmations for risky actions; GUI / hotkey | idea |
