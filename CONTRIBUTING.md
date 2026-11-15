# Contributing

Thanks for looking. MAVERICK is a personal project, but issues and small pull requests are welcome.

## Set up and run the tests

```powershell
git clone https://github.com/redrighthand2007/MAVERICK.git
cd MAVERICK
pip install -e ".[dev,minilm]"
python -m pytest -q
```

The suite takes about 5 minutes. Every system call (processes, services, power, devices, the disk
history) is replaced by a fake, so running it never changes your PC.

## How the code is shaped

- `maverick/agents/<name>/agent.py` **understands** a request: `parse(text)` (keyword rules) and
  `extract(operation, text)` (pulls out the details).
- `maverick/agents/<name>/ops.py` **does** it, after the safety checks in `maverick/core/safety.py`.
- `maverick/brain/` holds every model; `maverick/llm/` holds the local LLM and the MiniLM export.

Keep understanding and doing separate: `agent.py` never touches the disk, and `ops.py` never reads
the user's sentence.

## Adding an agent

1. Write `ops.py`: plain functions that return a `Result`.
2. Write `agent.py`: a `SubAgent` with keywords, `extract()` and, for anything that changes something,
   the operation in `risky` plus a `describe()` for the y/n question.
3. Register it in `build()` in `maverick/main.py` (order matters for keyword rules; see the comments
   there).
4. Add at least 30 example sentences per operation to `maverick/brain/data/intents.tsv`, and a few
   tricky ones to `hard_cases.tsv`.
5. Retrain and compare: `python -m maverick.brain.train`, `python -m maverick.brain.multi`,
   `python -m maverick.brain.evaluate`. Accuracy must not drop below the floors in
   `tests/test_brain.py`.
6. Add tests with fakes for every system call.

## Rules that are not negotiable

- Never overwrite, never touch system folders or whole drives, delete only to the Recycle Bin.
- Anything that changes or removes something asks y/n first.
- A model, the slot tagger or the LLM may only *propose* an action; safety checks always run.
- Nothing is sent over the internet.
