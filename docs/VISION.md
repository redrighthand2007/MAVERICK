# MAVERICK: Vision and Design

## What it is

An **offline AI assistant for Windows**. You type a request in plain English. A **central agent** (the
orchestrator) works out which **specialist agent** owns that kind of task, and that agent does it
safely, in Python. No internet, no cloud, no API keys: every model runs on your own PC.

MAVERICK grew out of a single-purpose Linux course project, a smart archive agent. It takes that idea
further: many specialist agents under one coordinator, with a brain that learns.

## How a request flows

```text
You type: "clone notes.txt into D:\backup and zip it"
   │
   ▼
main.py ── chat, one-shot, or --background
   │
   ▼
Splitter (brain/multi.py) ── one action or several? → "clone notes.txt into D:\backup" | "zip it"
   │
   ▼  for each piece:
Brain (brain/minilm.py) ── which agent.operation, and how sure? → files.copy, 0.98
   │   unsure → keyword rules → still nothing → local LLM (llm/loop.py), if Ollama is running
   ▼
Orchestrator (core/orchestrator.py) ── picks the agent; checks EVERY piece is understood before running any
   │
   ▼
FilesAgent (agents/files/agent.py)
   extract → Intent(operation="copy", args={source, destination})   (slot tagger finds the names)
   handle  → ops.copy(...) ── safety checks first (core/safety.py)
   │          risky? → y/n prompt, safety checks again after "yes"
   ▼
Result(success, message, data) → printed; "it" in the next step means this result
```

## Design rules

1. **Every agent has the same shape** (`core/agent_base.py`):
   - `parse(text)`: keyword rules, used when the brain is unsure
   - `extract(operation, text)`: pulls out the details
   - `handle(intent)`: returns a `Result`
   - `risky`, plus `describe()` for the y/n question

   Adding an agent means one new folder plus one line in `main.py`.
2. **Understanding is separate from doing.** `agent.py` only reads text; `ops.py` only acts. That's
   why the brain could be swapped seven times (Naive Bayes → ... → MiniLM) without touching any
   operation.
3. **AI decides *what* you asked for, never *whether it's allowed*.** The brain, the slot tagger and
   the LLM only propose. Safety checks and the y/n prompt always run, whoever proposed the action.
4. **Safe by default.**
   - Never overwrite.
   - Never touch system folders or whole drives.
   - Delete only to the Recycle Bin.
   - Never stop core Windows services.
   - System commands use fixed argument lists, and user-supplied names are quoted.
   - Passwords are typed at a hidden prompt and never logged.
5. **Measured, not guessed.** A new model replaces the old one only if it scores higher on the same
   5-fold cross-validation, and failures are written down too ([RESULTS.md](RESULTS.md)).
6. **Testable without side effects.** Every system call is behind a small function that tests replace
   with a fake. The suite never kills a process or changes a setting.

## What was built

| Stage | What |
|---|---|
| 1 | Foundation: core shapes, orchestrator, safety checks, command line, tests |
| 2 | Files agent (copy, move, size, rename) and the first brain (Naive Bayes from scratch) |
| 3 | Safety net: y/n confirmation for risky actions |
| 4 | Read-only agents: hardware, process tree, file search |
| 5 | Action agents: process hunter, disk clean-up, archives, power, frozen apps |
| 6 | Background agents: background mode, folder watcher, log rotator |
| 7 | Admin-level agents: services, network adapters, devices, memory and handle leaks, admin audit |
| 8 | AI methods: 30 techniques, from TF-IDF to a shipped transformer encoder and a local LLM agent loop |

Step-by-step detail: [PROGRESS.md](../PROGRESS.md).

## Possible next steps

- A small window (GUI) or a global hotkey instead of the terminal
- A task scheduler, so the maintenance plan from `jobs.plan` actually runs at the planned times
- MiniLM-based file search ("my tax papers" → `ITR_2025.pdf`)
- Learning search ranking from the results you actually open
