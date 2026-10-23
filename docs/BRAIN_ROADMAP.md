# MAVERICK — Brain Roadmap

The "brain" is the part of MAVERICK that reads a sentence and decides **which
agent and which operation** it means:

```
"how much space does D:\games take up"   →   files.size
"make a backup copy of notes.txt"        →   files.copy
"what's the weather like"                →   unknown
```

We are building it **ourselves, from scratch**: first by hand in pure Python,
then with scikit-learn to compare. No LLM, no Ollama, no internet. Everything
runs offline on this laptop (16 GB RAM, RTX 2050 4 GB — plenty; none of
Phases 1–6 even need the GPU).

## What the brain does and does NOT do

Be clear about this from day one:

| The brain (classifier) | The existing rules (`parse()`) |
|---|---|
| Picks the **label**: `files.rename` | Pulls out the **arguments**: `a.txt`, `b.txt` |
| Handles "make a duplicate of…", "how heavy is…", typos-ish wording | Finds paths, quoted strings, numbers |
| Gives a **confidence** (0.0 – 1.0) | Reports what is **missing** |

A classifier picks one answer from a fixed list. It **cannot** read a path out
of a sentence, invent a new operation, or do anything it has no label for.
Safety checks in `core/safety.py` stay exactly where they are: the brain only
decides *what* you asked for, never *whether it is allowed*.

## How to use this roadmap

- Work one phase at a time. Each phase has a **goal**, small **steps**, and a
  **done when** check. Don't move on until "done when" is true.
- You write the code; Claude explains, reviews, and answers questions.
- Commit small (on `build`), one step at a time.

## Planned layout

```
maverick/brain/
    __init__.py
    data/
        intents.tsv        # the training examples (committed)
        hard_cases.tsv     # tricky sentences, never trained on (committed)
        inbox.tsv          # real requests logged by MAVERICK (gitignored)
    text.py                # cleaning + tokenizing, shared by everything
    naive_bayes.py         # Version A: your own classifier, no libraries
    sk_model.py            # Version B: scikit-learn version
    train.py               # reads data, trains, saves the model file
    evaluate.py            # accuracy, per-label scores, confusion matrix
    models/                # trained model files (gitignored)
tests/
    test_brain.py
```

---

## Phase 1 — Concepts first (no code)

**Goal:** be able to explain, in your own words, every idea the later phases use.

1. **Classification.** A function that takes an input and picks one label from
   a fixed list. Spam filters, "is this a cat photo", and our brain are all
   classifiers. The list of labels is decided by *us*, up front.
2. **Features.** Computers can't do maths on sentences, so we turn each
   sentence into numbers.
   - *Bag of words*: count each word, ignore order.
     `"copy the file"` → `{copy: 1, the: 1, file: 1}`.
     Loses order ("dog bites man" = "man bites dog"), but for short commands it
     works surprisingly well.
   - *TF-IDF*: like bag of words, but words that appear in almost every
     sentence ("the", "please") get a low weight, and rare, telling words
     ("rename") get a high weight.
3. **Training vs testing data.** The model learns from the *training* set. We
   then grade it on a *test* set it has **never seen**. Grading on training
   data is like a teacher giving the exam questions as homework first: the score
   means nothing.
4. **Accuracy.** Correct predictions ÷ total predictions on the test set. Also
   look at accuracy **per label**: 95% overall can hide a label that is wrong
   half the time.
5. **Overfitting.** The model memorises the training sentences instead of
   learning the pattern. Symptom: ~100% on training data, much worse on test
   data. Cure: more and more varied examples, simpler models.
6. **Confidence scores.** The model gives a probability for every label, e.g.
   `files.size 0.82, files.copy 0.10, unknown 0.08`. We act only when the top
   score is high enough; otherwise MAVERICK asks you to rephrase. Warning:
   these numbers are *the model's opinion*, not truth. Naive Bayes in
   particular tends to be over-confident.

**Done when:** you can answer, without notes: *Why can't we test on training
data? What would overfitting look like in our numbers? Why does TF-IDF give
"the" a low weight? What does the brain NOT do?*

---

## Phase 2 — The dataset

**Goal:** a labeled file of example sentences that the brain will learn from.
The data matters more than the algorithm.

### Labels

Format: `agent.operation`, matching MAVERICK's real agents and operations.

```
files.copy
files.move
files.rename
files.size
unknown          # anything MAVERICK can't do: "tell me a joke", "hi", "what's 2+2"
```

`unknown` is essential. Without it the brain is forced to pick a real
operation for *every* sentence, even nonsense.

### Format: `maverick/brain/data/intents.tsv`

One example per line: label, a **tab**, then the sentence. Tab-separated
because Windows paths and sentences are full of commas and quotes; tabs never
appear in them.

```
files.copy	copy notes.txt to D:\backup
files.copy	make a duplicate of report.docx
files.size	how much space does D:\games use
files.rename	change the name of a.txt to b.txt
unknown	what's the weather today
```

Lines starting with `#` are comments; blank lines are skipped.

### Paths are noise: replace them

`D:\games` or `notes.txt` say nothing about *which operation* you want, and
every real request will contain different ones. So before training **and**
before predicting, `text.py` replaces anything path-like with a placeholder:

```
"copy notes.txt to D:\backup"  →  "copy <path> to <path>"
```

Now the model learns from the words that matter. (The real paths are still
extracted later by the rule code, from the original text.)

### How many examples

- Start: **30 per label** (≈150 total). Enough to get going.
- Target: **80–100+ per label**.
- `unknown`: give it *at least* as many as any other label, and make them
  varied (greetings, questions, other tasks MAVERICK can't do yet, gibberish).
- Keep labels roughly balanced: a label with 200 examples next to one with 20
  biases the model toward the big one.

### Writing varied phrasings

For each label, vary on purpose:

- verbs: copy / duplicate / clone / make a backup of
- politeness: "please copy…", "can you copy…", "copy…"
- word order: "to D:\backup copy notes.txt"
- short and long: "size of D:\x" vs "I'd like to know how big my games folder is"
- casual spelling: "whats", "pls", lowercase, no punctuation
- **confusable pairs**: copy vs move ("move a copy of…" is a copy!), rename vs
  move ("move a.txt to b.txt" in the same folder is really a rename)

Separately, write `hard_cases.tsv`: 20–40 deliberately tricky sentences that
are **never** used for training. This is your honest final exam.

### Logging real requests (future data)

Later (Phase 6), MAVERICK appends every request it sees to
`maverick/brain/data/inbox.tsv` with its guess and confidence. You read it
now and then, fix the labels by hand, and move good lines into `intents.tsv`.
`inbox.tsv` is **gitignored**: it contains your real file paths.

**Done when:** `intents.tsv` has ≥30 examples for each of the 5 labels,
`hard_cases.tsv` exists, and a tiny script can load the file and print how
many examples each label has.

---

## Phase 3 — Version A: Naive Bayes from scratch (pure Python)

**Goal:** a working classifier you wrote yourself, with no libraries, so the
maths is yours.

### The idea in one line

Pick the label that makes the sentence's words most likely:

```
score(label) = P(label) × P(word1 | label) × P(word2 | label) × ...
```

- `P(label)`: how common the label is in training (prior).
- `P(word | label)`: how often that word appears in sentences of that label.
- "Naive" = we pretend words are independent of each other. It's false, and it
  works anyway.

### Steps

1. **`text.py`**: `tokenize(sentence) -> list[str]`: lowercase, replace paths
   with `<path>`, split into words, strip punctuation. Test it on a few
   sentences by hand.
2. **Count.** For each label: how many sentences it has, and how many times
   each word appears in it. Plain `dict`s and `collections.Counter`.
3. **Laplace smoothing.** A word never seen with a label would give
   probability 0 and wipe out the whole product. Add 1 to every count:
   `P(word | label) = (count + 1) / (total_words_in_label + vocabulary_size)`.
4. **Use logs.** Multiplying many small numbers underflows to 0.0. Add
   logarithms instead: `log(a × b) = log a + log b`.
5. **Predict.** Compute the log-score for every label; the highest wins.
6. **Confidence.** Turn log-scores into probabilities that sum to 1
   (subtract the max, `exp`, divide by the total; this is called *softmax*).
   Return `(label, confidence)`.
7. **Save / load.** The "model" is just the counts. Save them as JSON to
   `maverick/brain/models/naive_bayes.json` and load them back.

**Done when:** `train()` then `predict("duplicate my notes file")` returns
`("files.copy", <some confidence>)`, the JSON file round-trips, and you can
explain every line.

---

## Phase 4 — Version B: scikit-learn (TF-IDF + logistic regression)

**Goal:** solve the same problem with a standard library and see how your own
version compares.

1. Add `scikit-learn` to `requirements.txt` and install it in `.venv`.
2. `TfidfVectorizer(tokenizer=your tokenize)`: reuse **your** `text.py` so
   both versions see identical words.
3. `LogisticRegression`: a different model family: it learns a weight per
   word per label instead of counting.
4. Wrap both in a `Pipeline`, `fit` on the training data, `predict_proba` for
   confidence.
5. Save with `joblib` to `maverick/brain/models/sk_model.joblib`.
6. Give both versions the **same interface**:
   `predict(text) -> (label, confidence)`, so MAVERICK can use either.

Try `ngram_range=(1, 2)` (single words *and* pairs of words like "a copy") and
see whether it helps on the confusable pairs.

**Done when:** both versions train on the same data and you have a small table
comparing their test accuracy.

---

## Phase 5 — Evaluation

**Goal:** honest numbers, and a test that protects them.

1. **Train/test split.** Shuffle with a **fixed seed** (so results repeat),
   keep 80% for training, 20% for testing. Split **per label** (stratified) so
   every label appears in the test set.
2. **Overall accuracy** on the test set, and on `hard_cases.tsv`.
3. **Per-label accuracy**: for each label, what fraction of its test sentences
   were labeled correctly.
4. **Confusion matrix**: a table, real label down the side, predicted label
   across the top. The diagonal is correct; everything off it shows *which*
   labels get mixed up (probably copy↔move). Print it as text, no plotting
   needed.
5. **Baseline:** run the current keyword `parse()` rules on the same test set.
   The brain must beat it, or it isn't earning its place.
6. **Threshold check:** for confidences 0.5, 0.6, 0.7, 0.8: how many
   predictions would be accepted, and how many of those would be wrong? Pick
   the threshold from this table.
7. **`tests/test_brain.py`**: trains on the training split and **fails if test
   accuracy drops below a threshold** (start at 0.85, raise it as the data
   grows). Also a few must-pass sentences, e.g. `"rename a.txt to b.txt"` →
   `files.rename`.

**Done when:** `python -m maverick.brain.evaluate` prints accuracy, per-label
scores and a confusion matrix for both versions, and `pytest` runs the brain
test alongside the existing 15.

---

## Phase 6 — Integration into MAVERICK

**Goal:** the orchestrator uses the brain to choose the agent and operation;
the rules still extract arguments.

### The new flow

```
text
 │
 ▼
brain.predict(text) ──► ("files.size", 0.91)
 │
 ├─ confidence ≥ threshold and label ≠ unknown
 │      → agent "files", operation "size"
 │      → files agent extracts the arguments (paths) for "size"
 │      → handle() as today (safety checks unchanged)
 │
 ├─ confidence < threshold, or model file missing
 │      → fall back to today's keyword parse() rules
 │      → rules also find nothing? → "I'm not sure what you mean. Did you
 │        want files.size? Try rephrasing."
 │
 └─ label = unknown (confident)
        → "No MAVERICK agent handles that yet."
```

### Steps

1. **Split `parse()` in two.** Today `FileAgent.parse` both *chooses* the
   operation and *extracts* paths. Add a method like
   `extract(operation, text) -> Intent` that only does the path part for a
   given operation. `parse()` keeps working (it becomes the fallback) and
   reuses `extract`. Existing tests must still pass.
2. **A `Brain` class** in `maverick/brain/__init__.py`: loads the saved model
   at start-up, exposes `predict(text)`. If the model file is missing, it says
   so once and MAVERICK runs on rules only. It never crashes MAVERICK.
3. **Orchestrator** takes an optional brain and follows the flow above. Look
   up the agent by the part before the dot (`files`).
4. **Threshold** as a single constant (the value you chose in Phase 5).
5. **Logging** to `inbox.tsv`: text, predicted label, confidence.
6. **Tests:** orchestrator with a fake brain (always returns a fixed answer)
   to test each branch without training anything.

### Commit the model file or not?

**Gitignore it** (`maverick/brain/models/`). It is a *build output*: anyone
can recreate it from `intents.tsv` + your code with
`python -m maverick.brain.train`. Committing it means every retrain adds a
binary diff, and the code and data are the real source. (Also, `joblib`/pickle
files can run code when loaded, so you should only ever load ones you made
yourself.) **Do commit** `intents.tsv` and `hard_cases.tsv`.

**Done when:** "make a duplicate of notes.txt to D:\backup" (no keyword
`copy`) works end-to-end, a low-confidence sentence gets the rephrase message,
deleting the model file still leaves MAVERICK working on rules, and all tests
pass.

---

## Phase 7 — Growing the brain

**Goal:** keep the brain good as MAVERICK grows toward ~35 agents.

### Adding a new agent (e.g. `process`, `hardware`, `network`)

Every new agent follows the same checklist:

1. Build the agent and its `extract()` as usual.
2. Add its labels (`process.list`, `process.kill`, `hardware.battery`, …) with
   30+ examples each to `intents.tsv`.
3. Add new hard cases, especially ones that could be confused with *existing*
   labels ("kill the file" vs "kill the process").
4. Some sentences that used to be `unknown` now belong to the new agent:
   **relabel them**, or the brain learns contradictions.
5. Retrain, run `evaluate`, check the confusion matrix, run `pytest`.

### Things that will come up as it grows

- **Many labels** (35 agents × 3–5 operations ≈ 100–150 labels). If accuracy
  drops, try two steps: first predict the *agent*, then the operation within
  that agent. Two smaller problems are often easier than one big one.
- **Data from real use.** Review `inbox.tsv` regularly; your real phrasing is
  the best training data there is.
- **Raise the accuracy bar** in `test_brain.py` as the data improves, never
  lower it silently.

### Optional, much later: fine-tune a small LLM with LoRA

Only after Phases 1–6 work and you've hit the limits of word-count models
(e.g. it can't understand phrasing it has never seen words for).

- **LoRA** trains a small set of extra weights on top of a frozen pre-trained
  model, so it fits on modest hardware.
- On a 4 GB RTX 2050, realistically a **~0.5–1.5B parameter** model with
  4-bit loading (QLoRA). Bigger won't fit.
- Same data, same labels, same evaluation, same tests: you'd compare it
  against Version A and B exactly like Phase 4 compared those two.
- A bonus an LLM could add: extracting arguments too (slot filling). Even
  then, everything still goes through `safety.py`.
- Honest trade-off: much slower to train and run, much bigger files, harder to
  understand. The from-scratch brain stays as the fallback.

**Done when (ongoing):** each new agent ships with its labels, examples, hard
cases, and a passing brain test.

---

## Progress

- [ ] Phase 1: Concepts (learning in the side chat)
- [x] Phase 2: Dataset (built, 220 examples + 26 hard cases)
- [x] Phase 3: Naive Bayes from scratch (built, to be studied)
- [ ] Phase 4: scikit-learn version
- [x] Phase 5: Evaluation (test 82%, hard cases 81%; keyword rules 75% / 46%)
- [x] Phase 6: Integration (threshold 0.6, rules fallback, inbox logging)
- [ ] Phase 7: Growing (ongoing)

Note: built first, learned later (user's choice). Phases 2-6 are in the code;
walk through them in the learning chat. A confident `unknown` still lets
keyword rules try, so an explicit command like "copy a b" can never be
blocked by a wrong brain guess.
