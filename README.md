# MAVERICK

An offline AI agent for Windows: one central agent routing plain-English
requests to specialist sub-agents. See [docs/VISION.md](docs/VISION.md) for the
design and roadmap.

## Run
```powershell
python maverick\main.py                                # interactive
python maverick\main.py copy notes.txt to D:\backup    # one-shot
python -m pytest -q                                    # tests
```

## Project layout
```
maverick/
  main.py                 entry point: REPL + one-shot; registers sub-agents
  core/
    agent_base.py         Intent, Result, SubAgent (the shape every agent follows)
    orchestrator.py       central agent: picks the sub-agent, catches errors
    safety.py             path checks: no overwrite, no system folders
  agents/
    files/
      agent.py            understands copy / move / size requests
      ops.py              actually copies / moves / measures
tests/                    pytest suite
docs/VISION.md            vision, design rules, roadmap
```

## What works today (v0.1)
- `copy <source> to <destination>`
- `move <source> to <destination>`
- `size of <path>` / `how big is <path>`

Paths with spaces go in double quotes: `move "C:\My Docs\a.txt" to "E:\New Folder"`.
