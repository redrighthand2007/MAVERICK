# MAVERICK — Progress Tracker

✅ done · 👉 next · ⬜ not started · ⏭️ skipped

---

## Stage 1: Foundation ✅

- ✅ **1.1 Vision and design rules**: [docs/VISION.md](docs/VISION.md)
- ✅ **1.2 Core shapes**: `Intent`, `Result`, `SubAgent` in `maverick/core/agent_base.py`
- ✅ **1.3 Orchestrator**: routes each request to the right sub-agent; handles `help`, `exit`, missing details, errors
- ✅ **1.4 Safety checks**: never overwrite, never touch system folders or whole drives, no folder into itself
- ✅ **1.5 Command line**: interactive mode (`python maverick\main.py`) and one-shot mode
- ✅ **1.6 Tests**: pytest suite
- ✅ **1.7 Git**: only `main` + `build`; work goes to `build`, you merge into `main`

## Stage 2: Files agent + Brain ✅

- ✅ **2.1 Copy**: files and folders; into a folder if the target is a folder
- ✅ **2.2 Move**: blocked for system folders
- ✅ **2.3 Size**: file or whole folder, readable units, counts unreadable files
- ✅ **2.4 Rename**: same folder only; blocks paths and invalid names; never overwrites
- ✅ **2.5 Brain roadmap**: [docs/BRAIN_ROADMAP.md](docs/BRAIN_ROADMAP.md)
- ✅ **2.6 Training data**: 220 labelled sentences + 26 hard cases (`maverick/brain/data/`)
- ✅ **2.7 Naive Bayes model**: written from scratch, no libraries (`naive_bayes.py`)
- ✅ **2.8 Training + evaluation**: `python -m maverick.brain.train` / `python -m maverick.brain.evaluate`
  - Test accuracy 82% (keyword rules 75%); hard cases 81% (rules 46%)
- ✅ **2.9 Brain wired in**: trusted at ≥ 60% confidence, keyword rules otherwise; requests logged to `inbox.tsv`
- ⬜ **2.10 scikit-learn version** to compare with your own model (optional)

## Stage 3: Safety net ✅

- ✅ **3.1 Confirmation prompt**: move and rename ask `(y/n)`; only y/yes goes ahead
  - Safety checks run before asking, and again after "yes"
  - Copy and size don't ask
  - New agents get it by listing operations in `risky` and writing `describe()`
- ⏭️ **3.2 Undo**: skipped for now

## Stage 4: Read-only agents (safe, can't break anything)

Every agent follows the same recipe:
**a)** `ops.py` functions → **b)** `agent.py` (keywords, `extract`) → **c)** register in `main.py` →
**d)** training sentences in `intents.tsv` + hard cases → **e)** retrain, check accuracy → **f)** tests → **g)** try live

- 👉 **4.1 Hardware agent (#33)**
  - RAM: total, used, free
  - RAM slots: how many, which are empty, type and speed
  - CPU: model, cores, current usage
  - Battery: percentage, charging or not, time left
  - Disks: each drive's total and free space
  - First time the brain has to choose between **two** agents
- ⬜ **4.2 Process tree agent (#4)**
  - List running processes (name, PID, CPU, RAM)
  - "What started X?": walk up the parent chain
  - Show children of a process
- ⬜ **4.3 File integrity agent (#28)**
  - Take a snapshot: SHA-256 of every file in a folder, saved as JSON
  - Compare later: list added, removed, changed files
- ⬜ **4.4 Connectivity agent (#20)**
  - Ping a host; check DNS lookup; trace the route
  - Diagnose step by step: adapter → gateway → DNS → internet
- ⬜ **4.5 Port viewer agent (#16, view only)**
  - Which app is using port X
  - List all listening ports with their apps
- ⬜ **4.6 File search agent (#7)**
  - By name or pattern (`*.pdf`), by date ("edited yesterday"), by size ("bigger than 1 GB")
  - Search inside text files for a word

## Stage 5: Action agents (use the 3.1 confirmation)

- ⬜ **5.1 Process hunter (#1)**: find heavy processes by CPU/RAM/name; end them after y/n
- ⬜ **5.2 CPU priority and affinity (#3)**: set priority (low/normal/high), pin to cores
- ⬜ **5.3 Disk space optimizer (#8)**: find big/old files; delete to the **Recycle Bin** only
- ⬜ **5.4 Smart archive (#12)**: zip/tar create, list, extract (Zip Slip guard), AES encryption; port of the Linux project
- ⬜ **5.5 Broken shortcut finder (#10)**: find `.lnk` files whose target is gone; remove after y/n
- ⬜ **5.6 Power agent (#34)**: switch power plans, set screen brightness
- ⬜ **5.7 Hung app reaper (#2)**: find "Not Responding" apps; end them after y/n

## Stage 6: Background agents (MAVERICK keeps running)

- ⬜ **6.1 Background mode**: MAVERICK runs in the background so agents can watch and wait
- ⬜ **6.2 Folder watcher (#11)**: e.g. move every new PDF in Downloads to Documents
- ⬜ **6.3 Background jobs (#5)**: run a command detached, Windows notification when done
- ⬜ **6.4 Task scheduler (#32)**: "every Friday at midnight" → Windows Task Scheduler
- ⬜ **6.5 Log rotator (#15)**: copy, compress, empty a big log file

## Stage 7: Admin-level and hard agents (last)

These need Administrator rights or are risky; each explains clearly when admin is required.

- ⬜ **7.1 Services (#31)**: list, start, stop, enable at boot
- ⬜ **7.2 Event logs (#35)**: read the Windows System log, explain errors (e.g. USB disconnects)
- ⬜ **7.3 Login audit (#26)**: logons outside given hours
- ⬜ **7.4 Network adapters (#17)**: Wi-Fi on/off, show IP addresses
- ⬜ **7.5 Firewall (#18)**: add/remove rules from plain English
- ⬜ **7.6 Drivers (#30)**: restart a device (e.g. webcam)
- ⬜ **7.7 Users and passwords (#23, #24)**: create local users, force password change
- ⬜ **7.8 Mount (#14)**: mount ISO / VHD files only
- ⬜ **7.9 Secure shredding (#13)**: overwrite then delete; warns that SSDs can't guarantee it
- ⬜ **7.10 Bandwidth (#19)**: which app is using the network
- ⬜ **7.11 Connections audit (#22)**: outbound connections + offline GeoIP lookup
- ⬜ **7.12 Permissions (#9)**: folder permissions from plain English
- ⬜ **7.13 Memory hogs (#29)**: spot apps whose RAM keeps growing
- ⬜ **7.14 Handle leaks (#6)**: apps holding too many handles
- ⬜ **7.15 Admin-rights audit (#25)**: who has admin on this PC (read-only)
- ❌ **#27 Linux capabilities**: dropped, no Windows equivalent

## Learning track (side chat)

- ✅ **L.1** Classification
- ✅ **L.2** Bag of words
- ⬜ **L.3** TF-IDF
- ⬜ **L.4** Train/test split and accuracy
- ⬜ **L.5** Overfitting
- ⬜ **L.6** Confidence scores
- ⬜ **L.7** Code walkthrough: `text.py` → `naive_bayes.py` → `evaluate.py` → orchestrator

## Small chores

- ⬜ GitHub "About" text still says PILOT: edit it with the ⚙️ gear on the repo page
