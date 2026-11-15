# Changelog

## Unreleased

- Demo GIF in the README, rendered from MAVERICK's real answers to real requests
- `CHANGELOG.md` and `CONTRIBUTING.md`
- CI runs once per pull request and after merging, and skips docs-only changes

## 1.0.0 (2026-11-07)

First complete version.

**Agents (14 agents, 46 operations)**
- Files: copy, move, rename, size; never overwrites
- Search: by name, kind, date, size or text; learned result ranking; k-means grouping
- Archive: zip / tar / tar.gz / tar.bz2 / tar.xz, AES-256 passwords, list, extract with a Zip Slip guard
- Cleanup: temp and junk scan, Recycle Bin deletes, "free up N GB" planned as a knapsack problem
- Process: top programs, process tree, end, frozen apps, memory and handle leaks, anomaly detection
- Hardware: RAM, slots, CPU, battery, disks, disk-full forecast
- Power: Windows 11 power modes, laptop brightness
- Services, Network adapters, Devices, Accounts (admin audit)
- Background mode: folder watcher, log rotator, saved jobs, maintenance planning (constraint solving)

**Understanding requests**
- Brain: MiniLM sentence encoder (ONNX) + logistic regression, 91.6% on 5-fold cross-validation;
  falls back to an ensemble of from-scratch NumPy models (84.5%)
- Slot tagger for file names (93.0%), multi-action splitter (95.8%)
- Local LLM fallback: Llama 3.2 3B via Ollama, tool calling with few-shot prompting (95.2%),
  multi-step agent loop; every proposed value is checked against the request
- Active learning: `python -m maverick.brain.review`

**Safety**
- y/n confirmation for risky actions; safety checks before and after "yes"
- Protected system folders, whole drives and core Windows services
- Deletes go to the Recycle Bin only; passwords are typed at a hidden prompt and never logged

**Project**
- 491 tests with all system calls faked; CI on Windows, Python 3.12 + 3.14
- `pip install -e .` gives a `maverick` command; MIT license
