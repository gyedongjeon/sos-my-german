"""Shadowing a sentence of a video, and searching the saved subtitles."""

import pytest

from app import videos
from app.db import get_connection, init_db
from app.videos import Snippet

SPEECH = [
    Snippet(0.0, 4.0, "Ehrlich gesagt habe ich nie studiert."),
    Snippet(4.0, 4.0, "Und so geht's -- jedenfalls bei mir."),
    Snippet(8.0, 3.0, "Heute will ich euch drei Geschichten erzählen."),
]
TALK = [Snippet(0.0, 3.0, "Ich will euch ein Geheimnis erzählen."), Snippet(3.0, 3.0, "Es ist 100% wahr.")]


@pytest.fixture
def saved(client, monkeypatch):
    """Two saved videos; resolves with them, the speech first."""
    tracks = {"UF8uR6Z6KLc": SPEECH, "arj7oStGLkU": TALK}
    titles = {"UF8uR6Z6KLc": ("Eine Rede", "Uni"), "arj7oStGLkU": ("Ein Vortrag", "TED")}
    monkeypatch.setattr(videos, "_transcript", lambda video_id: (tracks[video_id], "de", False))
    monkeypatch.setattr(videos, "_about", lambda video_id: titles[video_id])
    return [client.post("/api/videos", json={"url": f"https://youtu.be/{video_id}"}).json() for video_id in tracks]


def shadow(client, line: dict, said: str) -> dict:
    response = client.post(f"/api/video-lines/{line['id']}/attempts", json={"text": said})
    assert response.status_code == 200, response.text
    return response.json()


def test_sentences_have_an_id_and_start_unshadowed(saved):
    lines = saved[0]["lines"]
    assert len({line["id"] for line in lines}) == 3
    assert all(line["shadowed"] == 0 and line["best"] is None for line in lines)


def test_a_sentence_said_as_it_is_scores_full_marks(client, saved):
    line = saved[0]["lines"][0]
    # Spoken, so punctuation and capitals do not matter.
    result = shadow(client, line, "ehrlich gesagt habe ich nie studiert")
    assert result["accuracy"] == 100
    assert [word["text"] for word in result["words"]] == line["text"].split()
    assert all(word["heard"] for word in result["words"])
    assert (result["shadowed"], result["best"]) == (1, 100)


def test_the_words_that_were_not_heard_are_marked(client, saved):
    result = shadow(client, saved[0]["lines"][0], "Ehrlich gesagt hab ich nie studiert")
    assert [word["text"] for word in result["words"] if not word["heard"]] == ["habe"]
    # Five of its six words.
    assert result["accuracy"] == 83


def test_a_word_said_once_does_not_count_twice(client, saved):
    result = shadow(client, saved[1]["lines"][0], "Ich will ein Geheimnis erzählen")
    assert [word["heard"] for word in result["words"]] == [True, True, False, True, True, True]


def test_short_forms_and_marks_that_are_not_words_are_handled(client, saved):
    line = saved[0]["lines"][1]
    result = shadow(client, line, "Und so geht es jedenfalls bei mir")
    assert result["accuracy"] == 100
    # "--" is not something to say, so it does not count for or against.
    assert len(result["words"]) == len(line["text"].split())


def test_the_best_try_is_kept_with_the_sentence(client, saved):
    line = saved[0]["lines"][0]
    shadow(client, line, "ehrlich gesagt habe ich nie studiert")
    worse = shadow(client, line, "ehrlich gesagt")
    assert worse["accuracy"] == 33 and (worse["shadowed"], worse["best"]) == (2, 100)
    kept = client.get(f"/api/videos/{saved[0]['id']}").json()["lines"][0]
    assert (kept["shadowed"], kept["best"]) == (2, 100)


def test_only_a_saved_sentence_can_be_shadowed(client, saved):
    assert client.post("/api/video-lines/999/attempts", json={"text": "Hallo."}).status_code == 404
    line = saved[0]["lines"][0]
    assert client.post(f"/api/video-lines/{line['id']}/attempts", json={"text": ""}).status_code == 422


def test_the_subtitles_of_all_videos_are_searched(client, saved):
    found = client.get("/api/video-lines", params={"q": "euch"}).json()
    assert [(hit["title"], hit["position"], hit["text"]) for hit in found] == [
        ("Ein Vortrag", 0, "Ich will euch ein Geheimnis erzählen."),
        ("Eine Rede", 2, "Heute will ich euch drei Geschichten erzählen."),
    ]
    assert found[0]["video"] == saved[1]["id"] and found[0]["video_id"] == "arj7oStGLkU"
    assert found[1]["start"] == 8.0


def test_the_search_ignores_capitals_and_takes_signs_as_they_are(client, saved):
    assert len(client.get("/api/video-lines", params={"q": "EHRLICH GESAGT"}).json()) == 1
    # Umlauts too, which SQLite alone compares by case.
    assert len(client.get("/api/video-lines", params={"q": "ERZÄHLEN"}).json()) == 2
    # "%" and "_" are looked for, not used as wildcards.
    assert [hit["text"] for hit in client.get("/api/video-lines", params={"q": "100%"}).json()] == ["Es ist 100% wahr."]
    assert client.get("/api/video-lines", params={"q": "w_hr"}).json() == []


def test_a_search_needs_something_to_look_for(client, saved):
    assert client.get("/api/video-lines", params={"q": " "}).status_code == 422
    assert client.get("/api/video-lines", params={"q": "zebra"}).json() == []


def test_a_database_from_before_shadowing_gains_the_columns(client, saved):
    with get_connection() as conn:
        conn.execute("ALTER TABLE video_lines DROP COLUMN shadowed")
        conn.execute("ALTER TABLE video_lines DROP COLUMN best")
    init_db()
    assert client.get(f"/api/videos/{saved[0]['id']}").json()["lines"][0]["shadowed"] == 0


def test_a_number_counts_whether_it_was_heard_as_a_word_or_as_a_figure(client, saved):
    # Speech recognition often writes "3" where "drei" was said.
    result = shadow(client, saved[0]["lines"][2], "Heute will ich euch 3 Geschichten erzählen")
    assert result["accuracy"] == 100
    assert shadow(client, saved[1]["lines"][1], "Es ist hundert Prozent wahr")["accuracy"] < 100
