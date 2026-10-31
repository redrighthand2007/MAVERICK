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

## Stage 4: Read-only agents (safe, can't break anything) · learned 0/6

Every agent follows the same recipe:
**a)** `ops.py` functions → **b)** `agent.py` (keywords, `extract`) → **c)** register in `main.py` →
**d)** training sentences in `intents.tsv` + hard cases → **e)** retrain, check accuracy → **f)** tests → **g)** try live

- 👉 📕 **4.1 Hardware agent (#33)**
  - RAM: total, used, free
  - RAM slots: how many, which are empty, type and speed
  - CPU: model, cores, current usage
  - Battery: percentage, charging or not, time left
  - Disks: each drive's total and free space
  - First time the brain has to choose between **two** agents
- ⬜ 📕 **4.2 Process tree agent (#4)**
  - List running processes (name, PID, CPU, RAM)
  - "What started X?": walk up the parent chain
  - Show children of a process
- ⬜ 📕 **4.3 File integrity agent (#28)**
  - Take a snapshot: SHA-256 of every file in a folder, saved as JSON
  - Compare later: list added, removed, changed files
- ⬜ 📕 **4.4 Connectivity agent (#20)**
  - Ping a host; check DNS lookup; trace the route
  - Diagnose step by step: adapter → gateway → DNS → internet
- ⬜ 📕 **4.5 Port viewer agent (#16, view only)**
  - Which app is using port X
  - List all listening ports with their apps
- ⬜ 📕 **4.6 File search agent (#7)**
  - By name or pattern (`*.pdf`), by date ("edited yesterday"), by size ("bigger than 1 GB")
  - Search inside text files for a word

## Stage 5: Action agents (use the 3.1 confirmation) · learned 0/7

- ⬜ 📕 **5.1 Process hunter (#1)**: find heavy processes by CPU/RAM/name; end them after y/n
- ⬜ 📕 **5.2 CPU priority and affinity (#3)**: set priority (low/normal/high), pin to cores
- ⬜ 📕 **5.3 Disk space optimizer (#8)**: find big/old files; delete to the **Recycle Bin** only
- ⬜ 📕 **5.4 Smart archive (#12)**: zip/tar create, list, extract (Zip Slip guard), AES encryption; port of the Linux project
- ⬜ 📕 **5.5 Broken shortcut finder (#10)**: find `.lnk` files whose target is gone; remove after y/n
- ⬜ 📕 **5.6 Power agent (#34)**: switch power plans, set screen brightness
- ⬜ 📕 **5.7 Hung app reaper (#2)**: find "Not Responding" apps; end them after y/n

## Stage 6: Background agents (MAVERICK keeps running) · learned 0/5

- ⬜ 📕 **6.1 Background mode**: MAVERICK runs in the background so agents can watch and wait
- ⬜ 📕 **6.2 Folder watcher (#11)**: e.g. move every new PDF in Downloads to Documents
- ⬜ 📕 **6.3 Background jobs (#5)**: run a command detached, Windows notification when done
- ⬜ 📕 **6.4 Task scheduler (#32)**: "every Friday at midnight" → Windows Task Scheduler
- ⬜ 📕 **6.5 Log rotator (#15)**: copy, compress, empty a big log file

## Stage 7: Admin-level and hard agents (last) · learned 0/15

These need Administrator rights or are risky; each explains clearly when admin is required.

- ⬜ 📕 **7.1 Services (#31)**: list, start, stop, enable at boot
- ⬜ 📕 **7.2 Event logs (#35)**: read the Windows System log, explain errors (e.g. USB disconnects)
- ⬜ 📕 **7.3 Login audit (#26)**: logons outside given hours
- ⬜ 📕 **7.4 Network adapters (#17)**: Wi-Fi on/off, show IP addresses
- ⬜ 📕 **7.5 Firewall (#18)**: add/remove rules from plain English
- ⬜ 📕 **7.6 Drivers (#30)**: restart a device (e.g. webcam)
- ⬜ 📕 **7.7 Users and passwords (#23, #24)**: create local users, force password change
- ⬜ 📕 **7.8 Mount (#14)**: mount ISO / VHD files only
- ⬜ 📕 **7.9 Secure shredding (#13)**: overwrite then delete; warns that SSDs can't guarantee it
- ⬜ 📕 **7.10 Bandwidth (#19)**: which app is using the network
- ⬜ 📕 **7.11 Connections audit (#22)**: outbound connections + offline GeoIP lookup
- ⬜ 📕 **7.12 Permissions (#9)**: folder permissions from plain English
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
