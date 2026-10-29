# MAVERICK — Progress Tracker

> **Open this first whenever you resume.** It says what is done, what is
> happening now, and what comes next. Updated after every finished step.

**Last updated:** 2026-10-29
**Branches:** `main` and `build` are in sync (both at `7161cf0`)
**Tests:** 34 passing (`python -m pytest -q`)

## 👉 You are here

**Next step: Stage 3.1, the confirmation prompt** ("Are you sure? y/n" before risky actions).
Not started yet.

---

## Stage 1: Foundation ✅

- [x] Vision and design rules ([docs/VISION.md](docs/VISION.md))
- [x] Core: orchestrator, sub-agent shape (`Intent` / `Result` / `SubAgent`), safety checks
- [x] REPL (`python maverick\main.py`) and one-shot command mode
- [x] Git setup: only `main` + `build`; Claude commits to `build`, you merge to `main`

## Stage 2: Files agent + Brain ✅

- [x] Files agent: **copy, move, size** (tested on real files)
- [x] Files agent: **rename** (blocks paths, never overwrites)
- [x] Brain roadmap written ([docs/BRAIN_ROADMAP.md](docs/BRAIN_ROADMAP.md))
- [x] Brain built: own Naive Bayes model, 220 training sentences + 26 hard cases
  - Test accuracy **82%** (keyword rules: 75%); hard cases **81%** (rules: 46%)
  - Used when ≥ 60% confident, otherwise keyword rules decide
  - Train once per PC: `python -m maverick.brain.train`
- [ ] Brain Phase 4: scikit-learn version to compare (optional, later)

## Stage 3: Safety net 🔜

- [ ] **3.1 Confirmation prompt**: ask y/n before move/rename and every future risky action
- [ ] **3.2 Undo**: reverse the last move or rename

## Stage 4: Read-only agents (safe, can't break anything)

From the 35-agent plan, Windows versions. Each new agent also adds its sentences to the brain's training data.

- [ ] #33 Hardware: RAM, CPU, battery, empty RAM slots
- [ ] #4 Process tree: what started this process
- [ ] #28 File integrity: hash a folder, detect changes later
- [ ] #20 Connectivity diagnostics: ping, DNS, route
- [ ] #16 Port sentinel (view only): which app uses port X
- [ ] #7 File search: by name, date, size, content

## Stage 5: Action agents (need confirmation from 3.1)

- [ ] #1 Process hunter: find and end heavy processes
- [ ] #3 CPU priority and affinity
- [ ] #8 Disk space optimizer: delete to the Recycle Bin only
- [ ] #12 Smart archive: port of the Linux project
- [ ] #10 Broken shortcut finder
- [ ] #34 Power plans and brightness
- [ ] #2 Hung app reaper (Windows version of "zombie reaper")

## Stage 6: Background agents (MAVERICK keeps running)

- [ ] #11 Folder watcher: auto-move downloads
- [ ] #5 Background jobs with a notification when done
- [ ] #32 Task Scheduler (Windows version of cron)
- [ ] #15 Log rotator

## Stage 7: Admin-level and hard agents (last)

- [ ] #31 Services · #35 Event logs · #26 Login audit · #17 Network adapters
- [ ] #18 Firewall · #30 Drivers · #23/#24 Users and passwords · #14 Mount ISO
- [ ] #13 Secure shredding · #19 Bandwidth · #22 Connections audit · #9 Permissions
- [ ] #29 Memory hogs · #6 Handle leaks · #25 Admin-rights audit
- Dropped: #27 Linux capabilities (no Windows equivalent)

## Learning track (side chat)

- [x] Phase 1: classification, bag of words
- [ ] Phase 1: TF-IDF, train/test split, accuracy, overfitting, confidence
- [ ] Walk through the brain code: `text.py` → `naive_bayes.py` → `evaluate.py` → orchestrator

## Small chores

- [ ] GitHub repo "About" text still says PILOT. Edit it with the ⚙️ gear on the repo page.

---

## Log

| Date | What happened |
|---|---|
| 2026-10-21 | Project framed; core + files agent (copy, move, size); repo set up with `main` + `build` |
| 2026-10-21 | Rename added and tested on real files |
| 2026-10-23 | Brain roadmap written; brain built and wired in (82% vs 75%) |
| 2026-10-29 | `build` merged into `main` (PR #2), branches synced; this tracker created |
