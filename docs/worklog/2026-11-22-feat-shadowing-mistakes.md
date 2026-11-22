---
title: "feat: keep sentences not said right after a video with the corrections"
date: 2026-11-22
branch: feat/shadowing-mistakes
request-source: chat session, 2026-11-22
---

## Request

Bring the shadowing mistakes made in SOS My English (`feat/shadowing-mistakes` there) to SOS My
German: a sentence said after a video with "Say it after" that did not come through in full
should be kept with the corrections, and every try recorded, so that once enough have piled up
the sounds often got wrong can be analysed with the LLM.

## Changes

- **Corrections**: a sentence shadowed below 100% is kept in a new `shadowing_mistakes` table
  (one row per sentence; a new wrong try replaces what was said and resets its practice count,
  as pattern mistakes do). `GET /api/corrections` lists it with id `s<n>`, the video's title, what
  was heard as `original`, the sentence as `improved`, and an explanation naming the words not
  heard with what was heard in their place: `Not heard: “Lücken” (heard “locken”).` It is
  practised and removed like any correction, and links to its sentence in the video.
- **Deleting the video keeps it**: the row holds the sentence and the video's title, and only its
  link to the sentence is dropped (`ON DELETE SET NULL`); the page then shows "From “<title>”
  (deleted)" without a link.
- **What was heard instead** comes from lining up the sentence's words with the transcription
  (`difflib.SequenceMatcher`), with words compared as for shadowing ("ß" as "ss", "geht's" as
  "geht es"); words missed side by side are named together, and a word left out is named alone.
- **Log for later analysis**: every try, right or not, is written to `shadowing_attempts` (the
  sentence, what was heard, the score, the time). It keeps the sentence itself, so it outlives
  the video; the README says so. The analysis itself is left for later.
- **Frontend**: `SavedCorrection` gains `video` and `position`; the link of a correction is chosen
  by `source()`, extracted first in a `refactor:` commit.
- The code is the same as in SOS My English; only the tests' sentences and the README are in
  German terms.

## Verification

- `cd backend && uv run pytest`: 249 passed (7 new, in `tests/test_shadowing_mistakes.py`, seen
  failing before the code was added), 12 live tests deselected.
- `cd frontend && npm test`: 123 passed; `npm run build` succeeded. The new `source` tests came
  with the ported code, so they were not seen failing here (they were in SOS My English).
- Desktop unchanged.
- Not verified: the running app of this repository (the same change was checked in the running
  SOS My English).
