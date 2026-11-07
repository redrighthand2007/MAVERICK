# Results

Every model in MAVERICK, how it was measured, and what it scored, including the ones that failed.

## How things are measured

- **Data:** `maverick/brain/data/intents.tsv` has 1,374 hand-labelled sentences across 46 operations
  plus `unknown`. `hard_cases.tsv` has 84 deliberately tricky sentences that are never trained on.
- **5-fold cross-validation:** train on 4/5 of the sentences, test on the other 1/5, five times. Every
  sentence is tested exactly once. A single 80/20 split swung between 75% and 86% depending on the
  random seed, which is why 5-fold is the standard here.
- **Two scores:**
  - **brain alone**: the model by itself
  - **as MAVERICK runs**: the model when its confidence is over its cut-off, keyword rules otherwise.
    This is what a user actually gets.
- **Rule:** a new model replaces the current one only if it is better on the same folds. The test
  suite fails if accuracy drops below a floor (`tests/test_brain.py`).
- **Reproduce:** `python -m maverick.brain.evaluate` (every brain kind side by side), and each module
  below has its own `python -m ...` benchmark.

## 1. The brain: which operation did you mean?

"Hard cases" means as MAVERICK runs. Rows marked * were measured when that model was added, on the
smaller dataset of the time; all other rows use the final 1,374 sentences.

| Model (all written from scratch) | Brain alone | As MAVERICK runs | Hard cases |
|---|---|---|---|
| Naive Bayes, bag of words * | 73.4% | 83.8% | 60% |
| Logistic regression, TF-IDF + word pairs, momentum, L2 | 78.9% | 83.2% | 73% |
| Linear SVM (hinge loss) | 77.4% | 80.8% | – |
| k-nearest neighbours (k = 5) | 63.0% | 78.6% | – |
| Decision tree (Gini) | 55.2% | 79.4% | – |
| Bernoulli Naive Bayes (smoothing 0.1) | 77.6% | – | – |
| MLP: 128 ReLU, dropout, Adam, backprop * | 79.5% | – | 81% |
| GloVe 50d word vectors as extra features | 81.1% | 84.0% | 80% |
| Ensemble: LR + Bernoulli NB + linear SVM, soft voting | 80.7% | 84.5% | 75% |
| MiniLM fine-tuned end to end (PyTorch, GPU) | 91.9% | 92.3% | 81% |
| **MiniLM frozen (ONNX) + logistic regression: shipped** | **90.2%** | **91.6%** | **86%** |

Why the frozen MiniLM was shipped instead of the fine-tuned one, which scores 0.7 points higher:
- It's better on hard cases.
- Retraining after you correct it takes 11 seconds on a CPU, instead of 2 minutes on a GPU.
- It runs with `onnxruntime` (2.5 ms per request) instead of 3 GB of PyTorch.
- The ONNX export was checked against PyTorch: maximum difference 1.5 × 10⁻⁷.

### What failed, and why

- **TF-IDF word pairs inside Naive Bayes:** 74% → 71%. Overlapping pairs ("started", "started_chrome")
  are counted twice by Naive Bayes. The same features lifted logistic regression, which learns weights
  instead.
- **Bernoulli Naive Bayes with the usual +1 smoothing: 5.8%.** The 71-sentence `unknown` label paid
  the smallest penalty for all the words a short sentence *lacks*, so it won almost every time.
  Smoothing 0.1, chosen by cross-validation, fixed it (77.6%).
- **GloVe synonym swap:** replacing unknown words with their nearest GloVe neighbour didn't help
  (79.0% vs 78.9%). In GloVe's 50 dimensions, "duplicate" sits next to "categorize", not "copy".
  MiniLM, trained on sentence pairs, puts "duplicate this file" next to "copy this file" (0.72
  similarity vs 0.07 for "kill chrome").
- **MLP vs logistic regression:** a tie (79.5% vs 79.4%) at 4× the training time. With about 1,200
  sentences, a deeper model has little extra to learn.
- **LoRA fine-tune of SmolLM2-360M** (3.3M of 365M weights trained): 81.5% vs the brain's 82.7% on the
  same split, at 250 ms per sentence. Not used.

## 2. Pulling out the details

| Task | Method | Result |
|---|---|---|
| File names in a request (source / destination / new name) | Per-word softmax tagger, BIO tags, Viterbi decoding | **93.0%** of sentences fully right vs 79.0% for regex rules |
| Several actions in one sentence | Learned splitter at every "and" / "then" / comma, stacked with the brain's predictions | **95.8%** of multi-action sentences cut right; 89.2% of one-action sentences left whole ("cut and paste" is one action) |

## 3. Local LLM (Llama 3.2 3B via Ollama)

Tested on 42 unseen requests (36 actions, 6 that must be refused), with the exact arguments expected.

| Prompting | Fully right | Time per request |
|---|---|---|
| Zero-shot tool calling | 88.1% | ~2.8 s |
| **Few-shot (8 worked examples)** | **95.2%** | ~2.8 s |

- Every value the LLM returns must appear in the request or in an earlier result; otherwise MAVERICK
  asks for it.
- This caught a real bug: the drive letter "c" inside "much" counted as the user typing drive C.
  Values must now match whole words.
- The agent loop (think → act → read the result → repeat, up to 4 steps) handles requests like
  "which one is heavier, a or b".

## 4. Models inside agents

| Agent feature | Method | Benchmark | Result |
|---|---|---|---|
| "any unusual programs running?" | Isolation forest on behaviour (RAM growth, threads per copy, handles per thread, connections per copy) | 3 planted fake programs among 113 real ones | Ranked **3rd, 5th, 6th** vs ~57th when sorted by RAM |
| "group the files in my downloads" | k-means++ on TF-IDF of file-name words, number of groups chosen by silhouette | 33 names in 8 known groups | **96.8%** pair agreement vs 94.9% grouping by extension |
| "when will C: be full?" | Least-squares line with R² and slope uncertainty | Made-up 60-day disk, last 14 days hidden | Off by **2.1 GB** vs 7.3 GB (no change) and 35.5 GB (repeat yesterday) |
| Search result order | Learning to rank: pairwise logistic regression over 9 signals | 200 made-up searches, MRR | **0.718** vs 0.571 hand-set weights, 0.422 newest first, 0.339 disk order |
| "free up 5 GB" | Knapsack by dynamic programming: least total "would you miss it" score | Made-up disk, 40 candidates, 20 GB goal | Regret **1.93** vs 2.15 greedy, 2.90 biggest first; checked against brute force |
| "plan maintenance between 10 pm and 2 am" | Constraint satisfaction: backtracking + MRV + forward checking | 8 jobs into an impossible window | **509** choices tried vs 141,885 plain backtracking (~280× fewer) |

Honest limits:
- The ranking and planning benchmarks use made-up data, so they encode assumptions. Logging which
  result you actually open would give real ranking data.
- MRV alone was *worse* than plain backtracking. Without forward checking it can't see that a slot
  is already ruled out.

## 5. Learning from real use

- `python -m maverick.brain.review` shows logged real requests, least confident first (active
  learning).
- Corrections go to `learned.tsv`, which stays on your PC, and are added at the next training.
- With the MiniLM brain, retraining takes about 11 seconds on a CPU.
