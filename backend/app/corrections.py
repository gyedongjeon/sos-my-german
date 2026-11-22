"""Corrections from saved conversations, practised by saying the better sentence aloud."""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from .conversation import _spoken
from .db import get_connection

router = APIRouter(prefix="/api")

# Speech recognition writes small numbers as figures or as words; both are heard the same. Words
# are compared with "ß" spelled "ss", so "dreißig" is listed as "dreissig".
NUMBERS = dict(
    zip(
        "null eins zwei drei vier fünf sechs sieben acht neun zehn elf zwölf dreizehn vierzehn fünfzehn "
        "sechzehn siebzehn achtzehn neunzehn zwanzig dreissig vierzig fünfzig sechzig siebzig achtzig neunzig".split(),
        [*map(str, range(21)), "30", "40", "50", "60", "70", "80", "90"],
        strict=True,
    )
)
# "zwo" is said for "zwei" to tell it from "drei".
NUMBERS["zwo"] = "2"


class SavedCorrection(BaseModel):
    """A sentence to practise again: a correction made in a saved conversation, or a sentence
    got wrong in pattern practice. It also says how often it was practised since."""

    # "m" and the id of the learner's line it was made on, or "p" and the id of the mistake.
    id: str
    # Where it comes from: one of the two is set. `title` is the conversation's title or the
    # pattern's formula.
    conversation_id: int | None = None
    pattern_id: str | None = None
    title: str
    # For a pattern mistake: the sentence that was to be said in German.
    prompt: str | None = None
    original: str
    improved: str
    explanation: str
    # How many times the better sentence was said correctly, and when it last was.
    practiced: int
    practiced_at: str | None


class AttemptRequest(BaseModel):
    text: str = Field(min_length=1, description="What the learner said, as transcribed.")


class Attempt(BaseModel):
    matched: bool
    # Words of the better sentence that were not heard, in its order.
    missing: list[str]
    practiced: int


def _words(text: str) -> list[str]:
    """The words of a sentence as heard: "'s" spelled out, so "geht's" equals "geht es", "ß"
    as "ss", as Swiss German writes it, and small numbers as figures, so "drei" equals "3"."""
    words: list[str] = []
    for word in _spoken(text):
        word = word.replace("ß", "ss")
        if word.endswith("'s") and len(word) > 2:
            # Spoken German shortens "es" after a verb or a question word: "wie geht's?"
            word = word.removesuffix("'s") + " es"
        words.extend(NUMBERS.get(part, part) for part in word.split())
    return words


def _contains(said: list[str], wanted: list[str]) -> bool:
    """Whether the wanted words were said one after another, in order."""
    return any(said[i : i + len(wanted)] == wanted for i in range(len(said) - len(wanted) + 1))


def _missing(said: list[str], wanted: list[str]) -> list[str]:
    left = list(said)
    missing = []
    for word in wanted:
        if word in left:
            left.remove(word)
        else:
            missing.append(word)
    return missing


# Where each kind of correction is stored, by the letter its id starts with: the table, and the
# column that holds the better sentence.
KINDS = {"m": ("messages", "correction_improved"), "p": ("pattern_mistakes", "improved")}
NOW = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"


def _locate(correction_id: str) -> tuple[str, str, int]:
    """The table, the column of the better sentence, and the row a correction's id stands for."""
    kind, number = correction_id[:1], correction_id[1:]
    if kind not in KINDS or not number.isdecimal():
        raise HTTPException(status_code=404, detail="Correction not found")
    return (*KINDS[kind], int(number))


@router.get("/corrections", response_model=list[SavedCorrection])
def list_corrections() -> list[SavedCorrection]:
    """Every correction of the saved conversations and every sentence got wrong in pattern
    practice, newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT 'm' || m.id AS id, m.conversation_id, NULL AS pattern_id, c.title, NULL AS prompt,
                   m.correction_original AS original, m.correction_improved AS improved,
                   m.correction_explanation AS explanation, m.practiced, m.practiced_at,
                   COALESCE(m.corrected_at, c.started_at) AS made_at, m.id AS row
            FROM messages m JOIN conversations c ON c.id = m.conversation_id
            WHERE m.correction_improved IS NOT NULL AND m.dismissed = 0
            UNION ALL
            SELECT 'p' || id, NULL, pattern_id, pattern, prompt, said, improved, explanation,
                   practiced, practiced_at, created_at, id
            FROM pattern_mistakes
            ORDER BY made_at DESC, row DESC
            """
        ).fetchall()
    return [SavedCorrection(**{key: row[key] for key in row.keys() if key not in ("made_at", "row")}) for row in rows]


@router.post("/corrections/{correction_id}/attempts", response_model=Attempt)
def attempt(correction_id: str, body: AttemptRequest) -> Attempt:
    """Check what the learner said against the better sentence; a match is counted as practice."""
    table, improved, row_id = _locate(correction_id)
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {improved} AS improved, practiced FROM {table} WHERE id = ? AND {improved} IS NOT NULL", (row_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Correction not found")
        said, wanted = _words(body.text), _words(row["improved"])
        matched = _contains(said, wanted)
        if matched:
            conn.execute(f"UPDATE {table} SET practiced = practiced + 1, practiced_at = {NOW} WHERE id = ?", (row_id,))
    return Attempt(
        matched=matched,
        missing=[] if matched else _missing(said, wanted),
        practiced=row["practiced"] + matched,
    )


@router.delete("/corrections/{correction_id}", status_code=204)
def remove(correction_id: str) -> Response:
    """Take a correction off the list. One made in a conversation stays in that conversation."""
    table, improved, row_id = _locate(correction_id)
    with get_connection() as conn:
        if table == "messages":
            gone = conn.execute(
                f"UPDATE messages SET dismissed = 1 WHERE id = ? AND {improved} IS NOT NULL AND dismissed = 0",
                (row_id,),
            )
        else:
            gone = conn.execute("DELETE FROM pattern_mistakes WHERE id = ?", (row_id,))
    if gone.rowcount == 0:
        raise HTTPException(status_code=404, detail="Correction not found")
    return Response(status_code=204)


def keep_mistake(pattern_id: str, pattern: str, prompt: str, said: str, improved: str, explanation: str) -> None:
    """Keep a sentence got wrong in pattern practice. A new wrong try at the same sentence
    replaces what was said, and it has to be practised again."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pattern_mistakes (pattern_id, pattern, prompt, said, improved, explanation)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (pattern_id, prompt) DO UPDATE SET
                pattern = excluded.pattern, said = excluded.said, improved = excluded.improved,
                explanation = excluded.explanation, practiced = 0, practiced_at = NULL,
                created_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            """,
            (pattern_id, pattern, prompt, said, improved, explanation),
        )
