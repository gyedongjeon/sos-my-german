"""The sentences of a saved video, translated into the learner's language when asked for."""

import json
import re

import pytest

from app import translations, videos
from app.db import get_connection
from app.llm import LLMError
from app.videos import Snippet

SPEECH = [
    Snippet(0.0, 3.0, "Guten Morgen."),
    Snippet(3.0, 3.0, "Heute sprechen wir über das Wetter."),
    Snippet(6.0, 3.0, "Es regnet schon seit Tagen."),
]


@pytest.fixture
def youtube(monkeypatch):
    """YouTube serves `youtube.speech` for every video."""

    def transcript(video_id):
        return youtube.speech, "de", False

    youtube.speech = SPEECH
    monkeypatch.setattr(videos, "_transcript", transcript)
    monkeypatch.setattr(videos, "_about", lambda video_id: ("Das Wetter", "Ein Kanal"))
    return youtube


@pytest.fixture
def model(monkeypatch):
    """The model "translates" each numbered sentence it is sent as "<language>: <sentence>"."""

    def complete(system, user, **params):
        complete.calls.append((system, user))
        language = re.search(r"into (\w+)", system).group(1)
        found = re.findall(r"^\[(\d+)\] (.+)$", user, flags=re.MULTILINE)
        return json.dumps({"translations": [{"id": int(i), "text": f"{language}: {text}"} for i, text in found]})

    complete.calls = []
    monkeypatch.setattr(translations, "complete", complete)
    return complete


def add(client) -> dict:
    response = client.post("/api/videos", json={"url": "https://youtu.be/UF8uR6Z6KLc"})
    assert response.status_code == 201, response.text
    return response.json()


def translate(client, video: dict):
    return client.post(f"/api/videos/{video['id']}/translations")


def test_every_sentence_is_translated_into_the_feedback_language(client, youtube, model):
    client.put("/api/settings", json={"feedback_language": "Korean"})
    video = add(client)
    response = translate(client, video)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "language": "Korean",
        "lines": [{"line": line["id"], "text": f"Korean: {line['text']}"} for line in video["lines"]],
    }
    system, user = model.calls[0]
    # The title helps with what the sentences are about.
    assert "Korean" in system and "Das Wetter" in user


def test_a_translation_is_kept_and_not_asked_for_again(client, youtube, model):
    client.put("/api/settings", json={"feedback_language": "Korean"})
    video = add(client)
    first = translate(client, video).json()
    assert translate(client, video).json() == first
    assert len(model.calls) == 1


def test_another_feedback_language_is_translated_on_its_own(client, youtube, model):
    video = add(client)
    client.put("/api/settings", json={"feedback_language": "Korean"})
    translate(client, video)
    client.put("/api/settings", json={"feedback_language": "Japanese"})
    lines = translate(client, video).json()["lines"]
    assert all(line["text"].startswith("Japanese: ") for line in lines)
    assert len(model.calls) == 2


def test_a_long_video_is_translated_a_part_at_a_time(client, youtube, model):
    youtube.speech = [Snippet(i * 3.0, 3.0, f"Das ist Satz Nummer {i}.") for i in range(2 * translations.CHUNK + 5)]
    video = add(client)
    lines = translate(client, video).json()["lines"]
    assert len(lines) == len(video["lines"])
    assert len(model.calls) == 3
    assert all(len(re.findall(r"^\[\d+\]", user, flags=re.MULTILINE)) <= translations.CHUNK for _, user in model.calls)


def test_a_sentence_left_out_by_the_model_is_asked_for_next_time(client, youtube, model, monkeypatch):
    client.put("/api/settings", json={"feedback_language": "Korean"})
    video = add(client)
    first, *rest = video["lines"]

    def skip_the_first(system, user, **params):
        reply = json.loads(model(system, user, **params))
        # One sentence left out, and an id that was not asked for.
        reply["translations"] = [t for t in reply["translations"] if t["id"] != first["id"]] + [{"id": 999, "text": "?"}]
        return json.dumps(reply)

    monkeypatch.setattr(translations, "complete", skip_the_first)
    assert [line["line"] for line in translate(client, video).json()["lines"]] == [line["id"] for line in rest]
    monkeypatch.setattr(translations, "complete", model)
    model.calls.clear()
    assert len(translate(client, video).json()["lines"]) == 3
    # Only the missing sentence was sent.
    assert re.findall(r"^\[(\d+)\]", model.calls[0][1], flags=re.MULTILINE) == [str(first["id"])]


def test_a_translation_that_cannot_be_written_is_reported(client, youtube, monkeypatch):
    def fail(system, user, **params):
        raise LLMError("The LLM provider is not responding.")

    monkeypatch.setattr(translations, "complete", fail)
    response = translate(client, add(client))
    assert response.status_code == 502 and "not responding" in response.json()["detail"]


def test_there_is_nothing_to_translate_into_german(client, youtube, model):
    client.put("/api/settings", json={"feedback_language": "German"})
    response = translate(client, add(client))
    assert response.status_code == 422 and "German" in response.json()["detail"]
    assert model.calls == []


def test_only_a_saved_video_is_translated(client, model):
    assert client.post("/api/videos/999/translations").status_code == 404


def test_deleting_a_video_deletes_its_translations(client, youtube, model):
    video = add(client)
    translate(client, video)
    client.delete(f"/api/videos/{video['id']}")
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM line_translations").fetchone()[0] == 0
