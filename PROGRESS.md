# MAVERICK — Progress Tracker

Built: ✅ done · 👉 next · ⬜ not started · ⏭️ skipped
Learned: 🧠 I understand it · 📕 not learned yet

Each step shows both: built status first, then learned status. Only mark 🧠 when you can explain it in your own words.

---

## Start here: basics (learn before Stage 1) · learned 0/5

No prior knowledge assumed. These explain the ideas every stage below is built on.

- 📕 **B.1 What an "agent" is**: a program that takes a request and does one job; MAVERICK's agents are plain Python, not ChatGPT
- 📕 **B.2 Multi-agent design**: one orchestrator (the manager) hands each request to the right sub-agent (the worker)
- 📕 **B.3 One request, start to finish**: you type → brain guesses the intent → orchestrator picks the agent → agent pulls out the details → safety checks → action → result
- 📕 **B.4 Where the "AI" actually is**: only the brain, a small model that learns from example sentences; the rest is normal code
- 📕 **B.5 Python you need**: functions, classes, modules and imports, running tests with pytest

## Stage 1: Foundation ✅ · learned 0/7

- ✅ 📕 **1.1 Vision and design rules**: [docs/VISION.md](docs/VISION.md)
- ✅ 📕 **1.2 Core shapes**: `Intent`, `Result`, `SubAgent` in `maverick/core/agent_base.py`
- ✅ 📕 **1.3 Orchestrator**: routes each request to the right sub-agent; handles `help`, `exit`, missing details, errors
- ✅ 📕 **1.4 Safety checks**: never overwrite, never touch system folders or whole drives, no folder into itself
- ✅ 📕 **1.5 Command line**: interactive mode (`python maverick\main.py`) and one-shot mode
- ✅ 📕 **1.6 Tests**: pytest suite
- ✅ 📕 **1.7 Git**: only `main` + `build`; work goes to `build`, you merge into `main`

## Stage 2: Files agent + Brain ✅ · learned 0/10

- ✅ 📕 **2.1 Copy**: files and folders; into a folder if the target is a folder
- ✅ 📕 **2.2 Move**: blocked for system folders
- ✅ 📕 **2.3 Size**: file or whole folder, readable units, counts unreadable files
- ✅ 📕 **2.4 Rename**: same folder only; blocks paths and invalid names; never overwrites
- ✅ 📕 **2.5 Brain roadmap**: [docs/BRAIN_ROADMAP.md](docs/BRAIN_ROADMAP.md)
- ✅ 📕 **2.6 Training data**: 220 labelled sentences + 26 hard cases (`maverick/brain/data/`)
- ✅ 📕 **2.7 Naive Bayes model**: written from scratch, no libraries (`naive_bayes.py`)
- ✅ 📕 **2.8 Training + evaluation**: `python -m maverick.brain.train` / `python -m maverick.brain.evaluate`
  - Test accuracy 82% (keyword rules 75%); hard cases 81% (rules 46%)
- ✅ 📕 **2.9 Brain wired in**: trusted at ≥ 60% confidence, keyword rules otherwise; requests logged to `inbox.tsv`
- ⬜ 📕 **2.10 scikit-learn version**: moved into Stage 8 as 8.2–8.4

## Stage 3: Safety net ✅ · learned 0/2

- ✅ 📕 **3.1 Confirmation prompt**: move and rename ask `(y/n)`; only y/yes goes ahead
  - Safety checks run before asking, and again after "yes"
  - Copy and size don't ask
  - New agents get it by listing operations in `risky` and writing `describe()`
- ⏭️ 📕 **3.2 Undo**: skipped for now

## Stage 4: Read-only agents (safe, can't break anything) ✅ · learned 0/6

Every agent follows the same recipe:
**a)** `ops.py` functions → **b)** `agent.py` (keywords, `extract`) → **c)** register in `main.py` →
**d)** training sentences in `intents.tsv` + hard cases → **e)** retrain, check accuracy → **f)** tests → **g)** try live

- ✅ 📕 **4.1 Hardware agent (#33)**: `maverick/agents/hardware/` (uses `psutil` + Windows CIM)
  - RAM: total, used, free
  - RAM slots: how many, which are empty, type and speed, max supported
  - CPU: model, cores / threads, current usage
  - Battery: percentage, charging or not, time left
  - Disks: each drive's total and free space, or one drive (`space left on D:`)
  - Brain now chooses between **two** agents and 10 labels (414 sentences, 42 hard cases)
  - Brain alone 76% on unseen sentences; **as MAVERICK runs (brain + rules) 87%**; keyword rules alone 79%
  - `evaluate.py` now reports the combined score; brain-alone test floor lowered 0.80 → 0.75, new combined floors 0.85 / 0.70
  - Fixed: one-shot mode now accepts the whole request as one quoted sentence
- ✅ 📕 **4.2 Process tree agent (#4)**: `maverick/agents/process/`
  - Biggest programs by RAM or CPU, with copies grouped (`chrome.exe x18`)
  - "What started X?": walks up the parent chain, notices closed parents and reused PIDs, says it in plain words
  - "What did X start?": direct and total child programs
  - Find by name (`chrome`, `code.exe`) or PID
- ⏭️ 📕 **4.3 File integrity agent (#28)**: skipped for now
  - Take a snapshot: SHA-256 of every file in a folder, saved as JSON
  - Compare later: list added, removed, changed files
- ⏭️ 📕 **4.4 Connectivity agent (#20)**: skipped for now
  - Ping a host; check DNS lookup; trace the route
  - Diagnose step by step: adapter → gateway → DNS → internet
- ⏭️ 📕 **4.5 Port viewer agent (#16, view only)**: skipped for now
  - Which app is using port X
  - List all listening ports with their apps
- ✅ 📕 **4.6 File search agent (#7)**: `maverick/agents/search/`
  - By name, kind (`pdf`, `videos`, `photos`, `python`, `*.mkv`), date (`today`, `yesterday`, `this week`, `last 3 days`, `older than 2 years`), size (`bigger than 1 gb`, `big files`)
  - Inside text files, showing the matching line
  - Where: a typed path, `e drive`, or `in downloads / documents / desktop`; default is your user folder
  - Skips system and junk folders (Windows, AppData, node_modules, .git); stops after 20 s on huge drives
- Brain after Stage 4: 15 labels, 564 sentences, 51 hard cases
  - Brain alone 66%; **as MAVERICK runs 82%** (keyword rules alone 77%); hard cases 73% (rules 49%)
  - Naive Bayes has hit its limit (ignores word order: "what started chrome" vs "what did chrome start"); Stage 8 brains should lift this
  - Test floors now: brain alone 0.60, as MAVERICK runs 0.80 / 0.70

## Stage 5: Action agents (use the 3.1 confirmation) · learned 0/5

- ✅ 📕 **5.1 Process hunter (#1)**: `end` command in `maverick/agents/process/`
  - `kill chrome`, `close notepad`, `end pid 1234`, `kill whatever is using the most ram / cpu`
  - Asks y/n first, showing how many copies and how much RAM they use
  - Closes politely, then forces any copy still running after 3 s
  - Refuses Windows' own processes (svchost, csrss, explorer, ...) and MAVERICK itself
  - Brain: 16 labels; alone 73%, as MAVERICK runs 86% test / 69% hard (hard floor lowered 0.70 → 0.65)
- ⏭️ 📕 **5.2 CPU priority and affinity (#3)**: skipped for now
- ✅ 📕 **5.3 Disk space optimizer (#8)**: `maverick/agents/cleanup/`
  - `free up space (on e drive)`: temp files older than a day, files over 500 MB, downloads untouched for 90+ days
  - `clear temp files`, `delete D:\old.zip`: always to the **Recycle Bin** (restorable), after y/n
  - Refuses your user folder and its main folders, Windows / Program Files, and whole drives; never empties the bin
  - Brain: 18 labels; alone 75%, as MAVERICK runs 85% test / 62% hard (hard floors lowered to 0.70 / 0.60)
- ✅ 📕 **5.4 Smart archive (#12)**: `maverick/agents/archive/`, ported from VIT-OS-SMART-ARCHIVE-AGENT
  - `zip D:\work`, `compress D:\logs as tar.gz`, `zip D:\work into E:\backups`: .zip, .tar, .tar.gz, .tar.bz2, .tar.xz
  - `zip D:\work with a password`: AES-256 (`pyzipper`, now in requirements.txt); password typed at a hidden prompt, twice
  - `what's inside backup.zip`: list without extracting; `unzip backup.zip to D:\restore`: extract
  - Zip Slip guard (`..\..\` names are refused before anything is written); tar links/devices refused
  - Never overwrites; a wrong password writes nothing
  - Brain: 21 labels; alone 74%, as MAVERICK runs ~80% across splits (75% on seed 42, floor 0.80 → 0.75)
- ⏭️ 📕 **5.5 Broken shortcut finder (#10)**: skipped for now
- ✅ 📕 **5.6 Power agent (#34)**: `maverick/agents/power/`
  - `what power mode am i on`, `switch to power saver`, `use best performance`, `go to balanced power mode`
  - Uses Windows 11 power modes (the Settings slider) through `powrprof.dll`; classic plans through `powercfg`
  - `set brightness to 40`, `make the screen brighter`, `dim the screen`: laptop screens only (WMI)
  - No y/n: both change instantly and can be switched straight back
  - Brain: 23 labels; alone 72%, as MAVERICK runs 78% test / 60% hard
- ✅ 📕 **5.7 Hung app reaper (#2)**: `hung` command in `maverick/agents/process/`
  - `which apps are not responding`: the windows Windows itself marks "Not Responding" (`IsHungAppWindow`)
  - `end frozen apps`: y/n listing each app and window title, then forces them (frozen apps can't close politely)
  - `kill excel it is stuck` ends just excel; Windows' own processes are never ended
  - Core: agents can now decide y/n from the details (`is_risky`): "show frozen apps" is safe, "end frozen apps" asks
  - Brain: 24 labels; alone 73%, as MAVERICK runs 78% test / 58% hard (hard floor 0.60 → 0.55)

## Stage 6: Background agents (MAVERICK keeps running) · learned 0/3

- 👉 📕 **6.1 Background mode**: MAVERICK runs in the background so agents can watch and wait
- ⬜ 📕 **6.2 Folder watcher (#11)**: e.g. move every new PDF in Downloads to Documents
- ⏭️ 📕 **6.3 Background jobs (#5)**: skipped for now
- ⏭️ 📕 **6.4 Task scheduler (#32)**: skipped for now
- ⬜ 📕 **6.5 Log rotator (#15)**: copy, compress, empty a big log file

## Stage 7: Admin-level and hard agents (last) · learned 0/6

These need Administrator rights or are risky; each explains clearly when admin is required.

- ⬜ 📕 **7.1 Services (#31)**: list, start, stop, enable at boot
- ⏭️ 📕 **7.2 Event logs (#35)**: skipped for now
- ⏭️ 📕 **7.3 Login audit (#26)**: skipped for now
- ⬜ 📕 **7.4 Network adapters (#17)**: Wi-Fi on/off, show IP addresses
- ⏭️ 📕 **7.5 Firewall (#18)**: skipped for now
- ⬜ 📕 **7.6 Drivers (#30)**: restart a device (e.g. webcam)
- ⏭️ 📕 **7.7 Users and passwords (#23, #24)**: skipped for now
- ⏭️ 📕 **7.8 Mount (#14)**: skipped for now
- ⏭️ 📕 **7.9 Secure shredding (#13)**: skipped for now
- ⏭️ 📕 **7.10 Bandwidth (#19)**: skipped for now
- ⏭️ 📕 **7.11 Connections audit (#22)**: skipped for now
- ⏭️ 📕 **7.12 Permissions (#9)**: skipped for now
- ⬜ 📕 **7.13 Memory hogs (#29)**: spot apps whose RAM keeps growing
- ⬜ 📕 **7.14 Handle leaks (#6)**: apps holding too many handles
- ⬜ 📕 **7.15 Admin-rights audit (#25)**: who has admin on this PC (read-only)
- ❌ **#27 Linux capabilities**: dropped, no Windows equivalent

## Stage 8: AI methods (every technique from the AI Map that MAVERICK can use) · learned 0/28

Not strictly after Stage 7: each step can start once the data or agent it needs exists (noted in brackets).
Every new brain must beat the current one in `evaluate.py` before it replaces it.

**8A. Better text features**
- ⬜ 📕 **8.1 N-grams + TF-IDF**: count word pairs and weight telling words (after 4.1)

**8B. More classic models, compared side by side**
- ⬜ 📕 **8.2 Logistic regression** (scikit-learn): weight per word (after 4.1)
- ⬜ 📕 **8.3 SVM, k-nearest neighbours, decision tree**: extra comparisons, keep the winner
- ⬜ 📕 **8.4 Bernoulli Naive Bayes**: variant of the current brain, for short sentences
- ⬜ 📕 **8.5 Ensemble / voting**: combine the best models' answers

**8C. Better evaluation**
- ⬜ 📕 **8.6 Cross-validation**: more reliable scores from small data
- ⬜ 📕 **8.7 Precision, recall, F1 per label**: once labels become unbalanced
- ⬜ 📕 **8.8 Hyperparameter tuning**: try settings, keep the best

**8D. Neural networks**
- ⬜ 📕 **8.9 Neural brain (MLP)** from scratch with NumPy: layers, ReLU, softmax, loss, backpropagation, epochs, dropout (after 4.1)
- ⬜ 📕 **8.10 Word embeddings**: "duplicate" ≈ "copy" without examples (small offline model)
- ⬜ 📕 **8.11 Sentence embedding model**: match meaning, not exact words (pretrained, offline)
- ⬜ 📕 **8.12 Small pretrained transformer encoder**: fine-tuned for intent (transfer learning)

**8E. Learning from real use**
- ⬜ 📕 **8.13 Online learning**: retrain from reviewed `inbox.tsv` lines
- ⬜ 📕 **8.14 Active learning**: show the least-confident inbox lines first for labelling

**8F. Filling arguments (function calling)**
- ⬜ 📕 **8.15 Slot filling**: the brain also tags source / destination / name in the sentence
- ⬜ 📕 **8.16 Multi-label**: one sentence → several actions ("copy and zip")

**8G. Small local LLM (offline)**
- ⬜ 📕 **8.17 Local LLM setup**: Ollama or llama.cpp, a 1–4B open-weights model at 4-bit (fits RTX 2050)
- ⬜ 📕 **8.18 LLM tool calling**: describe `ops` functions; the model returns function + arguments as JSON; safety checks still run
- ⬜ 📕 **8.19 Prompting / few-shot**: tune the instructions given to the local model
- ⬜ 📕 **8.20 LoRA fine-tune** of a 0.5–1.5B model on `intents.tsv`
- ⬜ 📕 **8.21 LLM agent loop** for multi-step requests (think → tool → result → repeat)

**8H. Unsupervised and prediction (used inside agents)**
- ⬜ 📕 **8.22 Anomaly detection** (isolation forest / autoencoder): unusual RAM growth and connections (7.11, 7.13)
- ⬜ 📕 **8.23 Clustering**: group similar files, e.g. in Downloads (after 4.6)
- ⬜ 📕 **8.24 Regression / forecasting**: "C: will be full in about 3 weeks" (after 4.1)
- ⬜ 📕 **8.25 Ranking**: order file-search results by relevance (after 4.6)

**8I. Classic AI for goal requests**
- ⬜ 📕 **8.26 Planning + utility scoring**: "free up 5 GB" → choose the best files to remove (after 5.3)
- ⬜ 📕 **8.27 Constraint solving**: scheduled jobs that must not clash (after 6.4)

**8J. Voice**
- ⬜ 📕 **8.28 Offline speech-to-text** (Whisper): speak commands instead of typing

## Learning track (side chat) · learned 0/7

- 📕 **L.1** Classification
- 📕 **L.2** Bag of words
- 📕 **L.3** TF-IDF
- 📕 **L.4** Train/test split and accuracy
- 📕 **L.5** Overfitting
- 📕 **L.6** Confidence scores
- 📕 **L.7** Code walkthrough: `text.py` → `naive_bayes.py` → `evaluate.py` → orchestrator

## Small chores

- ⬜ GitHub "About" text still says PILOT: edit it with the ⚙️ gear on the repo page
