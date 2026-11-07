"""A small pretrained transformer encoder: frozen (Stage 8.11) and fine-tuned (Stage 8.12).

Model: all-MiniLM-L6-v2 (sentence-transformers, on Microsoft's MiniLM; Apache 2.0; 22.7M numbers, 90 MB).
It reads a whole sentence, every word looking at every other word (attention), and turns it into 384 numbers.
It was trained on a billion sentence pairs to put sentences that MEAN the same close together, even with no
word in common: "duplicate this file" lands near "copy this file". That's what GloVe (8.10) couldn't do.

8.11, FROZEN: use those 384 numbers as they come, as features for our own logistic regression.
  Nothing inside MiniLM changes; only the small classifier on top learns. Training takes seconds.
8.12, FINE-TUNED (transfer learning): add one output layer (384 -> 45 labels) and train the WHOLE model on
  intents.tsv for a few rounds, with a small learning rate so it keeps what it learned and only adapts.
  Like LoRA in 8.20, but this model is small enough to update every number.

Both are measured with the same 5-fold cross-validation as the brain, brain alone and "as MAVERICK runs".
Needs PyTorch + transformers, which MAVERICK itself doesn't: they live in .venv.
Run:  .venv\\Scripts\\python -m maverick.llm.encoder
"""
import time

import numpy as np

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"


def load():
    import torch
    from transformers import AutoModel, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModel.from_pretrained(MODEL_ID, use_safetensors=True).to("cuda" if torch.cuda.is_available() else "cpu")
    return tokenizer, model


def pooled(model, batch):
    """One vector per sentence: the average of its word vectors (padding left out), length 1."""
    import torch
    out = model(**batch).last_hidden_state
    mask = batch["attention_mask"].unsqueeze(-1).float()
    mean = (out * mask).sum(1) / mask.sum(1).clamp(min=1)
    return torch.nn.functional.normalize(mean, dim=-1)


def embed(tokenizer, model, sentences: list[str], batch_size: int = 64) -> np.ndarray:
    import torch
    model.eval()
    chunks = []
    with torch.no_grad():
        for i in range(0, len(sentences), batch_size):
            batch = tokenizer(sentences[i:i + batch_size], padding=True, truncation=True, return_tensors="pt").to(model.device)
            chunks.append(pooled(model, batch).cpu().numpy())
    return np.vstack(chunks)


class Frozen:
    """8.11: logistic regression on MiniLM's sentence vectors. Speaks the brain's predict(tokens) language."""
    threshold = 0.4

    def __init__(self, vectors: dict[str, np.ndarray]):
        from maverick.brain.logistic_regression import LogisticRegression

        class OnVectors(LogisticRegression):
            def features(self, docs):
                return np.array([vectors[" ".join(d)] for d in docs])

        self.model = OnVectors(epochs=400, learning_rate=4.0)

    def fit(self, examples):
        self.model.fit(examples)
        return self

    def predict(self, tokens):
        return self.model.predict(tokens)


class FineTuned:
    """8.12: the whole MiniLM plus a 384 -> labels layer, trained end to end."""
    threshold = 0.4

    def __init__(self, tokenizer, epochs: int = 6, lr: float = 5e-5, batch_size: int = 16, seed: int = 0):
        self.tokenizer, self.epochs, self.lr, self.batch_size, self.seed = tokenizer, epochs, lr, batch_size, seed

    def fit(self, examples):
        import torch
        from transformers import AutoModel
        torch.manual_seed(self.seed)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.encoder = AutoModel.from_pretrained(MODEL_ID, use_safetensors=True).to(device)  # fresh copy per fold
        self.labels = sorted({label for label, _ in examples})
        self.head = torch.nn.Linear(384, len(self.labels)).to(device)
        params = list(self.encoder.parameters()) + list(self.head.parameters())
        optimizer = torch.optim.AdamW(params, lr=self.lr)
        texts = [" ".join(tokens) for _, tokens in examples]
        targets = torch.tensor([self.labels.index(label) for label, _ in examples])
        rng = np.random.default_rng(self.seed)
        for _ in range(self.epochs):
            self.encoder.train()
            order = rng.permutation(len(texts))
            for i in range(0, len(order), self.batch_size):
                rows = order[i:i + self.batch_size]
                batch = self.tokenizer([texts[r] for r in rows], padding=True, truncation=True, return_tensors="pt").to(device)
                # x20: the sentence vector has length 1, so raw scores would be tiny; a fixed "temperature" helps.
                logits = self.head(pooled(self.encoder, batch) * 20)
                loss = torch.nn.functional.cross_entropy(logits, targets[rows].to(device))
                loss.backward()
                optimizer.step()
                optimizer.zero_grad()
        self.encoder.eval()
        return self

    def predict(self, tokens):
        import torch
        with torch.no_grad():
            batch = self.tokenizer([" ".join(tokens)], return_tensors="pt").to(self.encoder.device)
            probs = torch.softmax(self.head(pooled(self.encoder, batch) * 20), dim=-1)[0].cpu().numpy()
        best = int(np.argmax(probs))
        return self.labels[best], float(probs[best])


def main() -> None:
    from maverick.brain.dataset import HARD_CASES_PATH, INTENTS_PATH, folds, load_examples
    from maverick.brain.evaluate import accuracy, as_maverick_runs, grade
    from maverick.brain.text import tokenize
    from maverick.brain.train import train

    examples, hard = load_examples(INTENTS_PATH), load_examples(HARD_CASES_PATH)
    tokenizer, model = load()
    texts = sorted({" ".join(tokenize(s)) for _, s in examples + hard})
    start = time.time()
    vectors = dict(zip(texts, embed(tokenizer, model, texts)))
    print(f"MiniLM turned {len(texts)} sentences into 384 numbers each in {time.time() - start:.1f} s.")
    v = lambda s: vectors[" ".join(tokenize(s))]  # noqa: E731
    print("  similarity 'duplicate this file' / 'copy this file':",
          f"{float(embed(tokenizer, model, ['duplicate this file', 'copy this file']).prod(axis=0).sum()):.2f}",
          "| 'kill chrome' / 'copy this file':", f"{float(v('kill chrome') @ v('copy notes.txt')):.2f}")

    makers = {"current brain (8.5 ensemble)": lambda part: train(part),
              "8.11 MiniLM frozen + LR": lambda part: Frozen(vectors).fit([(l, tokenize(s)) for l, s in part]),
              "8.12 MiniLM fine-tuned": lambda part: FineTuned(tokenizer).fit([(l, tokenize(s)) for l, s in part])}
    print("\n5-fold cross-validation, every sentence tested once (hard cases: trained on everything):")
    for name, make in makers.items():
        start, brain, maverick = time.time(), [], []
        for train_part, test_part in folds(examples):
            m = make(train_part)
            brain.append(accuracy(grade(lambda s, m=m: m.predict(tokenize(s)), test_part)))
            maverick.append(accuracy(grade(as_maverick_runs(m), test_part)))
        full = make(examples)
        hard_brain = accuracy(grade(lambda s: full.predict(tokenize(s)), hard))
        hard_maverick = accuracy(grade(as_maverick_runs(full), hard))
        print(f"  {name:30} brain {np.mean(brain):.1%}  as MAVERICK runs {np.mean(maverick):.1%}  "
              f"| hard: brain {hard_brain:.0%}, as MAVERICK runs {hard_maverick:.0%}  ({time.time() - start:.0f} s)")


if __name__ == "__main__":
    main()
