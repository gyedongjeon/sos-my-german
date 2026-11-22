---
title: "fix: cut automatic German subtitles into sentences"
date: 2026-11-22
branch: fix/punctuate-automatic-subtitles
request-source: chat session, 2026-11-22
---

## Request

Videos in SOS My German were listed line by line as YouTube shows its subtitles, not sentence by
sentence as in SOS My English, which made them hard to study with. Subtitles should be grouped
into sentences where possible.

## Changes

- **Cause**: the video tried had only YouTube's automatic subtitles, and YouTube's automatic
  German subtitles have no punctuation at all ("hallo halli Hallo ich bin Kari und ich"). With
  no sentence ends to cut at, the app keeps such subtitles line by line. YouTube's automatic
  English subtitles come punctuated, which is why SOS My English cut them into sentences.
- **Fix**: when a video is added and its subtitles have too few sentence ends (the test the
  sentence cutting already used), `videos.punctuate` has the model add punctuation and capitals,
  up to 300 words a request and four requests at a time, each part ending with a subtitle line.
  Each line keeps its own number of words, so every word keeps its time, and the sentences are
  then cut as for punctuated subtitles.
- **Only the marks are taken from the model.** In a first try the model was required to return
  the words unchanged, and every part of a real video was refused: told not to, it still
  corrected recognition errors ("baldm" to "bald", "manuelmann" to "manuel mann"). The reply is
  now lined up with the words (`difflib.SequenceMatcher`); each word keeps its own spelling and
  takes the capital and the marks after it from the model's version of it, and where words were
  joined, split, added, or dropped, the marks after the model's last word go after the last word
  said there. A reply in which fewer than nine in ten of the words are found is not used.
- **A part that could not be punctuated** stays line by line (each of its subtitle lines ends a
  sentence), so it does not run into one long line next to punctuated parts. With no model, or
  when every part fails, the video is saved line by line as before.
- Subtitles with punctuation are not sent, and nothing changes for them. Videos saved before keep
  their lines; deleting and adding one again cuts it into sentences.
- **Privacy**: all the subtitles of a video without punctuation are sent to the LLM provider
  when it is added; the README says so.
- **The review in German, again**: while this was checked, the live review test failed 1 of 4
  runs, the review written in German though Korean was chosen. The wording "whatever language
  the conversation was in" (from `feat/init`) had replaced "not in German", which cannot be said
  when German is the chosen language. `settings.not_german` now adds "Do not use German for it,
  …" to the prompts of a correction, a pattern verdict, and the review, unless German is chosen.
- **Merged with `main`** after the video translation was merged: both changed the same lines of
  the READMEs and both added a live test at the end of `test_live_llm.py`; both sides were kept.
- **Alternatives considered**: cutting at pauses alone (pauses in speech do not follow sentences
  closely enough), and transcribing the video's audio with the local Whisper model, which writes
  punctuation (the video would have to be downloaded, which the app does not do).

## Verification

- `cd backend && uv run pytest`: 226 passed (7 new, in `tests/test_punctuation.py`), 11 live
  tests deselected, before the merge.
- New live test, `uv run --env-file .env pytest -m live -k automatic_subtitles` (Gemini):
  passed; four unpunctuated lines with a recognition error came back cut at sentence ends, with
  every word as it was.
- With the real model and a temporary data folder, the video that was tried (286 automatic
  subtitle lines) was saved in 11.9 s as 230 sentences instead of 281 lines, for example
  "Hallo, ich bin Kari und ich bin Janusch, und wir zeigen euch heute die wichtigsten
  Begrüßungen und Verabschiedungen in der deutschen Sprache."; the longest has 30 words.
- After the merge and the prompt change: `uv run pytest` 237 passed; the live review test passed
  6 runs in a row, and the whole live suite (12 tests) passed twice.
- Not verified: the videos page in the running app (the API's lines are what the page lists).
