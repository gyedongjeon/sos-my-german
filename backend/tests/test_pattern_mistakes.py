"""A sentence got wrong in pattern practice is kept with the corrections, to be practised again."""

import json

import pytest

from app import conversation, patterns

WRONG = {"correct": False, "improved": "Ich hätte früher gehen sollen.", "explanation": "sollen은 원형 그대로 씁니다."}
ATTEMPT = {"prompt": "더 일찍 떠났어야 했어.", "answer": "Ich hätte früher gehen sollen.", "said": "Ich hätte früher gehen gesollt."}


@pytest.fixture
def judge(monkeypatch):
    """The model judges every sentence with `judge.verdict`."""

    def complete(system, user, **params):
        return json.dumps(complete.verdict)

    complete.verdict = dict(WRONG)
    monkeypatch.setattr(patterns, "complete", complete)
    return complete


def check(client, **changes) -> dict:
    response = client.post("/api/patterns/haette-sollen/check", json={**ATTEMPT, **changes})
    assert response.status_code == 200, response.text
    return response.json()


def test_a_sentence_got_wrong_is_listed_with_the_corrections(client, judge):
    check(client)
    listed = client.get("/api/corrections").json()
    assert len(listed) == 1
    mistake = listed[0]
    assert (mistake["original"], mistake["improved"], mistake["explanation"]) == (
        "Ich hätte früher gehen gesollt.",
        "Ich hätte früher gehen sollen.",
        WRONG["explanation"],
    )
    # It names the pattern it comes from, and shows the sentence that was asked for.
    assert mistake["pattern_id"] == "haette-sollen" and mistake["conversation_id"] is None
    assert mistake["title"] == "hätte + infinitive + sollen"
    assert mistake["prompt"] == ATTEMPT["prompt"]
    assert mistake["practiced"] == 0 and mistake["practiced_at"] is None


def test_a_sentence_got_right_is_not_listed(client, judge):
    judge.verdict = {"correct": True, "improved": "Ich hätte eher losgehen sollen.", "explanation": None}
    check(client, said="Ich hätte eher losgehen sollen.")
    # Nor is the model answer said as it is, which needs no model.
    check(client, said="ich hätte früher gehen sollen")
    assert client.get("/api/corrections").json() == []


def test_trying_the_same_sentence_again_keeps_one_entry_with_the_last_try(client, judge):
    check(client)
    judge.verdict = {**WRONG, "explanation": "hätte가 빠졌습니다."}
    check(client, said="Ich sollte früher gehen.")
    listed = client.get("/api/corrections").json()
    assert len(listed) == 1
    assert listed[0]["original"] == "Ich sollte früher gehen." and listed[0]["explanation"] == "hätte가 빠졌습니다."
    # Another sentence of the same pattern is another entry.
    check(client, prompt="그에게 말했어야 했어.", answer="Ich hätte es ihm sagen sollen.", said="Ich hätte es ihm gesagt sollen.")
    assert len(client.get("/api/corrections").json()) == 2


def test_getting_it_right_later_in_the_round_keeps_the_entry(client, judge):
    """Right at the second try is still a sentence worth practising again."""
    check(client)
    check(client, said="Ich hätte früher gehen sollen.")
    assert len(client.get("/api/corrections").json()) == 1


def test_a_mistake_is_practised_by_saying_the_better_sentence(client, judge):
    check(client)
    mistake = client.get("/api/corrections").json()[0]
    missed = client.post(f"/api/corrections/{mistake['id']}/attempts", json={"text": "Ich hätte früher gehen gesollt"})
    assert missed.json() == {"matched": False, "missing": ["sollen"], "practiced": 0}
    said = client.post(f"/api/corrections/{mistake['id']}/attempts", json={"text": "Ich hätte früher gehen sollen."})
    assert said.json() == {"matched": True, "missing": [], "practiced": 1}
    kept = client.get("/api/corrections").json()[0]
    assert kept["practiced"] == 1 and kept["practiced_at"].endswith("Z")


def test_mistakes_and_conversation_corrections_are_listed_together_newest_first(client, judge, monkeypatch):
    fix = {"original": "Ich gehe", "improved": "Ich bin gegangen", "explanation": "Perfekt."}
    monkeypatch.setattr(
        conversation, "complete", lambda system, user, **params: json.dumps({"reply": "Ach so!", "correction": fix})
    )
    started = client.post("/api/conversations", json={"topic_id": 1}).json()
    client.post(f"/api/conversations/{started['id']}/messages", json={"text": "Ich gehe an den Strand."})
    client.post(f"/api/conversations/{started['id']}/reply")
    check(client)
    listed = client.get("/api/corrections").json()
    assert [(c["conversation_id"], c["pattern_id"]) for c in listed] == [(None, "haette-sollen"), (started["id"], None)]
    assert len({c["id"] for c in listed}) == 2
    # Each is practised under its own id.
    for correction in listed:
        attempt = client.post(f"/api/corrections/{correction['id']}/attempts", json={"text": correction["improved"]})
        assert attempt.json()["matched"] is True


def test_a_correction_can_be_removed_from_the_list(client, judge):
    check(client)
    mistake = client.get("/api/corrections").json()[0]
    assert client.delete(f"/api/corrections/{mistake['id']}").status_code == 204
    assert client.get("/api/corrections").json() == []
    assert client.delete(f"/api/corrections/{mistake['id']}").status_code == 404
    assert client.delete("/api/corrections/nonsense").status_code == 404
