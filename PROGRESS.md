# MAVERICK — Progress Tracker

| Column | Meaning |
|---|---|
| **Built** | ✅ done · ⬜ not yet |
| **Learned** | ✅ I can explain it in my own words · ⬜ not learned yet |

Only tick **Learned** when you can explain the point without looking.

## Overview

| Stage | Topic | Built | Learned |
|---|---|---|---|
| 0 | Basics (learning only) | — | 0 / 12 |
| 1 | Foundation | 7 / 7 | 0 / 7 |
| 2 | Files agent + first brain | 9 / 9 | 0 / 9 |
| 3 | Safety net | 1 / 1 | 0 / 1 |
| 4 | Read-only agents | 3 / 3 | 0 / 3 |
| 5 | Action agents | 5 / 5 | 0 / 5 |
| 6 | Background agents | 3 / 3 | 0 / 3 |
| 7 | Admin-level agents | 6 / 6 | 0 / 6 |
| 8 | AI methods | 30 / 30 | 0 / 30 |
| **All** | | **64 / 64** | **0 / 76** |

Numbers keep their original step number (code comments say "8.5", "8.22", ...), so a few numbers are missing
where skipped agents were removed.

---

## Stage 0: Basics (learn before Stage 1)

No prior knowledge assumed. Nothing to build here: these are the ideas every stage below is built on.

**0A. How MAVERICK works**

| Built | Learned | # | Name | What it means |
|---|---|---|---|---|
| — | ⬜ | B.1 | What an "agent" is | A program that takes a request and does one job. MAVERICK's agents are plain Python, not ChatGPT |
| — | ⬜ | B.2 | Multi-agent design | One orchestrator (the manager) hands each request to the right sub-agent (the worker) |
| — | ⬜ | B.3 | One request, start to finish | You type → brain guesses the intent → orchestrator picks the agent → agent pulls out the details → safety checks → action → result |
| — | ⬜ | B.4 | Where the "AI" actually is | Only the brain: a small model that learns from example sentences. The rest is normal code |
| — | ⬜ | B.5 | Python you need | Functions, classes, modules and imports, running tests with pytest |

**0B. Machine-learning basics (side chat)**

| Built | Learned | # | Name | What it means |
|---|---|---|---|---|
| — | ⬜ | L.1 | Classification | Putting a sentence into one of a fixed set of labels (`files.copy`, `process.end`, ...) |
| — | ⬜ | L.2 | Bag of words | Turning a sentence into word counts, ignoring order |
| — | ⬜ | L.3 | TF-IDF | Rare, telling words weigh more than common ones like "the" |
| — | ⬜ | L.4 | Train/test split and accuracy | Learn from part of the data, grade on sentences the model never saw |
| — | ⬜ | L.5 | Overfitting | Memorising the training sentences instead of learning the pattern |
| — | ⬜ | L.6 | Confidence scores | How sure the model is; below a cut-off MAVERICK falls back to keyword rules |
| — | ⬜ | L.7 | Code walkthrough | `text.py` → `naive_bayes.py` → `evaluate.py` → orchestrator |

---

## Stage 1: Foundation

| Built | Learned | # | Name | What it means | Where |
|---|---|---|---|---|---|
| ✅ | ⬜ | 1.1 | Vision and design rules | What MAVERICK is for and the rules it never breaks | [docs/VISION.md](docs/VISION.md) |
| ✅ | ⬜ | 1.2 | Core shapes | `Intent` (what you want), `Result` (what happened), `SubAgent` (the shape every agent follows) | `maverick/core/agent_base.py` |
| ✅ | ⬜ | 1.3 | Orchestrator | Routes each request to the right sub-agent; handles `help`, `exit`, missing details, errors | `maverick/core/` |
| ✅ | ⬜ | 1.4 | Safety checks | Never overwrite, never touch system folders or whole drives, no folder into itself | `maverick/core/` |
| ✅ | ⬜ | 1.5 | Command line | Interactive mode and one-shot mode | `python maverick\main.py` |
| ✅ | ⬜ | 1.6 | Tests | pytest suite that checks every part automatically | `tests/` |
| ✅ | ⬜ | 1.7 | Git | Only `main` + `build`; work goes to `build`, you merge into `main` by PR | — |

---

## Stage 2: Files agent + first brain

**2A. Files agent**

| Built | Learned | # | Name | What it means | Notes |
|---|---|---|---|---|---|
| ✅ | ⬜ | 2.1 | Copy | Copy files and folders; into a folder if the target is a folder | |
| ✅ | ⬜ | 2.2 | Move | Move files and folders | Blocked for system folders |
| ✅ | ⬜ | 2.3 | Size | Size of a file or whole folder in readable units | Counts unreadable files |
| ✅ | ⬜ | 2.4 | Rename | Rename in the same folder only | Blocks paths and invalid names; never overwrites |

**2B. The brain (intent classifier)**

| Built | Learned | # | Name | What it means | Notes |
|---|---|---|---|---|---|
| ✅ | ⬜ | 2.5 | Brain roadmap | The plan for how the brain grows | [docs/BRAIN_ROADMAP.md](docs/BRAIN_ROADMAP.md) |
| ✅ | ⬜ | 2.6 | Training data | Labelled example sentences + hard cases | `maverick/brain/data/` (started at 220 + 26) |
| ✅ | ⬜ | 2.7 | Naive Bayes model | Counts how often each word appears with each label; written from scratch | `naive_bayes.py` |
| ✅ | ⬜ | 2.8 | Training + evaluation | Train the brain, then grade it on unseen sentences | Test 82% vs keyword rules 75%; hard cases 81% vs 46% |
| ✅ | ⬜ | 2.9 | Brain wired in | Brain is trusted above its confidence cut-off, keyword rules otherwise | Requests logged to `inbox.tsv` |

---

## Stage 3: Safety net

| Built | Learned | # | Name | What it means | Notes |
|---|---|---|---|---|---|
| ✅ | ⬜ | 3.1 | Confirmation prompt | Risky actions ask `(y/n)`; only y/yes goes ahead | Safety checks run before asking and again after "yes"; new agents list operations in `risky` and write `describe()` |

---

## Stage 4: Read-only agents (safe, can't break anything)

Every agent follows the same recipe: **a)** `ops.py` functions → **b)** `agent.py` (keywords, `extract`) →
**c)** register in `main.py` → **d)** training sentences + hard cases → **e)** retrain, check accuracy → **f)** tests → **g)** try live

| Built | Learned | # | Name | What it means | Notes |
|---|---|---|---|---|---|
| ✅ | ⬜ | 4.1 | Hardware agent | RAM (total/used/free, slots, type, speed), CPU, battery, disks | `maverick/agents/hardware/`; uses `psutil` + Windows CIM |
| ✅ | ⬜ | 4.2 | Process tree agent | Biggest programs by RAM/CPU; "what started X?"; "what did X start?" | `maverick/agents/process/`; copies grouped (`chrome.exe x18`) |
| ✅ | ⬜ | 4.6 | File search agent | Find files by name, kind, date, size, or text inside | `maverick/agents/search/`; skips system/junk folders, stops after 20 s |

---

## Stage 5: Action agents (use the 3.1 confirmation)

| Built | Learned | # | Name | What it means | Notes |
|---|---|---|---|---|---|
| ✅ | ⬜ | 5.1 | Process hunter | `kill chrome`, `end pid 1234`, kill the biggest RAM/CPU user | Asks y/n; polite close, then force after 3 s; refuses Windows' own processes |
| ✅ | ⬜ | 5.3 | Disk space optimizer | Find old temp files, huge files, stale downloads; delete to the Recycle Bin | `maverick/agents/cleanup/`; never empties the bin |
| ✅ | ⬜ | 5.4 | Smart archive | zip / tar / tar.gz, AES-256 passwords, list and extract | `maverick/agents/archive/`; Zip Slip guard; never overwrites |
| ✅ | ⬜ | 5.6 | Power agent | Windows power modes and laptop screen brightness | `maverick/agents/power/`; no y/n, both switch straight back |
| ✅ | ⬜ | 5.7 | Hung app reaper | Find "Not Responding" windows and end them | In `maverick/agents/process/`; y/n decided from the details (`is_risky`) |

---

## Stage 6: Background agents (MAVERICK keeps running)

| Built | Learned | # | Name | What it means | Notes |
|---|---|---|---|---|---|
| ✅ | ⬜ | 6.1 | Background mode | A thread that runs saved jobs on a timer while you chat | `maverick/core/background.py`; jobs in `~/.maverick/jobs.json`; `--background` mode |
| ✅ | ⬜ | 6.2 | Folder watcher | "move every new pdf in downloads to documents" | `maverick/agents/watch/`; waits for files to finish downloading; never overwrites |
| ✅ | ⬜ | 6.5 | Log rotator | Save a log as a dated `.gz` copy, then empty it; can run when it gets too big | `maverick/agents/logs/`; old copies never deleted |

---

## Stage 7: Admin-level agents

These need Administrator rights or are risky; each says clearly when admin is required.

| Built | Learned | # | Name | What it means | Notes |
|---|---|---|---|---|---|
| ✅ | ⬜ | 7.1 | Services | Show, start, stop, restart, enable, disable Windows services | `maverick/agents/services/`; never touches core Windows services |
| ✅ | ⬜ | 7.4 | Network adapters | IP, MAC, Wi-Fi name and signal; turn adapters on/off | `maverick/agents/network/`; y/n with a lose-internet warning |
| ✅ | ⬜ | 7.6 | Drivers / devices | Devices with problems, USB list, restart a device | `maverick/agents/devices/`; never restarts disks, CPU, firmware |
| ✅ | ⬜ | 7.13 | Memory hogs | Find programs whose RAM keeps growing (leaks) | `growing` in the process agent; samples 5 times |
| ✅ | ⬜ | 7.14 | Handle leaks | Programs holding the most Windows handles | `handles` in the process agent; flags > 10,000 |
| ✅ | ⬜ | 7.15 | Admin-rights audit | Who is an Administrator on this PC, and is MAVERICK one | `maverick/agents/accounts/`; read-only |

---

## Stage 8: AI methods

Every new brain must beat the current one in `evaluate.py` before it replaces it.
"As MAVERICK runs" = brain + keyword rules together, the score you actually feel.

**8A. Better text features**

| Built | Learned | # | Name | What it means | Result |
|---|---|---|---|---|---|
| ✅ | ⬜ | 8.1 | N-grams + TF-IDF | Word pairs (`what_started`) so word order counts; rare words weigh more | `features.py`; didn't help Naive Bayes, paid off in 8.2 |

**8B. More classic models, compared side by side**

| Built | Learned | # | Name | What it means | Result (5-fold, as MAVERICK runs) |
|---|---|---|---|---|---|
| ✅ | ⬜ | 8.2 | Logistic regression | Learns a weight per (word, label) by gradient descent | Hard cases 60% → 76% |
| ✅ | ⬜ | 8.3 | SVM, k-NN, decision tree | Three more classic models, from scratch | SVM 80.8%, k-NN 78.6%, tree 79.4%; LR 83.2% stayed best alone |
| ✅ | ⬜ | 8.4 | Bernoulli Naive Bayes | Missing words count as evidence too | 5.8% with +1 smoothing → 77.6% with 0.1 |
| ✅ | ⬜ | 8.5 | Ensemble / voting | LR + Bernoulli NB + SVM average their answers | **84.5%**, hard 75%; now the fallback brain |

**8C. Better evaluation**

| Built | Learned | # | Name | What it means | Result |
|---|---|---|---|---|---|
| ✅ | ⬜ | 8.6 | Cross-validation | Train on 4/5, test on 1/5, five times; every sentence tested once | One split swung 75–86%; 5-fold is stable |
| ✅ | ⬜ | 8.7 | Precision, recall, F1 | Per label: how often right when it says it, how many it catches | Naive Bayes macro F1 0.73 |
| ✅ | ⬜ | 8.8 | Hyperparameter tuning | Pick settings (epochs, cut-off, ...) by cross-validation | Used for every model since |

**8D. Neural networks and embeddings**

| Built | Learned | # | Name | What it means | Result |
|---|---|---|---|---|---|
| ✅ | ⬜ | 8.9 | Neural brain (MLP) | 128 neurons, backpropagation, Adam, dropout | Tied with LR (79.5%); kept as an option |
| ✅ | ⬜ | 8.10 | Word embeddings | GloVe: each word becomes 50 numbers of "meaning" | Synonym swap failed; as extra features 84.0%; not used at runtime |
| ✅ | ⬜ | 8.11 | Sentence embedding model | MiniLM (frozen) turns a sentence into 384 numbers; our LR on top | **91.6%**, hard 86% (cut-off 0.3): **the current brain**, see below |
| ✅ | ⬜ | 8.12 | Pretrained transformer, fine-tuned | The whole MiniLM retrained on our sentences | 92.3%, hard 81%; not shipped: frozen is as good and retrains in seconds without a GPU |

**8E. Learning from real use**

| Built | Learned | # | Name | What it means | Notes |
|---|---|---|---|---|---|
| ✅ | ⬜ | 8.13 | Online learning | Your reviewed real requests become training data | `python -m maverick.brain.review`; `learned.tsv` stays on your PC |
| ✅ | ⬜ | 8.14 | Active learning | The review asks about the brain's least confident guesses first | Enter = right, type a label to fix, s = skip, q = stop |

**8F. Filling arguments**

| Built | Learned | # | Name | What it means | Result |
|---|---|---|---|---|---|
| ✅ | ⬜ | 8.15 | Slot filling | Tag each word as source / destination / new name (BIO tags + Viterbi) | 93.0% fully right vs 79.0% regex |
| ✅ | ⬜ | 8.16 | Several actions in one sentence | A learned splitter cuts "zip X and then move it to Y" | Multi-action cut right 97.5% |

**8G. Small local LLM (offline)**

| Built | Learned | # | Name | What it means | Result |
|---|---|---|---|---|---|
| ✅ | ⬜ | 8.17 | Local LLM setup | Ollama + Llama 3.2 3B on your own GPU | ~38 tokens/s, 0.7 s per short answer |
| ✅ | ⬜ | 8.18 | LLM tool calling | The LLM picks an action + arguments as JSON; MAVERICK checks them | Made-up values caught and asked for |
| ✅ | ⬜ | 8.19 | Prompting / few-shot | 8 worked examples sent before each request | 88.1% → **95.2%** fully right |
| ✅ | ⬜ | 8.20 | LoRA fine-tune | Train a tiny add-on to a 360M model (0.9% of its numbers) | 81.5% vs brain 82.7%; brain stays |
| ✅ | ⬜ | 8.21 | LLM agent loop | Think → act → read result → next action or "done" | Last-resort fallback; max 4 steps |

**8H. Unsupervised and prediction (used inside agents)**

| Built | Learned | # | Name | What it means | Result |
|---|---|---|---|---|---|
| ✅ | ⬜ | 8.22 | Anomaly detection | Isolation forest: "any unusual programs running?" | Planted fakes ranked 3rd, 5th, 6th of 113 |
| ✅ | ⬜ | 8.23 | Clustering | k-means groups files in a folder by name | 96.8% vs 94.9% by extension |
| ✅ | ⬜ | 8.24 | Regression / forecasting | Straight line through disk history: "when will C: be full" | Misses by 2.1 GB vs 7.3 / 35.5 |
| ✅ | ⬜ | 8.25 | Ranking | Learned weights order search results by what you meant | MRR 0.718 vs 0.339 disk order |

**8I. Classic AI for goal requests**

| Built | Learned | # | Name | What it means | Result |
|---|---|---|---|---|---|
| ✅ | ⬜ | 8.26 | Planning + utility scoring | "free up 5 GB" with the least regret (knapsack, dynamic programming) | Optimal regret 1.93 vs greedy 2.15 |
| ✅ | ⬜ | 8.27 | Constraint solving | Fit maintenance jobs into a time window (backtracking, MRV, forward checking) | ~280x fewer tries; plans only, doesn't start jobs |

---

## MiniLM shipped (8.11 via ONNX)

| Built | Learned | # | Name | What it means | Result |
|---|---|---|---|---|---|
| ✅ | ⬜ | 8.11b | ONNX export | Convert MiniLM once (in `.venv`, needs PyTorch) to one portable file | `maverick/llm/export_onnx.py` → `maverick/brain/models/minilm/` (90 MB, gitignored) |
| ✅ | ⬜ | 8.11c | MiniLM brain | `onnxruntime` + `tokenizers` run it in MAVERICK's own Python, no PyTorch | `maverick/brain/minilm.py`; same numbers as PyTorch (diff 0.00000015); 2.5 ms per request |
| ✅ | ⬜ | 8.11d | Fallback | Also trains and saves the 8.5 ensemble; used when the files are missing | Nothing breaks on a PC without the model |

- Setup on a new PC: `pip install -r requirements.txt`, then `.venv\Scripts\python -m maverick.llm.export_onnx`,
  then `python -m maverick.brain.train` and `python -m maverick.brain.multi`
- Fixed wordings, old → new: "clone this folder" recycle 0.18 → copy 0.98; "get rid of chrome" process.origin → process.end

## Release polish (v1.0, GitHub-ready)

| Done | What | Where |
|---|---|---|
| ✅ | README rewritten: highlights, request flow diagram, 14 agents, results, setup | `README.md` |
| ✅ | Docs brought up to date; full results incl. failures; demo recording script | `docs/` |
| ✅ | MIT license | `LICENSE` |
| ✅ | Installable: `pip install -e .` gives a `maverick` command; private data excluded from packages | `pyproject.toml` |
| ✅ | CI: tests on Windows, Python 3.12 + 3.14, on every push and PR | `.github/workflows/tests.yml` |
| ✅ | Fixed: forecast said "2 readings over 5.7 days, I need 2 days" (it needs 3 readings) | `agents/hardware/ops.py` |
| ✅ | Fixed: `numpy` was missing from `requirements.txt` | |
| ✅ | Pushed and merged; CI green on Windows (Python 3.12 + 3.14) | GitHub Actions |
| ✅ | About text + topics, repo pinned on the profile | GitHub |
| ✅ | Release **v1.0.0** published | GitHub Releases |
| ✅ | Learning guide: every stage from atoms to the whole system, for study and revision | `docs/LEARN.html` |
| ⬜ | Demo GIF (`docs/demo.gif`, script in `docs/DEMO.md`) | later |
