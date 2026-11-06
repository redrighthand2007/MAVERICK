"""LoRA fine-tuning a small LLM on MAVERICK's own requests (Stage 8.20).

8.19 TOLD the model what we want (instructions + examples in every prompt).
Fine-tuning TEACHES it instead: we keep training the model on intents.tsv, so the knowledge ends up in its weights.

Full fine-tuning would update all 360 million numbers of the model: too much memory for a 4 GB card.
LoRA (Low-Rank Adaptation) freezes them all and adds small trainable matrices next to the attention layers:
  W x   becomes   W x + B (A x)       W: frozen (960 x 960),  A: 16 x 960,  B: 960 x 16  (trained)
B starts at zero, so before training the model behaves exactly like the original.
Only ~1% of the numbers train, and the result (the "adapter") is a few MB instead of 700 MB.

The task is the brain's task (8.2): sentence -> "agent.operation".
  training text:  "Request: how much ram do i have\nAction: hardware.ram<end>"
The loss only counts the words after "Action:"; the model isn't graded on repeating the request.

Predicting: instead of letting the model write freely (it could write a label that doesn't exist),
we SCORE every real label: how likely does the model find "Action: <label>" after the request?
The most likely label wins, and softmax over the scores gives a confidence, just like the brain's.

Model: SmolLM2-360M-Instruct by Hugging Face (Apache 2.0, ~700 MB). Small enough to train on the RTX 2050.
Needs PyTorch + transformers + peft, which MAVERICK itself doesn't: they live in .venv.

Run:  .venv\\Scripts\\python -m maverick.llm.lora     (downloads the model once, trains, compares with the brain)
"""
import math
import random
import time
from pathlib import Path

from maverick.brain.dataset import HARD_CASES_PATH, INTENTS_PATH, load_examples, split
from maverick.brain.logistic_regression import LogisticRegression
from maverick.brain.text import tokenize

MODEL_ID = "HuggingFaceTB/SmolLM2-360M-Instruct"
ADAPTER_DIR = Path(__file__).resolve().parent.parent / "brain" / "models" / "lora"
EPOCHS, BATCH, LEARNING_RATE, RANK = 3, 16, 2e-4, 16


def prompt(sentence: str) -> str:
    return f"Request: {sentence}\nAction:"


def encode(tokenizer, sentence: str, label: str) -> tuple[list[int], list[int]]:
    """Token ids for prompt + answer, and the training targets: -100 (= not graded) over the prompt."""
    asked = tokenizer(prompt(sentence), add_special_tokens=False).input_ids
    answer = tokenizer(" " + label, add_special_tokens=False).input_ids + [tokenizer.eos_token_id]
    return asked + answer, [-100] * len(asked) + answer


def batches(rows: list, size: int, rng: random.Random | None = None):
    rows = rows[:]
    if rng:
        rng.shuffle(rows)
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def pad(torch, rows: list[tuple[list[int], list[int]]], pad_id: int):
    """Different sentences have different lengths; fill the short ones up so they stack into one tensor."""
    width = max(len(ids) for ids, _ in rows)
    ids = torch.tensor([ids + [pad_id] * (width - len(ids)) for ids, _ in rows])
    targets = torch.tensor([t + [-100] * (width - len(t)) for _, t in rows])
    mask = torch.tensor([[1] * len(i) + [0] * (width - len(i)) for i, _ in rows])
    return ids, targets, mask


class LoRAClassifier:
    """The fine-tuned model behind the brain's interface: predict(sentence) -> (label, confidence)."""

    def __init__(self, model, tokenizer, labels: list[str]):
        import torch
        self.torch, self.model, self.tokenizer, self.labels = torch, model, tokenizer, labels

    def scores(self, sentence: str) -> list[float]:
        """Log-probability of every label's answer after this request, all labels in one batch."""
        torch = self.torch
        rows = [encode(self.tokenizer, sentence, label) for label in self.labels]
        ids, targets, mask = (t.to(self.model.device) for t in pad(torch, rows, self.tokenizer.eos_token_id))
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
            logits = self.model(input_ids=ids, attention_mask=mask).logits.float()
        # The model's guess at position i is about token i+1, so shift by one.
        logprobs = torch.log_softmax(logits[:, :-1], dim=-1)
        wanted = targets[:, 1:]
        graded = wanted != -100
        picked = logprobs.gather(2, wanted.clamp(min=0).unsqueeze(-1)).squeeze(-1)
        return (picked * graded).sum(dim=1).tolist()

    def predict(self, sentence: str) -> tuple[str, float]:
        scores = self.scores(sentence)
        best = max(range(len(scores)), key=scores.__getitem__)
        total = sum(math.exp(s - scores[best]) for s in scores)
        return self.labels[best], 1 / total


def train(examples, epochs: int = EPOCHS, seed: int = 42) -> LoRAClassifier:
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.manual_seed(seed)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.float32).to("cuda")
    model = get_peft_model(model, LoraConfig(r=RANK, lora_alpha=2 * RANK, lora_dropout=0.05, task_type="CAUSAL_LM",
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]))
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"  LoRA trains {trainable:,} of {total:,} numbers ({trainable / total:.2%})")

    labels = sorted({label for label, _ in examples})
    classifier = LoRAClassifier(model, tokenizer, labels)
    rows = [encode(tokenizer, sentence, label) for label, sentence in examples]
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LEARNING_RATE)
    rng = random.Random(seed)
    for epoch in range(epochs):
        model.train()
        start, losses = time.time(), []
        for batch in batches(rows, BATCH, rng):
            ids, targets, mask = (t.to("cuda") for t in pad(torch, batch, tokenizer.eos_token_id))
            with torch.autocast("cuda", dtype=torch.bfloat16):
                loss = model(input_ids=ids, attention_mask=mask, labels=targets).loss
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            losses.append(loss.item())
        print(f"  epoch {epoch + 1}: loss {sum(losses) / len(losses):.3f} ({time.time() - start:.0f} s)")
    model.eval()
    return classifier


def accuracy(predict, examples) -> float:
    return sum(predict(sentence)[0] == label for label, sentence in examples) / len(examples)


def main() -> None:
    import torch
    if not torch.cuda.is_available():
        raise SystemExit("No CUDA GPU visible to PyTorch; install the GPU build into .venv.")
    train_set, test_set = split(load_examples(INTENTS_PATH))
    hard = load_examples(HARD_CASES_PATH)
    print(f"{len(train_set)} training sentences, {len(test_set)} test sentences, {len(hard)} hard cases")

    brain = LogisticRegression().fit([(label, tokenize(s)) for label, s in train_set])
    brain_predict = lambda s: brain.predict(tokenize(s))  # noqa: E731

    print(f"\nFine-tuning {MODEL_ID} with LoRA (rank {RANK}, {EPOCHS} epochs):")
    start = time.time()
    lora = train(train_set)
    print(f"  trained in {time.time() - start:.0f} s")

    start = time.time()
    lora_test = accuracy(lora.predict, test_set)
    per_sentence = (time.time() - start) / len(test_set)
    print(f"\n{'':28}{'test set':>10}{'hard cases':>12}")
    print(f"{'brain (logistic regression)':28}{accuracy(brain_predict, test_set):>10.1%}"
          f"{accuracy(brain_predict, hard):>12.1%}")
    print(f"{'LoRA fine-tuned SmolLM2':28}{lora_test:>10.1%}{accuracy(lora.predict, hard):>12.1%}")
    print(f"LoRA speed: {per_sentence * 1000:.0f} ms per sentence")

    lora.model.save_pretrained(ADAPTER_DIR)
    print(f"Adapter saved to {ADAPTER_DIR}")


if __name__ == "__main__":
    main()
