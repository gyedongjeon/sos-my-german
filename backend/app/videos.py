"""Videos to study with: a YouTube video is watched in its own player; its subtitles are kept
here, cut into sentences, so each sentence can be listened to on its own."""

import json
import re
import sqlite3
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html import unescape

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
    YouTubeTranscriptApiException,
)

from .corrections import _words
from .db import get_connection
from .llm import LLMError, complete, parse_json_reply
from .pattern_list import LEVELS

router = APIRouter(prefix="/api")

VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
# Path prefixes under which youtube.com names a video: /embed/<id>, /shorts/<id>, /live/<id>.
PATH_KINDS = {"embed", "shorts", "live", "v"}
GERMAN = ["de", "de-DE", "de-AT", "de-CH"]

# What subtitles carry besides speech: [Musik], (Gelächter), speaker arrows, music notes.
NOISE = re.compile(r"\[[^\]]*\]|\([A-ZÄÖÜ][a-zäöüß]+(?: [a-zäöüß]+)?\)|>>|♪|♫")
SENTENCE_END = re.compile(r"[.!?][\"'”’)\]]*$")
# A full stop after one of these does not end a sentence.
ABBREVIATIONS = {"dr.", "hr.", "fr.", "prof.", "nr.", "ca.", "bzw.", "usw.", "etc.", "evtl.", "ggf.", "vgl.", "z.b.", "d.h.", "u.a."}
# Subtitles with fewer sentence ends than one in this many words were written without
# punctuation (typical of automatic ones), so they cannot be cut into sentences.
WORDS_PER_END = 40
# A silence of this many seconds between two subtitle lines ends a sentence left without a full stop.
PAUSE = 1.5
# A sentence longer than this is cut at its next comma, and at the hard limit without one.
LONG, TOO_LONG = 40, 60


class NoSubtitles(Exception):
    """Raised with a user-facing message when a video's German subtitles cannot be had."""


@dataclass(frozen=True)
class Snippet:
    """One subtitle line as YouTube shows it."""

    start: float
    duration: float
    text: str


class Line(BaseModel):
    """One sentence of a video, with the part of the video in which it is said (in seconds)."""

    start: float
    end: float
    text: str


class SavedLine(Line):
    """A sentence of a saved video, and how the learner has done at shadowing it."""

    id: int
    # How often it was shadowed, and the best score so far (0-100); None before the first try.
    shadowed: int = 0
    best: int | None = None


class Said(BaseModel):
    text: str = Field(min_length=1, description="What the learner said, as transcribed.")


class ShadowedWord(BaseModel):
    text: str
    heard: bool


class Shadowed(BaseModel):
    """How one try at saying a sentence after the video went."""

    # The share of the sentence's words that were heard, 0-100.
    accuracy: int
    # The sentence word by word, as it is written, with whether each was heard.
    words: list[ShadowedWord]
    shadowed: int
    best: int


class Hit(BaseModel):
    """A sentence found in the saved subtitles."""

    id: int
    # The saved video it is in (our id and YouTube's), and where.
    video: int
    video_id: str
    title: str
    position: int
    start: float
    text: str


class VideoSummary(BaseModel):
    id: int
    # YouTube's own id of the video, which its player is given.
    video_id: str
    title: str
    channel: str
    # The language code of the subtitles, and whether YouTube made them automatically.
    language: str
    generated: bool
    added_at: str
    sentences: int
    # The CEFR level of its German, A1 to C2; None while it has none.
    level: str | None = None


class Video(BaseModel):
    id: int
    video_id: str
    title: str
    channel: str
    language: str
    generated: bool
    added_at: str
    level: str | None = None
    lines: list[SavedLine]


class NewVideo(BaseModel):
    url: str


class Level(BaseModel):
    level: str | None


class Estimate(BaseModel):
    level: str = Field(description="The CEFR level a learner needs to follow the video: A1, A2, B1, B2, C1 or C2.")


LEVEL_PROMPT = """\
You are a German teacher choosing videos for learners. You get sentences taken from the
start, the middle, and the end of a video's subtitles, and how fast it is spoken. Estimate the
CEFR level a learner needs to follow the video by ear and to repeat its sentences: A1, A2, B1,
B2, C1 or C2. Go by the vocabulary, the length and build of the sentences, how much is idiom or
specialist language, and the speed: around 120 words a minute is slow and clear, 150 is
ordinary speech, and 180 or more is fast. Dialect or strongly regional speech makes a video harder.

Reply with a single JSON object matching this schema, and nothing else:
{schema}"""

# How much of the subtitles the model reads to estimate a level, in characters.
SAMPLE = 2400


def _take(stretch: list[Line], limit: int, from_end: bool = False) -> str:
    """As many whole sentences of a stretch as fit the limit, from its start or up to its end."""
    picked: list[str] = []
    for line in reversed(stretch) if from_end else stretch:
        if sum(map(len, picked)) + len(line.text) > limit:
            break
        picked.append(line.text)
    return " ".join(reversed(picked) if from_end else picked)


def _sample(lines: list[Line]) -> str:
    """Sentences from all through a video, and its speed, for estimating its level."""
    words = sum(len(line.text.split()) for line in lines)
    # From the first word to the last, pauses included: the pace a listener has to keep up with.
    spoken = lines[-1].end - lines[0].start if lines else 0
    speed = f"Spoken at about {round(words / spoken * 60)} words a minute." if spoken > 0 else ""
    third, limit = max(1, len(lines) // 3), SAMPLE // 3
    parts = [
        _take(lines[:third], limit),
        _take(lines[third : 2 * third], limit),
        _take(lines[2 * third :], limit, from_end=True),
    ]
    return f"{speed}\n\n" + "\n…\n".join(part for part in parts if part)


def _estimate(lines: list[Line]) -> str | None:
    """The level the model gives a video; None when its answer is not a level. Raises LLMError
    when the model cannot be asked."""
    reply = complete(
        LEVEL_PROMPT.format(schema=Estimate.model_json_schema()),
        _sample(lines),
        max_tokens=1000,
        response_format={"type": "json_object"},
        reasoning_effort="low",
    )
    level = parse_json_reply(reply, Estimate).level.strip().upper()
    return level if level in LEVELS else None


def video_id_of(url: str) -> str | None:
    """The video a YouTube link leads to, or None when it is not a link to a YouTube video."""
    parts = urllib.parse.urlsplit(url.strip())
    host = (parts.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    path = [part for part in parts.path.split("/") if part]
    found = None
    if host == "youtu.be" and path:
        found = path[0]
    elif host in ("youtube.com", "youtube-nocookie.com", "music.youtube.com"):
        if path[:1] == ["watch"]:
            found = urllib.parse.parse_qs(parts.query).get("v", [None])[0]
        elif len(path) >= 2 and path[0] in PATH_KINDS:
            found = path[1]
    return found if found and VIDEO_ID.fullmatch(found) else None


def _clean(text: str) -> str:
    return " ".join(NOISE.sub(" ", unescape(text)).split())


def sentences(snippets: list[Snippet]) -> list[Line]:
    """Cut subtitles into sentences. A subtitle line breaks where it fits on the screen, not
    where a sentence ends, so the lines are joined and cut again at the sentence ends; a
    word's time is taken from how far into its line it stands."""
    kept = [(snippet, _clean(snippet.text)) for snippet in snippets]
    kept = [(snippet, text) for snippet, text in kept if text]
    # (word, the time it is said at, the time its subtitle line ends)
    words: list[tuple[str, float, float]] = []
    for i, (snippet, text) in enumerate(kept):
        end = snippet.start + snippet.duration
        if i + 1 < len(kept) and snippet.start < kept[i + 1][0].start < end:
            # Automatic subtitles stay on screen while the next line is already spoken.
            end = kept[i + 1][0].start
        at = 0
        for word in text.split():
            at = text.index(word, at)
            words.append((word, snippet.start + (end - snippet.start) * at / len(text), end))
            at += len(word)
    ends = sum(1 for word, _, _ in words if SENTENCE_END.search(word))
    if ends * WORDS_PER_END < len(words):
        return [
            Line(start=snippet.start, end=words_end, text=text)
            for (snippet, text), words_end in zip(kept, _line_ends(kept), strict=True)
        ]

    lines: list[Line] = []
    current: list[tuple[str, float, float]] = []
    for word in words:
        if current and word[1] - current[-1][2] >= PAUSE:
            lines.append(Line(start=current[0][1], end=current[-1][2], text=" ".join(w for w, _, _ in current)))
            current = []
        current.append(word)
        text = word[0]
        full = bool(SENTENCE_END.search(text)) and text.lower() not in ABBREVIATIONS
        if full or len(current) >= TOO_LONG or (len(current) >= LONG and text.endswith(",")):
            lines.append(Line(start=current[0][1], end=current[-1][2], text=" ".join(w for w, _, _ in current)))
            current = []
    if current:
        lines.append(Line(start=current[0][1], end=current[-1][2], text=" ".join(w for w, _, _ in current)))
    for line, following in zip(lines, lines[1:], strict=False):
        # A sentence ends where the next one starts, unless a pause comes first.
        if following.start > line.start:
            line.end = min(line.end, following.start)
    return lines


def _line_ends(kept: list[tuple[Snippet, str]]) -> list[float]:
    ends = []
    for i, (snippet, _) in enumerate(kept):
        end = snippet.start + snippet.duration
        if i + 1 < len(kept) and snippet.start < kept[i + 1][0].start < end:
            end = kept[i + 1][0].start
        ends.append(end)
    return ends


def _transcript(video_id: str) -> tuple[list[Snippet], str, bool]:
    """The German subtitles of a video: the lines, their language code, and whether they were
    made automatically. Subtitles written by a person are preferred."""
    try:
        track = YouTubeTranscriptApi().list(video_id).find_transcript(GERMAN)
        fetched = track.fetch()
    except (NoTranscriptFound, TranscriptsDisabled) as e:
        raise NoSubtitles("This video has no German subtitles.") from e
    except VideoUnavailable as e:
        raise NoSubtitles("This video does not exist or is not available.") from e
    except YouTubeTranscriptApiException as e:
        raise NoSubtitles(f"The subtitles could not be read from YouTube ({type(e).__name__}). Try again later.") from e
    except Exception as e:
        # Offline, or YouTube answered with something the library does not expect.
        raise NoSubtitles(f"YouTube could not be reached: {e}") from e
    return [Snippet(s.start, s.duration, s.text) for s in fetched], track.language_code, track.is_generated


def _about(video_id: str) -> tuple[str, str]:
    """The title and the channel of a video, from YouTube's public embedding information;
    empty when it cannot be had, which does not keep the video from being saved."""
    watch = urllib.parse.quote(f"https://www.youtube.com/watch?v={video_id}", safe="")
    try:
        with urllib.request.urlopen(f"https://www.youtube.com/oembed?url={watch}&format=json", timeout=10) as reply:
            about = json.load(reply)
        return str(about.get("title") or "").strip(), str(about.get("author_name") or "").strip()
    except Exception:
        return "", ""


def _load(conn: sqlite3.Connection, where: str, value: object) -> Video | None:
    found = conn.execute(f"SELECT * FROM videos WHERE {where} = ?", (value,)).fetchone()
    if found is None:
        return None
    rows = conn.execute(
        "SELECT id, start, end, text, shadowed, best FROM video_lines WHERE video = ? ORDER BY position",
        (found["id"],),
    ).fetchall()
    return Video(**dict(found), lines=[SavedLine(**dict(row)) for row in rows])


@router.get("/videos", response_model=list[VideoSummary])
def list_videos() -> list[VideoSummary]:
    """The saved videos, newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT v.*, COUNT(l.id) AS sentences
            FROM videos v LEFT JOIN video_lines l ON l.video = v.id
            GROUP BY v.id ORDER BY v.id DESC
            """
        ).fetchall()
    return [VideoSummary(**dict(row)) for row in rows]


@router.post("/videos", response_model=Video, status_code=201)
def add_video(body: NewVideo, response: Response) -> Video:
    """Save a YouTube video to study with: its title and its German subtitles, as sentences.
    The video itself is not downloaded; it is played by YouTube's player."""
    video_id = video_id_of(body.url)
    if video_id is None:
        raise HTTPException(status_code=422, detail="This is not a link to a YouTube video.")
    with get_connection() as conn:
        if saved := _load(conn, "video_id", video_id):
            response.status_code = 200
            return saved
    try:
        snippets, language, generated = _transcript(video_id)
    except NoSubtitles as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    lines = sentences(snippets)
    if not lines:
        raise HTTPException(status_code=422, detail="This video has no German subtitles.")
    title, channel = _about(video_id)
    try:
        level = _estimate(lines)
    except LLMError:
        # No model, or it did not answer: the video is saved all the same, without a level.
        level = None
    with get_connection() as conn:
        created = conn.execute(
            "INSERT INTO videos (video_id, title, channel, language, generated, level) VALUES (?, ?, ?, ?, ?, ?)",
            (video_id, title or f"YouTube video {video_id}", channel, language, generated, level),
        )
        conn.executemany(
            "INSERT INTO video_lines (video, position, start, end, text) VALUES (?, ?, ?, ?, ?)",
            [(created.lastrowid, i, line.start, line.end, line.text) for i, line in enumerate(lines)],
        )
        return _load(conn, "id", created.lastrowid)


@router.get("/videos/{video}", response_model=Video)
def get_video(video: int) -> Video:
    with get_connection() as conn:
        found = _load(conn, "id", video)
    if found is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return found


@router.put("/videos/{video}/level", response_model=Video)
def set_level(video: int, body: Level) -> Video:
    """Set a video's level by hand, or clear it."""
    if body.level is not None and body.level not in LEVELS:
        raise HTTPException(status_code=422, detail=f"A level is one of {', '.join(LEVELS)}.")
    with get_connection() as conn:
        changed = conn.execute("UPDATE videos SET level = ? WHERE id = ?", (body.level, video))
        if changed.rowcount == 0:
            raise HTTPException(status_code=404, detail="Video not found")
        return _load(conn, "id", video)


@router.post("/videos/{video}/level", response_model=Video)
def estimate_level(video: int) -> Video:
    """Have a video's level estimated again from its subtitles."""
    found = get_video(video)
    try:
        level = _estimate(found.lines)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=f"Could not estimate the level: {e}") from e
    if level is None:
        raise HTTPException(status_code=502, detail="Could not estimate the level: the model gave no level.")
    with get_connection() as conn:
        conn.execute("UPDATE videos SET level = ? WHERE id = ?", (level, video))
        return _load(conn, "id", video)


@router.delete("/videos/{video}", status_code=204)
def delete_video(video: int) -> Response:
    """Remove a saved video and its subtitles."""
    with get_connection() as conn:
        deleted = conn.execute("DELETE FROM videos WHERE id = ?", (video,))
    if deleted.rowcount == 0:
        raise HTTPException(status_code=404, detail="Video not found")
    return Response(status_code=204)


# The most sentences a search returns.
MAX_HITS = 50


@router.get("/video-lines", response_model=list[Hit])
def search_lines(q: str = Query(min_length=1, max_length=200)) -> list[Hit]:
    """The sentences of all saved videos that contain a word or phrase, newest video first."""
    phrase = " ".join(q.split())
    if not phrase:
        raise HTTPException(status_code=422, detail="Type a word or a phrase to look for.")
    # The phrase is looked for as it is: "%" and "_" are not wildcards here.
    escaped = phrase.casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    with get_connection() as conn:
        # SQLite ignores the case of ASCII letters only; "Ä" and "ä" are told apart.
        conn.create_function("casefold", 1, lambda text: text.casefold(), deterministic=True)
        rows = conn.execute(
            """
            SELECT l.id, l.video, v.video_id, v.title, l.position, l.start, l.text
            FROM video_lines l JOIN videos v ON v.id = l.video
            WHERE casefold(l.text) LIKE ? ESCAPE '\\'
            ORDER BY v.id DESC, l.position LIMIT ?
            """,
            (f"%{escaped}%", MAX_HITS),
        ).fetchall()
    return [Hit(**dict(row)) for row in rows]


@router.post("/video-lines/{line}/attempts", response_model=Shadowed)
def shadow(line: int, body: Said) -> Shadowed:
    """Compare what the learner said after the video with the sentence, word by word."""
    with get_connection() as conn:
        found = conn.execute("SELECT text, shadowed, best FROM video_lines WHERE id = ?", (line,)).fetchone()
        if found is None:
            raise HTTPException(status_code=404, detail="Sentence not found")
        left = _words(body.text)
        words, counted, heard_count = [], 0, 0
        for written in found["text"].split():
            # A short form is two words to say; a dash or a lone quotation mark is none.
            spoken = _words(written)
            heard = all(word in left for word in spoken)
            if heard:
                for word in spoken:
                    left.remove(word)
            if spoken:
                counted += 1
                heard_count += heard
            words.append(ShadowedWord(text=written, heard=heard))
        accuracy = int(100 * heard_count / counted + 0.5) if counted else 0
        best = max(accuracy, found["best"] or 0)
        conn.execute("UPDATE video_lines SET shadowed = shadowed + 1, best = ? WHERE id = ?", (best, line))
    return Shadowed(accuracy=accuracy, words=words, shadowed=found["shadowed"] + 1, best=best)
