---
title: "feat: translate a video's sentences into the learner's language"
date: 2026-11-22
branch: feat/video-translation
request-source: chat session, 2026-11-22
---

## Request

On a video's page, the learner should be able to turn a translation of the subtitles into their
own language on and off: without one, a learner often cannot tell what is being said.

## Changes

- **Backend**: `POST /api/videos/{id}/translations` returns every sentence of a saved video in
  the feedback language, by line id. Sentences without a kept translation are sent to the model
  in parts of 40, four parts at a time, with the video's title, and each part's translations are
  saved as it comes back (new table `line_translations`, one row per sentence and language,
  deleted with the video). A sentence the model leaves out is asked for the next time; ids that
  were not asked for are ignored. A failure is reported (502) only when nothing could be
  translated; otherwise what was translated is returned. With German as the feedback language
  the request is refused (422).
- **Frontend**: a "Translation" toggle next to "Show the text". Turned on, it asks for the
  translation of the open video (and of each video opened while it is on) and shows each
  sentence's translation under it, in smaller grey text, also while the German text is hidden.
  The toggle is kept while the app is open. Loading and failure (with "Try again") are shown
  under the controls.
- **Alternatives considered**: YouTube's own automatic translation of the subtitles costs no
  model request, but its lines are YouTube's subtitle lines, which the app joins and cuts again
  into sentences, so they would not line up with the sentences shown. Translating only the
  sentences on screen was left out to keep one request per part and a list that can be read
  ahead.
- **Privacy**: turning the translation on sends all of a video's subtitles to the LLM provider;
  the README says so next to what else is sent.
- **Docs**: the README and the Korean README describe the toggle.

## Verification

- `cd backend && uv run pytest`: 228 passed (9 new, in `tests/test_video_translations.py`),
  11 live tests deselected.
- New live test, `uv run --env-file .env pytest -m live -k translated` (Gemini): passed; three
  German sentences came back in Korean, in order.
- `cd frontend && npm test`: 118 passed (3 new store tests); `npm run build` succeeded.
- With the real model and a temporary data folder, a 281-sentence video with automatic
  subtitles was translated into Korean in 10.3 s; asking again answered at once from the kept
  translations.
- Not verified: the toggle in the running app (the store and the build are tested, the page by
  hand is not).
