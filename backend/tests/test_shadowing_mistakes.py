"""A sentence not said right after a video is kept with the corrections, to be practised again,
and every try is logged, so the words often not heard can be looked at later."""

import pytest

from app import videos
from app.db import get_connection
from app.videos import Snippet

SPEECH = [
    Snippet(0.0, 4.0, "Dadurch merkst du, wo du noch Lücken hast."),
    Snippet(4.0, 4.0, "Schreib und sprich zur gleichen Zeit."),
]


@pytest.fixture
def video(client, monkeypatch):
    monkeypatch.setattr(videos, "_transcript", lambda video_id: (SPEECH, "de", False))
    monkeypatch.setattr(videos, "_about", lambda video_id: ("Wie man lernt", "Ein Kanal"))
    return client.post("/api/videos", json={"url": "https://youtu.be/UF8uR6Z6KLc"}).json()


def shadow(client, line: dict, said: str) -> dict:
    response = client.post(f"/api/video-lines/{line['id']}/attempts", json={"text": said})
    assert response.status_code == 200, response.text
    return response.json()


def corrections(client) -> list[dict]:
    return client.get("/api/corrections").json()


def test_a_sentence_not_said_right_is_listed_with_the_corrections(client, video):
    line = video["lines"][0]
    shadow(client, line, "Dadurch merkst du wo du noch Locken hast")
    [mistake] = corrections(client)
    assert mistake["id"].startswith("s")
    assert (mistake["original"], mistake["improved"]) == (
        "Dadurch merkst du wo du noch Locken hast",
        "Dadurch merkst du, wo du noch Lücken hast.",
    )
    # The word that was not heard, with what was heard in its place.
    assert mistake["explanation"] == "Not heard: “Lücken” (heard “locken”)."
    # It names the video and the sentence it comes from.
    assert mistake["title"] == "Wie man lernt"
    assert (mistake["video"], mistake["position"]) == (video["id"], 0)
    assert mistake["conversation_id"] is None and mistake["pattern_id"] is None
    assert mistake["practiced"] == 0


def test_words_left_out_are_named_without_anything_heard_in_their_place(client, video):
    shadow(client, video["lines"][1], "Schreib und sprich zur Zeit")
    assert corrections(client)[0]["explanation"] == "Not heard: “gleichen”."


def test_a_sentence_said_right_is_not_listed(client, video):
    shadow(client, video["lines"][1], "schreib und sprich zur gleichen Zeit")
    assert corrections(client) == []


def test_trying_the_same_sentence_again_keeps_one_entry_with_the_last_try(client, video):
    line = video["lines"][1]
    shadow(client, line, "Schreib und sprich zur Zeit")
    shadow(client, line, "Schrei und sprich zur gleichen Zeit")
    [mistake] = corrections(client)
    assert mistake["original"] == "Schrei und sprich zur gleichen Zeit"
    assert mistake["explanation"] == "Not heard: “Schreib” (heard “schrei”)."


def test_a_shadowing_mistake_is_practised_like_any_correction(client, video):
    shadow(client, video["lines"][1], "Schreib und sprich zur Zeit")
    mistake_id = corrections(client)[0]["id"]
    tried = client.post(f"/api/corrections/{mistake_id}/attempts", json={"text": "Schreib und sprich zur gleichen Zeit."})
    assert tried.json()["matched"] is True
    assert corrections(client)[0]["practiced"] == 1
    assert client.delete(f"/api/corrections/{mistake_id}").status_code == 204
    assert corrections(client) == []


def test_a_mistake_outlives_its_video_without_a_link_to_it(client, video):
    shadow(client, video["lines"][1], "Schreib und sprich zur Zeit")
    assert client.delete(f"/api/videos/{video['id']}").status_code == 204
    [mistake] = corrections(client)
    assert (mistake["improved"], mistake["title"]) == ("Schreib und sprich zur gleichen Zeit.", "Wie man lernt")
    assert mistake["video"] is None and mistake["position"] is None
    tried = client.post(f"/api/corrections/{mistake['id']}/attempts", json={"text": "Schreib und sprich zur gleichen Zeit"})
    assert tried.json()["matched"] is True


def test_every_try_is_logged_and_the_log_outlives_the_video(client, video):
    line = video["lines"][1]
    shadow(client, line, "Schreib und sprich zur Zeit")
    shadow(client, line, "Schreib und sprich zur gleichen Zeit")
    client.delete(f"/api/videos/{video['id']}")
    with get_connection() as conn:
        logged = conn.execute("SELECT sentence, said, accuracy FROM shadowing_attempts ORDER BY id").fetchall()
    assert [tuple(row) for row in logged] == [
        ("Schreib und sprich zur gleichen Zeit.", "Schreib und sprich zur Zeit", 83),
        ("Schreib und sprich zur gleichen Zeit.", "Schreib und sprich zur gleichen Zeit", 100),
    ]
