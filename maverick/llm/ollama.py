"""Talking to a local LLM (Stage 8.17).

Ollama runs on this PC as a small web server at http://localhost:11434. It loads the model
(Llama 3.2 3B, about 2 GB) onto the graphics card and answers questions sent to it as JSON.
Nothing leaves the PC: "localhost" means this computer.

One question = one HTTP POST to /api/chat:
  {"model": "llama3.2:3b", "messages": [{"role": "system", ...}, {"role": "user", ...}]}
The "system" message tells the model how to behave; the "user" message is the question.

Only the standard library is used (urllib + json), so there is nothing extra to install.

Setup:  install Ollama, then  ollama pull llama3.2:3b
Run:    python -m maverick.llm.ollama "what is RAM?"
"""
import json
import sys
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2:3b"


class LLMError(Exception):
    """Ollama isn't running, the model isn't downloaded, or the answer came back broken."""


class Ollama:
    def __init__(self, model: str = DEFAULT_MODEL, url: str = OLLAMA_URL, timeout: float = 120):
        self.model = model
        self.url = url.rstrip("/")
        # Generous: the first question after a break also loads the model into memory.
        self.timeout = timeout

    def request(self, path: str, payload: dict | None = None) -> dict:
        """GET (no payload) or POST JSON to Ollama and return its JSON answer."""
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(self.url + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise LLMError(f"Model {self.model} isn't downloaded. Run: ollama pull {self.model}") from exc
            raise LLMError(f"Ollama answered with an error ({exc.code}).") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise LLMError(f"Ollama isn't reachable at {self.url}. Is it running?") from exc
        except json.JSONDecodeError as exc:
            raise LLMError("Ollama's answer wasn't valid JSON.") from exc

    def available(self) -> bool:
        """True if Ollama is running AND has our model downloaded."""
        try:
            models = self.request("/api/tags").get("models", [])
        except LLMError:
            return False
        return any(m.get("name") == self.model for m in models)

    def ask(self, question: str, system: str | None = None, temperature: float = 0.0) -> str:
        """One question in, the model's text answer out.

        temperature 0 = always pick the most likely next word, so the same question gets the same answer.
        Higher values make answers more varied (fine for chat, bad when we need an exact format).
        """
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": question}]
        answer = self.request("/api/chat", {
            "model": self.model, "messages": messages, "stream": False, "options": {"temperature": temperature},
        })
        try:
            return answer["message"]["content"].strip()
        except (KeyError, TypeError, AttributeError) as exc:
            raise LLMError("Ollama's answer had no message in it.") from exc


def main() -> None:
    llm = Ollama()
    if not llm.available():
        raise SystemExit(f"Ollama isn't running or {llm.model} isn't downloaded. Run: ollama pull {llm.model}")
    question = " ".join(sys.argv[1:]) or "In one sentence, what is an offline AI assistant?"
    print(llm.ask(question))


if __name__ == "__main__":
    main()
