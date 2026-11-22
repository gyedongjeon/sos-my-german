"""Reading the tutor's lines aloud: the voice model download, synthesis, and the clip cache."""

import io
import threading
import wave

import pytest

from app import speech


class FakePiperVoice:
    """Stands in for a voice: half a second of silence per request."""

    calls: list[str] = []

    def __init__(self, model_path):
        self.name = model_path.name.removesuffix(".onnx")

    @classmethod
    def load(cls, model_path, config_path=None):
        return cls(model_path)

    def synthesize_wav(self, text, wav_file):
        FakePiperVoice.calls.append(f"{self.name}: {text}")
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\0\0" * 11025)


def put_voice(voice: str) -> None:
    speech.TTS_DIR.mkdir(parents=True, exist_ok=True)
    for name in speech.model_files(voice):
        (speech.TTS_DIR / name).write_bytes(b"model")


@pytest.fixture
def voice_model(monkeypatch):
    """The default voice is "downloaded" and loading it gives the fake voice."""
    put_voice(speech.DEFAULT_VOICE)
    FakePiperVoice.calls = []
    monkeypatch.setattr(speech, "PiperVoice", FakePiperVoice)
    return FakePiperVoice


def test_line_is_rendered_as_wav(voice_model):
    audio = speech.synthesize("Wie war dein Wochenende?")
    with wave.open(io.BytesIO(audio)) as clip:
        assert (clip.getnchannels(), clip.getsampwidth(), clip.getframerate()) == (1, 2, 22050)
        assert clip.getnframes() == 11025


def test_repeated_line_is_served_from_the_cache(voice_model):
    first = speech.synthesize("Wie war dein Wochenende?")
    assert speech.synthesize("Wie war dein Wochenende?") == first
    assert voice_model.calls == [f"{speech.DEFAULT_VOICE}: Wie war dein Wochenende?"]


def test_another_voice_does_not_reuse_the_cached_clip(voice_model, monkeypatch):
    speech.synthesize("Wie war dein Wochenende?")
    put_voice("de_DE-kerstin-low")
    monkeypatch.setenv("TTS_VOICE", "de_DE-kerstin-low")
    speech.synthesize("Wie war dein Wochenende?")
    assert voice_model.calls[-1] == "de_DE-kerstin-low: Wie war dein Wochenende?"


def test_missing_model_is_downloaded_in_the_background(monkeypatch):
    started, release, downloads = threading.Event(), threading.Event(), []

    def download():
        downloads.append(1)
        started.set()
        release.wait(5)

    monkeypatch.setattr(speech, "_download_models", download)
    try:
        # The request fails at once instead of waiting for the download...
        with pytest.raises(RuntimeError, match="still downloading"):
            speech.synthesize("Wie war dein Wochenende?")
        assert started.wait(5)
        # ...and asking again while it runs does not start a second download.
        with pytest.raises(RuntimeError, match="still downloading"):
            speech.synthesize("Was hast du zu Mittag gegessen?")
        assert downloads == [1]
    finally:
        release.set()


def test_speech_endpoint_reports_the_download_so_the_ui_can_fall_back(client, monkeypatch):
    monkeypatch.setattr(speech, "_download_models", lambda: None)
    response = client.post("/api/speech", json={"text": "Wie war dein Wochenende?"})
    assert response.status_code == 502
    assert "still downloading" in response.json()["detail"]


def test_speech_endpoint_returns_audio(client, voice_model):
    response = client.post("/api/speech", json={"text": "Wie war dein Wochenende?"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content.startswith(b"RIFF")


def test_download_saves_both_voice_files_and_leaves_no_partial_file(monkeypatch):
    requested = []

    def urlopen(url, context=None):
        requested.append(url)
        return io.BytesIO(b"model-bytes")

    monkeypatch.setattr(speech.urllib.request, "urlopen", urlopen)
    speech._download_models()

    folder = f"{speech.RELEASE_URL}/de/de_DE/thorsten/high"
    assert requested == [f"{folder}/de_DE-thorsten-high.onnx", f"{folder}/de_DE-thorsten-high.onnx.json"]
    assert sorted(p.name for p in speech.TTS_DIR.iterdir()) == sorted(speech.model_files(speech.DEFAULT_VOICE))
    assert (speech.TTS_DIR / "de_DE-thorsten-high.onnx").read_bytes() == b"model-bytes"


def test_download_skips_files_that_are_already_there(monkeypatch):
    model, config = speech.model_files(speech.DEFAULT_VOICE)
    speech.TTS_DIR.mkdir(parents=True)
    (speech.TTS_DIR / model).write_bytes(b"kept")
    monkeypatch.setattr(speech.urllib.request, "urlopen", lambda url, context=None: io.BytesIO(b"new"))
    speech._download_models()
    assert (speech.TTS_DIR / model).read_bytes() == b"kept"
    assert (speech.TTS_DIR / config).read_bytes() == b"new"
