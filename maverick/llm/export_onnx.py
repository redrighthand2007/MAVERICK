"""Export MiniLM (8.11) to ONNX, so MAVERICK can use it WITHOUT PyTorch.

ONNX is a standard file format for a trained model: the layers and all 22.7M numbers, in one file.
PyTorch is needed once, here, to write it; afterwards the small `onnxruntime` engine runs it (like
exporting a document to PDF: you need the editor to make it, anyone can open it).

The exported graph already includes the last two steps of encoder.pooled(): the average over the words
and scaling to length 1. So the .onnx file takes word ids in and gives the 384 sentence numbers out.

Writes to maverick/brain/models/minilm/ (gitignored, ~90 MB):
  model.onnx        the network
  tokenizer.json    how a sentence is cut into word pieces and turned into ids
  reference.npz     a few sentences + PyTorch's vectors for them, so maverick.brain.minilm can check
                    that ONNX gives the same numbers (tests/test_minilm.py)

Run once:  .venv\\Scripts\\python -m maverick.llm.export_onnx
"""
import numpy as np

from maverick.brain.minilm import MINILM_DIR, MODEL_FILE, REFERENCE_FILE, TOKENIZER_FILE
from maverick.llm.encoder import embed, load, pooled

CHECK_SENTENCES = ["copy notes.txt to <path>", "duplicate this file", "kill chrome",
                   "how much ram do i have", "what started chrome", "free up 5 gb on d drive"]


def main() -> None:
    import torch

    tokenizer, model = load()
    model = model.to("cpu").eval()

    class SentenceVector(torch.nn.Module):
        """MiniLM + averaging + length 1, as one network: word ids -> 384 numbers per sentence."""

        def __init__(self, encoder):
            super().__init__()
            self.encoder = encoder

        def forward(self, input_ids, attention_mask):
            return pooled(self.encoder, {"input_ids": input_ids, "attention_mask": attention_mask})

    MINILM_DIR.mkdir(parents=True, exist_ok=True)
    sample = tokenizer(["copy this file", "kill chrome now please"], padding=True, return_tensors="pt")
    torch.onnx.export(
        SentenceVector(model), (sample["input_ids"], sample["attention_mask"]), str(MODEL_FILE),
        input_names=["input_ids", "attention_mask"], output_names=["sentence_vector"],
        # Any number of sentences, any length: these two sizes may change at every call.
        dynamic_axes={"input_ids": {0: "batch", 1: "words"}, "attention_mask": {0: "batch", 1: "words"},
                      "sentence_vector": {0: "batch"}},
        opset_version=17, dynamo=False)
    tokenizer.backend_tokenizer.save(str(TOKENIZER_FILE))
    np.savez(REFERENCE_FILE, sentences=np.array(CHECK_SENTENCES), vectors=embed(tokenizer, model, CHECK_SENTENCES))
    size = MODEL_FILE.stat().st_size / 1e6
    print(f"Wrote {MODEL_FILE} ({size:.0f} MB), {TOKENIZER_FILE.name} and {REFERENCE_FILE.name}.")


if __name__ == "__main__":
    main()
