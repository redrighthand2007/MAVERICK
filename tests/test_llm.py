import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from maverick.llm.ollama import LLMError, Ollama


class FakeOllama(BaseHTTPRequestHandler):
    """A stand-in for Ollama's web server, so these tests need no model, GPU or download."""
    models = ["llama3.2:3b"]
    received = []

    def reply(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/tags":
            self.reply(200, {"models": [{"name": name} for name in self.models]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.received.append(body)
        if body["model"] not in self.models:
            self.reply(404, {"error": f"model '{body['model']}' not found"})
        else:
            question = body["messages"][-1]["content"]
            self.reply(200, {"message": {"role": "assistant", "content": f"  You asked: {question}\n"}})

    def log_message(self, *args):  # keep pytest output quiet
        pass


@pytest.fixture
def server():
    FakeOllama.received = []
    httpd = HTTPServer(("127.0.0.1", 0), FakeOllama)  # port 0: the OS picks a free one
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_ask_returns_the_answer_without_extra_spaces(server):
    assert Ollama(url=server).ask("what is RAM?") == "You asked: what is RAM?"


def test_ask_sends_the_system_message_first_and_temperature(server):
    Ollama(url=server).ask("hi", system="You are MAVERICK.", temperature=0.5)
    sent = FakeOllama.received[0]
    assert sent["messages"] == [{"role": "system", "content": "You are MAVERICK."},
                                {"role": "user", "content": "hi"}]
    assert sent["options"]["temperature"] == 0.5
    assert sent["stream"] is False


def test_no_system_message_means_only_the_question(server):
    Ollama(url=server).ask("hi")
    assert FakeOllama.received[0]["messages"] == [{"role": "user", "content": "hi"}]


def test_available_needs_the_model_downloaded(server):
    assert Ollama(url=server).available()
    assert not Ollama(model="some-other-model", url=server).available()


def test_a_missing_model_says_how_to_download_it(server):
    with pytest.raises(LLMError, match="ollama pull some-other-model"):
        Ollama(model="some-other-model", url=server).ask("hi")


def test_ollama_not_running_is_a_clear_error():
    llm = Ollama(url=f"http://127.0.0.1:{free_port()}", timeout=2)
    assert not llm.available()
    with pytest.raises(LLMError, match="isn't reachable"):
        llm.ask("hi")
