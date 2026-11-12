"""Testes da API com retriever e gerador "mockados" (não precisam de Chroma nem de chave).

Rodar na raiz:  python -m pytest api -q
"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api import generator
from api.main import app, get_generator
from api.retriever import Hit, distance_to_score, get_retriever


class FakeRetriever:
    def __init__(self, hits=None, chunks=None):
        self.hits = hits if hits is not None else [
            Hit("rh-ferias", "Política de Férias", "RH", 0, "Férias de 30 dias por ano.", 0.87),
            Hit("rh-beneficios", "Benefícios", "RH", 2, "Vale-refeição de R$ 40 por dia.", 0.71),
            Hit("ti-senhas", "Política de Senhas", "TI", 1, "Senhas trocadas a cada 90 dias.", 0.55),
        ]
        self.chunks = chunks if chunks is not None else 42
        self.last_top_k = None

    def count(self):
        return self.chunks

    def search(self, question, top_k=4):
        self.last_top_k = top_k
        return self.hits[:top_k]


@pytest.fixture
def make_client():
    def _make(retriever=None, gen=None):
        r = retriever or FakeRetriever()
        app.dependency_overrides[get_retriever] = lambda: r
        app.dependency_overrides[get_generator] = lambda: (
            gen or (lambda q, s: "São 30 dias de férias por ano [1].")
        )
        return TestClient(app), r
    yield _make
    app.dependency_overrides.clear()


# ---------------- endpoints ----------------

def test_health(make_client):
    client, _ = make_client()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "chunks": 42}


def test_ask_contrato(make_client):
    client, fake = make_client()
    r = client.post("/ask", json={"question": "Quantos dias de férias?", "top_k": 2})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"answer", "sources", "latency_ms"}
    assert body["answer"] == "São 30 dias de férias por ano [1]."
    assert isinstance(body["latency_ms"], int) and body["latency_ms"] >= 0
    assert fake.last_top_k == 2
    assert [s["n"] for s in body["sources"]] == [1, 2]
    s1 = body["sources"][0]
    assert set(s1) == {"n", "doc_id", "titulo", "trecho", "score"}
    assert s1["doc_id"] == "rh-ferias" and 0 <= s1["score"] <= 1


def test_ask_top_k_padrao_4(make_client):
    client, fake = make_client()
    client.post("/ask", json={"question": "férias?"})
    assert fake.last_top_k == 4


def test_gerador_recebe_trechos_numerados(make_client):
    recebido = {}

    def gen(q, s):
        recebido["q"], recebido["s"] = q, s
        return "ok [1]"

    client, _ = make_client(gen=gen)
    client.post("/ask", json={"question": "  férias?  "})
    assert recebido["q"] == "férias?"
    assert recebido["s"][0]["n"] == 1 and "trecho" in recebido["s"][0]


def test_pergunta_vazia(make_client):
    client, _ = make_client()
    r = client.post("/ask", json={"question": "   "})
    assert r.status_code == 400


def test_top_k_invalido(make_client):
    client, _ = make_client()
    assert client.post("/ask", json={"question": "x", "top_k": 0}).status_code == 422


def test_base_vazia(make_client):
    client, _ = make_client(retriever=FakeRetriever(hits=[], chunks=0))
    r = client.post("/ask", json={"question": "férias?"})
    assert r.status_code == 503
    assert "ingest" in r.json()["detail"].lower()


def test_sem_chave(make_client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(generator, "_client", None)
    client, _ = make_client(gen=generator.generate)
    r = client.post("/ask", json={"question": "férias?"})
    assert r.status_code == 503
    assert "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_erro_do_llm_vira_502(make_client):
    def gen(q, s):
        raise RuntimeError("timeout")

    client, _ = make_client(gen=gen)
    assert client.post("/ask", json={"question": "férias?"}).status_code == 502


def test_cors(make_client):
    client, _ = make_client()
    r = client.options("/ask", headers={
        "Origin": "http://localhost:5500",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5500"


# ---------------- gerador (Claude mockado) ----------------

class FakeAnthropic:
    def __init__(self, text, stop_reason="end_turn"):
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)
        self._text, self._stop = text, stop_reason

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(stop_reason=self._stop,
                               content=[SimpleNamespace(type="text", text=self._text)])


SOURCES = [{"n": 1, "doc_id": "rh-ferias", "titulo": "Férias", "trecho": "30 dias.", "score": 0.9}]


def _usar_fake(monkeypatch, fake):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(generator, "_client", fake)


def test_generate_monta_prompt(monkeypatch):
    fake = FakeAnthropic("São 30 dias [1].")
    _usar_fake(monkeypatch, fake)
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    assert generator.generate("Quantos dias?", SOURCES) == "São 30 dias [1]."
    kw = fake.calls[0]
    assert kw["model"] == "claude-sonnet-5-5"
    assert generator.NOT_FOUND in kw["system"]
    assert "[1] Férias (rh-ferias)" in kw["messages"][0]["content"]
    assert "temperature" not in kw


def test_generate_sem_trechos_nao_chama_llm(monkeypatch):
    fake = FakeAnthropic("x")
    _usar_fake(monkeypatch, fake)
    assert generator.generate("q", []) == generator.NOT_FOUND
    assert fake.calls == []


def test_generate_normaliza_nao_encontrei(monkeypatch):
    _usar_fake(monkeypatch, FakeAnthropic("Desculpe. Não encontrei essa informação nos documentos internos"))
    assert generator.generate("q", SOURCES) == generator.NOT_FOUND


def test_generate_recusa(monkeypatch):
    _usar_fake(monkeypatch, FakeAnthropic("", stop_reason="refusal"))
    assert generator.generate("q", SOURCES) == generator.NOT_FOUND


# ---------------- score ----------------

def test_distance_to_score():
    assert distance_to_score(0.2, "cosine") == 0.8
    assert distance_to_score(0.4, "l2") == 0.8
    assert distance_to_score(1.7, "cosine") == 0.0
    assert distance_to_score(-0.1, "cosine") == 1.0
