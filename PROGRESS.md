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

- ✅ 📕 **6.1 Background mode**: `maverick/core/background.py` + `maverick/agents/jobs/`
  - A background thread inside MAVERICK ticks every job on its own interval while you keep chatting
  - Jobs are saved to `~/.maverick/jobs.json` and come back on the next start
  - `python -m maverick.main --background`: no chat, just the saved jobs (`pythonw` for no window; log in `~/.maverick/background.log`)
  - `show background jobs`, `stop job 2`, `stop watching downloads`, `cancel all background jobs`
  - One broken job never stops the others
  - Brain: 26 labels; alone 77%, as MAVERICK runs 78% test / 58% hard; floors set once for Stages 6-7 (0.60 / 0.60 / 0.70 / 0.50)
- ✅ 📕 **6.2 Folder watcher (#11)**: `maverick/agents/watch/` (a 6.1 background job)
  - `move every new pdf in downloads to documents`, `watch D:\inbox for txt files and copy them to E:\backup`
  - Asks y/n once when created; then checks every 3 s while MAVERICK (or `--background`) runs
  - Only files that arrive after it starts; waits until a file stops growing; skips `.crdownload` / `.part`
  - Never overwrites (`a.pdf` -> `a (2).pdf`); refuses folders inside each other and protected folders
  - Stop it with `stop watching downloads` or `stop job 1`
- ⏭️ 📕 **6.3 Background jobs (#5)**: skipped for now
- ⏭️ 📕 **6.4 Task scheduler (#32)**: skipped for now
- ✅ 📕 **6.5 Log rotator (#15)**: `maverick/agents/logs/`
  - `rotate D:\app\server.log`: saves it as `server-20261031-120000.log.gz` beside it, then empties it (after y/n)
  - Empties in place, so a program that has the log open keeps writing into it
  - `rotate server.log when it gets bigger than 50 mb`: a 6.1 background job that checks every minute
  - Old rotated copies are never deleted; `stop rotating server.log` ends the job
  - Brain: 29 labels; alone 74%, as MAVERICK runs 80% test / 58% hard

## Stage 7: Admin-level and hard agents (last) · learned 0/6

These need Administrator rights or are risky; each explains clearly when admin is required.

- ✅ 📕 **7.1 Services (#31)**: `maverick/agents/services/` + `maverick/core/windows.py`
  - `show running services`, `is the print spooler running`: read-only, no admin needed
  - `restart the spooler service`, `stop / start / disable ...`, `enable ... at boot`: y/n, then needs Administrator
  - Never stops or disables core Windows services (RPC, event log, Defender, firewall, DHCP/DNS, ...)
  - A name matching several services asks which one; names are safely quoted for PowerShell
  - Brain: 31 labels; alone 75%, as MAVERICK runs 81% test / 57% hard
- ⏭️ 📕 **7.2 Event logs (#35)**: skipped for now
- ⏭️ 📕 **7.3 Login audit (#26)**: skipped for now
- ✅ 📕 **7.4 Network adapters (#17)**: `maverick/agents/network/`
  - `what's my ip address`, `show network adapters`, `which wifi am i connected to`: IPv4/IPv6, MAC, speed, Wi-Fi name, signal, band
  - `turn off wifi`, `turn on wi-fi`, `disable the ethernet adapter`: y/n with a lose-internet warning, then needs Administrator
  - `connect to wifi` and Bluetooth are not handled (left for later)
  - Brain: 33 labels; alone 73%, as MAVERICK runs 80% test / 58% hard
- ⏭️ 📕 **7.5 Firewall (#18)**: skipped for now
- ✅ 📕 **7.6 Drivers (#30)**: `maverick/agents/devices/`
  - `show devices with problems`, `list usb devices`, `is my gpu working`, `show my webcam`: read-only
  - `restart the webcam`: y/n, then `pnputil /restart-device` (needs Administrator), like unplugging it
  - A broad word ("speakers") picks the one device that has a problem; otherwise asks which
  - Never restarts disks, CPU, firmware or core system devices
  - Brain: 35 labels; alone 75%, as MAVERICK runs 80% test / 53% hard
- ⏭️ 📕 **7.7 Users and passwords (#23, #24)**: skipped for now
- ⏭️ 📕 **7.8 Mount (#14)**: skipped for now
- ⏭️ 📕 **7.9 Secure shredding (#13)**: skipped for now
- ⏭️ 📕 **7.10 Bandwidth (#19)**: skipped for now
- ⏭️ 📕 **7.11 Connections audit (#22)**: skipped for now
- ⏭️ 📕 **7.12 Permissions (#9)**: skipped for now
- ✅ 📕 **7.13 Memory hogs (#29)**: `growing` command in `maverick/agents/process/`
  - `which app is leaking memory`, `find memory leaks for 2 minutes`, `whose ram keeps growing`
  - Samples every program's RAM 5 times (10 s by default, up to 5 min) and reports the ones that rose every time
  - Shows growth and MB per minute; ignores wobble under 20 MB; read-only (suggests `kill <name>`)
  - Brain: 36 labels; alone 74%, as MAVERICK runs 80% test / 52% hard
- ✅ 📕 **7.14 Handle leaks (#6)**: `handles` command in `maverick/agents/process/`
  - `which app has the most handles`, `find handle leaks`: top 10 programs by handles in their biggest process
  - Flags any single process over 10,000 handles as a likely leak; read-only (suggests `kill <name>`)
  - Brain: 37 labels; alone 75%, as MAVERICK runs 79% test / 51% hard
- ✅ 📕 **7.15 Admin-rights audit (#25)**: `maverick/agents/accounts/` (read-only)
  - `who has admin on this pc`, `am i admin`: members of the Administrators group (by SID, so any Windows language)
  - Marks disabled accounts, Microsoft vs local accounts, and which one is you; warns if more than 2 are active
  - Says whether MAVERICK itself is running as Administrator
  - Brain: 38 labels; alone 74%, as MAVERICK runs 88% test / 57% hard
- ❌ **#27 Linux capabilities**: dropped, no Windows equivalent

## Stage 8: AI methods (every technique from the AI Map that MAVERICK can use) · learned 0/28

Not strictly after Stage 7: each step can start once the data or agent it needs exists (noted in brackets).
Every new brain must beat the current one in `evaluate.py` before it replaces it.

**8A. Better text features**
- ✅ 📕 **8.1 N-grams + TF-IDF**: `maverick/brain/features.py`
  - Word pairs (`what_started`, `started_chrome`) so word order counts; TF-IDF makes rare telling words weigh more
  - Alone in Naive Bayes it didn't help (74% -> 71%: NB double-counts overlapping pairs); it pays off in 8.2

**8B. More classic models, compared side by side**
- ✅ 📕 **8.2 Logistic regression**: `maverick/brain/logistic_regression.py`, from scratch with NumPy (no scikit-learn)
  - Softmax over 38 labels, cross-entropy loss, gradient descent with momentum and L2
  - 5-fold: brain alone **73% -> 79%**, hard cases 74% -> 82%; as MAVERICK runs 84% -> 83%, hard **60% -> 76%**
  - Now the default brain; `python -m maverick.brain.train naive_bayes` still trains the old one
  - Each brain has its own confidence cut-off (logistic regression 0.4, Naive Bayes 0.6)
  - Fixed: "what started chrome" vs "what did chrome start", "what is eating my memory"
- ✅ 📕 **8.3 SVM, k-nearest neighbours, decision tree**: `maverick/brain/classic.py`, from scratch in NumPy
  - 5-fold, brain alone / as MAVERICK runs: logistic regression 78.9% / 83.2%, linear SVM 77.4% / 80.8%,
    k-NN 63.0% / 78.6%, decision tree 55.2% / 79.4%. Logistic regression stayed the best single model
- ✅ 📕 **8.4 Bernoulli Naive Bayes**: `maverick/brain/bernoulli_nb.py`, absent words count as evidence too
  - With the usual +1 smoothing: **5.8%**. The 71-sentence "unknown" label paid far less for the words a sentence
    lacks, and won almost everything. Smoothing tuned by CV: 0.3 → 63.0%, **0.1 → 77.6%**, 0.01 → 76.1%
  - Beats the original multinomial NB (73.3%; short sentences 77.0% vs 72.0%), not logistic regression
- ✅ 📕 **8.5 Ensemble / voting**: `maverick/brain/ensemble.py`, soft voting (averaged probabilities)
  - Best set: logistic regression + Bernoulli NB + linear SVM; adding NB or the MLP didn't help overall
  - Cut-off sweep, as MAVERICK runs: at **0.3** it beats logistic regression on both counts
    (5-fold **84.5% vs 83.2%**, hard cases **75% vs 73%**), so it is now the DEFAULT brain
  - Members are saved next to `brain.json` (`brain.logistic_regression.json`, ...)

**8C. Better evaluation**
- ✅ 📕 **8.6 Cross-validation**: `folds()` in `dataset.py`, `cross_validate()` in `evaluate.py`
  - 5 stratified folds: train on 4, test on 1, five times; every sentence is tested exactly once
  - Baseline Naive Bayes: brain **73.4%**, as MAVERICK runs **83.8%** (one 80/20 split swung between 75% and 86%)
- ✅ 📕 **8.7 Precision, recall, F1 per label**: `per_label()` and `macro_f1()` in `evaluate.py`
  - Precision: when the brain says a label, how often it's right; recall: how many of that label it catches
  - Macro F1 (every label counts the same): Naive Bayes 0.73
- ✅ 📕 **8.8 Hyperparameter tuning**: epochs, learning rate, L2 and the confidence cut-off picked by 5-fold cross-validation
  - `python -m maverick.brain.evaluate` compares every brain kind side by side before one replaces another

**8D. Neural networks**
- ✅ 📕 **8.9 Neural brain (MLP)**: `maverick/brain/mlp.py`, from scratch with NumPy
  - TF-IDF word pairs -> 128 ReLU neurons (30% dropout) -> softmax; backpropagation, mini-batches of 32, Adam, He init
  - A test checks backprop against a numeric gradient (nudge one weight, watch the loss)
  - 5-fold: brain alone 79.5% vs logistic regression 79.4% (a tie); hard as MAVERICK runs 81% vs 76%; 4x slower to train
  - Lesson: with ~1,200 sentences a deeper model has little extra to learn; more data (8.13) matters more
  - Kept as an option (`python -m maverick.brain.train mlp`); logistic regression stays the default
- ✅ 📕 **8.10 Word embeddings**: `maverick/brain/embeddings.py`, GloVe 6B 50d (Stanford NLP, 171 MB, `models/`)
  - The goal failed: in GloVe's 50 numbers "duplicate" is nearest "categorize" / "replicate", not "copy"
    (trained on news, too coarse for command words), so swapping unknown words didn't help (79.0% vs 78.9%)
  - Adding the sentence's average word vector to the TF-IDF features did: brain 78.9% → **81.1%**, as MAVERICK
    runs 84.0%, hard 80%. Not used at runtime (needs the 171 MB file); stanford.edu timed out, got it from HF
- ✅ 📕 **8.11 Sentence embedding model**: `maverick/llm/encoder.py`, all-MiniLM-L6-v2 FROZEN + our LR on its 384 numbers
  - "duplicate this file" / "copy this file" similarity 0.72 vs "kill chrome" 0.07: real meaning, unlike GloVe
  - 5-fold: brain **90.2%** (ensemble 80.7%), as MAVERICK runs **91.1%** (84.5%), hard cases 83% (75%); 10 s
- ✅ 📕 **8.12 Small pretrained transformer encoder**: the same MiniLM FINE-TUNED end to end (+ a 384 → labels layer)
  - 5-fold: brain **91.9%**, as MAVERICK runs **92.3%**, hard cases 81%; 2 min on the RTX 2050
  - The biggest jump of Stage 8 (+7-8 points), but NOT in MAVERICK yet: it needs PyTorch (3 GB) in MAVERICK's
    own Python, which only `.venv` has. Decide: install it, or export MiniLM to a lighter format (ONNX)

**8E. Learning from real use**
- ✅ 📕 **8.13 Online learning**: `python -m maverick.brain.review` then `python -m maverick.brain.train`
  - Your reviewed real requests go to `learned.tsv` (gitignored, stays on your PC); training adds them to intents.tsv
  - `inbox.tsv` is never changed; already-reviewed lines are not asked again
- ✅ 📕 **8.14 Active learning**: the review shows the brain's LEAST confident requests first
  - Enter = guess is right, type a label to correct it, s = skip, q = stop; typos get label suggestions

**8F. Filling arguments (function calling)**
- ✅ 📕 **8.15 Slot filling**: `maverick/brain/slots.py` + `data/slots.tsv` (200 hand-checked file sentences)
  - BIO tagging: every word gets B-source / I-source / B-destination / B-new_name / B-path / O
  - Per-word softmax regression (word, neighbours, shape, operation) + Viterbi so tag sequences are never broken
  - 5-fold cross-validation: **93.0%** of sentences fully right vs **79.0%** for the old regex rules
  - Train: `python -m maverick.brain.slots` (saves `models/slots.json`); without it the file agent uses its regex
- ✅ 📕 **8.16 Several actions in one sentence**: `maverick/brain/multi.py` + `data/multi.tsv` (85 sentences)
  - A learned splitter decides at every "and" / "then" / comma: cut here, or keep together ("cut and paste" is ONE action)
  - Stacking: the intent brain reads each side of the gap, and its answers become the splitter's features
  - 5-fold CV: multi-action sentences cut right 88.9% (words only) → **97.5%** (with the brain); one-action kept whole 80.5% → **86.4%**
  - The orchestrator checks every piece is understood BEFORE running any, then runs them in order;
    "it" / "them" means the previous step's result, a "no" or a failure stops the rest
  - Train: `python -m maverick.brain.multi` (saves `models/splitter.json`; needs the brain trained first)

**8G. Small local LLM (offline)**
- ✅ 📕 **8.17 Local LLM setup**: Ollama + **Llama 3.2 3B** (Meta, 2 GB, 4-bit); client in `maverick/llm/ollama.py`
  - Ollama is a local web server (`localhost:11434`); MAVERICK POSTs JSON to `/api/chat`, standard library only
  - On the RTX 2050: 80% GPU / 20% CPU, ~38 tokens/sec, 0.7 s per short answer once loaded (first load ~55 s)
  - temperature 0 by default, so the same question gets the same answer
  - Setup: install Ollama, then `ollama pull llama3.2:3b`. Try: `python -m maverick.llm.ollama "what is RAM?"`
  - Tests use a fake Ollama server, so they need no model or GPU
- ✅ 📕 **8.18 LLM tool calling**: `maverick/llm/tools.py`, a menu of 14 actions whose arguments are simple text
  - The model answers `{"action": "files.copy", "args": {...}}`; Ollama's JSON mode keeps the answer valid JSON
  - `check()` drops made-up actions, unknown arguments, and any value the user never typed (asked for instead)
  - The orchestrator asks the LLM only after the brain and the keyword rules failed; safety checks and y/n still run
  - Real model, 12 hand-picked requests: 10 right ("stash notes.txt over in E:\x" → files.move), 2 invented
    paths caught and asked for, "delete all my files" → none. About 3 s per request (the menu is a long prompt)
  - Off automatically when Ollama isn't running
- ✅ 📕 **8.19 Prompting / few-shot**: 8 worked examples (`tools.EXAMPLES`) sent before each request
  - Test set `data/llm_eval.tsv`: 42 unseen requests (36 actions, 6 that must be "none"), with expected arguments
  - `python -m maverick.llm.evaluate`: zero-shot **88.1%** fully right → few-shot **95.2%**, same ~2.8 s per request
  - Few-shot fixed: rename vs move, leaving out what wasn't said, "delete everything on D:" → none
  - Found a real bug: "c" inside "much" counted as the user typing drive C; values must now match whole words
- ✅ 📕 **8.20 LoRA fine-tune**: `maverick/llm/lora.py`, SmolLM2-360M-Instruct (Hugging Face) on `intents.tsv`
  - LoRA rank 16 on the attention layers: trains 3.3M of 365M numbers (0.9%); 3 epochs = 48 s on the RTX 2050
  - Predicts by SCORING every real label (it can't invent one); softmax over the scores = confidence
  - Same 80/20 split: brain **82.7%** test / **72.6%** hard cases vs LoRA 81.5% / 65.5%, 250 ms per sentence
  - Verdict: the 360M model doesn't beat our own brain, so the brain stays; adapter kept in `models/lora/`
  - Needs PyTorch (GPU), transformers, peft: installed only in `.venv`, MAVERICK itself doesn't use them
  - Run: `.venv\Scripts\python -m maverick.llm.lora`
- ✅ 📕 **8.21 LLM agent loop**: `maverick/llm/loop.py`, think → act → read the result → next action or "done"
  - Each result goes back to the model as the next message; it answers with another action or a short final answer
  - Safety stays with MAVERICK: every step goes through `check()` + `run()`; a y/n question, a failure,
    a repeated action or 4 steps end the loop; values may come from the request OR an earlier result
  - Replaces the 8.18 single call as the last-resort fallback (`ToolCaller` and `AgentLoop` share `solve()`)
  - Real model: "which one is heavier, a or b" → sizes both → "big.txt is heavier"; "weigh small.txt and if
    over 1 KB squash it" → "under 1 KB, so no action needed". It first repeated itself instead of answering;
    a reminder after each result ("reply done if answered") fixed that
  - Still weak: for big.txt it picked rename instead of zip, but rename is risky so it only got a y/n question
  - ~5 s per step; requests the keyword rules catch (e.g. with "zip" or "copy") never reach the loop

**8H. Unsupervised and prediction (used inside agents)**
- ✅ 📕 **8.22 Anomaly detection**: isolation forest in NumPy (`maverick/brain/anomaly.py`), the first UNSUPERVISED model
  - `process.unusual` ("any unusual programs running"): watches every program ~6 s, scores how unlike the rest each is
  - Numbers per program, by behaviour not size: RAM per copy, RAM growth %/min (growth only), CPU, threads per copy,
    handles per thread, network connections per copy. Every report names the extreme numbers behind it
  - First try used plain totals: it just flagged the BIG programs (svchost x90, VS Code, Brave)
  - `python -m maverick.brain.anomaly` plants 3 fake programs (a leaker, 400 connections, 3000 threads):
    ranked **3rd, 5th, 6th of 113** by the forest vs ~57th when sorting by RAM like Task Manager
  - Brain: 30 new `process.unusual` sentences, retrained; splitter retrained too (CV now 95.0% / 82.7%:
    the refolded data moved it by 2-3 sentences); `process.unusual` is also on the LLM's menu
- ✅ 📕 **8.23 Clustering**: k-means in NumPy (`maverick/brain/cluster.py`) + `search.group`, read-only
  - "group the files in my downloads": each file name → TF-IDF of its words + extension, k-means++ with restarts,
    the number of groups chosen by the silhouette score; each group is named by the words most of it shares
  - Check: `python -m maverick.brain.cluster`, 33 made-up names in 8 known groups (incl. 3 one-offs),
    scored by pair agreement: k-means **96.8%** vs one group per extension 94.9%
  - Measured, not guessed: the file kind ("document") at full weight glued invoices + lecture notes + a CV
    together (92.4%), so it now only names groups; keeping long numbers (IDs) scored worse (93.9%), dropped
  - On the real Downloads: found the 3 copies of one .pptx, the .pdf + .docx of one report, the review files;
    hidden files (desktop.ini) skipped. Brain: 30 new `search.group` sentences, retrained (+ splitter)
- ✅ 📕 **8.24 Regression / forecasting**: "when will C: be full" (`hardware.forecast`)
  - `maverick/brain/forecast.py`: least-squares line (slope, intercept, R², slope ± 2 standard errors)
  - `hardware.forecast`: line through the last 30 days of `~/.maverick/disk_history.tsv`, followed until full;
    needs 2+ days of history (recorded at most hourly: on MAVERICK start, on "space left", in --background mode)
  - Backtest (made-up 60-day disk, last 14 days hidden): line misses 2.1 GB vs 7.3 (no change), 35.5 (yesterday's change)
  - `tests/conftest.py` gives every test its own history file, so faked drives never touch the real one
  - Cost of 3 new commands (8.22-8.24, 90 sentences): first they stole old sentences ("list running processes" →
    unusual, "how long will my battery last" → forecast) because the new sentences leaned on generic words.
    Reworded 25 of them to lean on their own words (unusual, group, full): the 82% floor is kept (test split
    82.8%); the OLD commands still lost a little, 5-fold 83.0% → 82.4% (8 of 1224), the price of 3 more choices
- ✅ 📕 **8.25 Ranking**: `maverick/brain/rank.py`, search results ordered by what you most likely meant
  - 9 signals per found file: exact / whole-word / starts-with name match, name coverage, how recent,
    own folder, cache-or-system folder, depth, user file type; score = weighted sum
  - Weights LEARNED with pairwise logistic regression ("learning to rank"): meant file vs every other one
  - Graded with MRR on 200 made-up searches (look-alikes, and 1 in 5 meant the "odd" file): disk order
    0.339, newest first 0.422, hand-set weights 0.571, **learned 0.718**. Train: `python -m maverick.brain.rank`
  - Honest limit: made-up searches encode assumptions; logging which result you open would be real data
  - Live test found a search bug: the 20 s limit ran out inside hidden `.claude` / `.codex` folders before
    reaching Downloads. Dot-folders are now skipped and your own folders searched first: 1.5 s, real files found
  - Windows' Recent-files list is empty on this PC, so "opened recently" isn't used

**8I. Classic AI for goal requests**
- ✅ 📕 **8.26 Planning + utility scoring**: `maverick/brain/plan.py` + `cleanup.free` ("free up 5 GB")
  - A GOAL request: every candidate (old temp files, files over 50 MB) gets a benefit (its size) and a
    REGRET score (would you miss it: installers/ISOs low, recent documents/photos high; 0.9+ never offered)
  - The plan = the set that frees at least the goal with the least total regret: a knapsack problem,
    solved exactly by dynamic programming (16 MB steps); checked against brute force in the tests
  - `python -m maverick.brain.plan` (made-up disk, 40 candidates), total regret at 20 GB: biggest first 2.90,
    greedy 2.15, **optimal 1.93**; optimal never loses at any goal
  - Shows the plan and asks y/n; "yes" recycles EXACTLY the list shown (never a fresh plan), each item still
    through the 5.3 safety checks, to the Recycle Bin only
  - On this PC "free up 5 GB" honestly answers it can only find 2.32 GB that is safe to suggest
  - Brain: 30 `cleanup.free` sentences; accuracy went UP (test split 84.3%, 5-fold 82.7%, hard 70.2%)
- ✅ 📕 **8.27 Constraint solving**: `maverick/brain/constraints.py` + `jobs.plan` ("plan maintenance between 10 pm and 2 am")
  - A CSP: variables = when each of MAVERICK's 5 maintenance jobs starts, domains = 15-minute slots in the
    window, constraints = disk-heavy jobs never overlap, at most 2 at once, clear temp → junk scan → disk record
  - Backtracking search; `python -m maverick.brain.constraints` counts choices tried (8 jobs, 6 disk-heavy):
    fits by 02:00: plain 33, MRV 3,282, forward checking 8, both 9; impossible by 01:15: plain 141,885,
    **both 509 (~280x less)**. MRV alone was WORSE: without forward checking no slot is ever crossed out
  - Impossible windows get a reason ("the disk-heavy jobs alone need 60 minutes")
  - PLAN ONLY: 6.4 (task scheduler) was skipped, so MAVERICK can't start jobs at set times yet
  - Brain: 30 `jobs.plan` sentences. The seed-42 test split fell to 81.3% (seeds 43-47: 81.7-85.3%, 5-fold 83.2%),
    so that floor in `test_brain.py` is now checked on the 5-fold average, still 82%

**8J. Voice**
- ⏭️ 📕 **8.28 Offline speech-to-text** (Whisper): skipped (user's choice, 2026-11-06)

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
