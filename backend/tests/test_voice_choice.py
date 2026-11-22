"""The partner's voice can be chosen on the Settings page among a few German Piper voices."""

import pytest

from app import speech
from tests.test_speech import FakePiperVoice, put_voice


@pytest.fixture
def fake_voices(monkeypatch):
    FakePiperVoice.calls = []
    monkeypatch.setattr(speech, "PiperVoice", FakePiperVoice)
    monkeypatch.delenv("TTS_VOICE", raising=False)
    return FakePiperVoice


def test_the_voices_are_listed_with_the_default_chosen(client):
    voices = client.get("/api/voices").json()
    assert [v["id"] for v in voices][0] == speech.DEFAULT_VOICE
    assert {v["id"] for v in voices} >= {"de_DE-kerstin-low", "de_DE-ramona-low", "de_DE-karlsson-low"}
    assert all(v["label"] and v["size"] > 0 and v["downloaded"] is False for v in voices)
    assert [v["id"] for v in voices if v["chosen"]] == [speech.DEFAULT_VOICE]


def test_a_chosen_voice_reads_the_lines(client, fake_voices, monkeypatch):
    monkeypatch.setattr(speech, "_download_models", lambda: None)
    put_voice("de_DE-kerstin-low")
    response = client.put("/api/voice", json={"voice": "de_DE-kerstin-low"})
    assert response.status_code == 200, response.text
    assert [v["id"] for v in response.json() if v["chosen"]] == ["de_DE-kerstin-low"]
    assert next(v for v in response.json() if v["id"] == "de_DE-kerstin-low")["downloaded"] is True
    speech.synthesize("Wie war dein Wochenende?")
    assert fake_voices.calls == ["de_DE-kerstin-low: Wie war dein Wochenende?"]


def test_choosing_a_voice_starts_its_download_with_its_size(client, monkeypatch):
    fetched = []
    monkeypatch.setattr(speech, "_download_models", lambda: fetched.append(speech.current_voice()))
    client.put("/api/voice", json={"voice": "de_DE-ramona-low"})
    # The fake download writes nothing, so only its end is waited for.
    speech.model_download._thread.join(5)
    assert fetched == ["de_DE-ramona-low"]
    voice = next(m for m in client.get("/api/models").json() if m["id"] == "voice")
    assert voice["total"] == speech.VOICES["de_DE-ramona-low"].size


def test_only_a_listed_voice_can_be_chosen(client):
    assert client.put("/api/voice", json={"voice": "de_DE-nobody-high"}).status_code == 422
    assert [v["id"] for v in client.get("/api/voices").json() if v["chosen"]] == [speech.DEFAULT_VOICE]


def test_a_chosen_voice_comes_before_the_environment(client, monkeypatch):
    monkeypatch.setattr(speech, "_download_models", lambda: None)
    monkeypatch.setenv("TTS_VOICE", "de_DE-pavoque-low")
    assert speech.current_voice() == "de_DE-pavoque-low"
    client.put("/api/voice", json={"voice": "de_DE-eva_k-x_low"})
    assert speech.current_voice() == "de_DE-eva_k-x_low"
