"""Local text-to-speech with Piper (piper-tts); no API key, runs on this machine."""

import hashlib
import io
import os
import shutil
import ssl
import threading
import urllib.request
import wave

import certifi
from piper import PiperVoice

from .downloads import Download
from .paths import DATA_DIR

TTS_DIR = DATA_DIR / "tts"
CACHE_DIR = TTS_DIR / "cache"
# Piper's voices, pinned to a release of the collection; a voice is downloaded on first use.
RELEASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
# A German voice of high quality (~114 MB). Others are named the same way, as
# <language>_<REGION>-<name>-<quality>, for example "de_DE-kerstin-low".
DEFAULT_VOICE = "de_DE-thorsten-high"

# Size of the default voice's two files, for showing download progress.
EXPECTED_BYTES = 113_895_201 + 4_875

_voices: dict[str, PiperVoice] = {}
_lock = threading.Lock()


def _voice() -> str:
    return os.environ.get("TTS_VOICE", "").strip() or DEFAULT_VOICE


def model_files(voice: str) -> tuple[str, str]:
    """The voice model and its settings, as named in the collection and on disk."""
    return f"{voice}.onnx", f"{voice}.onnx.json"


def _voice_url(voice: str, name: str) -> str:
    """Where a file of a voice is: the collection keeps "de_DE-thorsten-high" under
    de/de_DE/thorsten/high/."""
    locale, speaker, quality = voice.split("-", 2)
    return f"{RELEASE_URL}/{locale.split('_')[0]}/{locale}/{speaker}/{quality}/{name}"


def _is_downloaded() -> bool:
    return all((TTS_DIR / name).exists() for name in model_files(_voice()))


def _downloaded_bytes() -> int:
    """Bytes of the voice's files on disk, counting a file that is still being downloaded."""
    names = [candidate for name in model_files(_voice()) for candidate in (name, f"{name}.part")]
    return sum((TTS_DIR / name).stat().st_size for name in names if (TTS_DIR / name).exists())


def _download_models() -> None:
    TTS_DIR.mkdir(parents=True, exist_ok=True)
    voice = _voice()
    for name in model_files(voice):
        path = TTS_DIR / name
        if not path.exists():
            # Download to a temporary name so an interrupted download is not reused.
            partial = path.with_name(path.name + ".part")
            # certifi's CA bundle: some Python installs ship without root certificates.
            tls = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(_voice_url(voice, name), context=tls) as response:
                with partial.open("wb") as out:
                    shutil.copyfileobj(response, out)
            partial.rename(path)


# The lambdas look the functions up when called, so tests can replace them.
model_download = Download(
    "voice",
    "Partner's voice",
    is_ready=lambda: _is_downloaded(),
    fetch=lambda: _download_models(),
    measure=lambda: _downloaded_bytes(),
    total=EXPECTED_BYTES if _voice() == DEFAULT_VOICE else None,
)


def _get_voice(voice: str) -> PiperVoice:
    """Return the loaded voice. Raises while its files are still being downloaded."""
    if voice not in _voices:
        if not _is_downloaded():
            # The download takes minutes, so it runs in the background instead of holding the
            # request; the caller reports the failure and the UI uses the browser voice meanwhile.
            model_download.start()
            raise RuntimeError("the voice model is still downloading")
        model, config = model_files(voice)
        _voices[voice] = PiperVoice.load(TTS_DIR / model, config_path=TTS_DIR / config)
    return _voices[voice]


def synthesize(text: str) -> bytes:
    """Return WAV audio of the text spoken in German."""
    voice = _voice()
    # Lines repeat across sessions, so keep each rendered clip on disk.
    key = hashlib.sha256(f"{voice}\n{text}".encode()).hexdigest()
    cached = CACHE_DIR / f"{key}.wav"
    if cached.exists():
        return cached.read_bytes()

    buffer = io.BytesIO()
    # One synthesis at a time: the model is loaded once and shared.
    with _lock:
        # Loaded first: a WAV file closed before anything was written to it raises.
        loaded = _get_voice(voice)
        with wave.open(buffer, "wb") as wav:
            loaded.synthesize_wav(text, wav)
    audio = buffer.getvalue()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(audio)
    return audio
