---
title: "feat: choose the partner's voice under Settings"
date: 2026-11-22
branch: feat/voice-choice
request-source: chat session, 2026-11-22
---

## Request

The partner's voice was always the same male voice. The learner should be able to choose among
several voices, female ones too, on the Settings page.

## Changes

- **Voices**: the German voices of Piper's collection that have one speaker, best first:
  Thorsten (male, high quality, the default), Kerstin and Ramona (female, low quality), Eva
  (female, the lowest quality), and Karlsson and Pavoque (male, low quality). Samples of each
  were rendered with the same German line and listened to before they were taken in. Left out:
  `thorsten-low`/`-medium` (the same speaker in lower quality), `thorsten_emotional` (moods,
  not a voice to talk with), and `mls`, whose 236 speakers are not labelled and would need a
  second choice.
- **Backend**: `speech.VOICES` lists them with their download size. `GET /api/voices` returns
  each with whether it is downloaded and which one is chosen; `PUT /api/voice` keeps the choice
  in the `settings` table and starts the voice's download. The voice in use is the choice, else
  `TTS_VOICE`, else Thorsten. Each voice's two files stay in `tts/` once downloaded, and the
  cache of rendered clips was already kept per voice. The voice download's expected size now
  follows the chosen voice (`Download` takes a `size` function next to `total`), so its progress
  is right for every voice.
- **Frontend**: a "Partner's voice" card on the Settings page with the voices, the size still
  to download after each that is not there, and "Hear it" to play a sample line. Choosing one
  starts its download, which the existing banner under the navigation bar shows; the list is
  loaded again when it ends. Until a voice is there the browser's own voice is used, as before.
- **Docs**: the README describes the choice; the Korean README adds it to the first setup.
- Known limit: when a voice is chosen while another voice is still downloading, its download
  starts the next time the partner speaks or the app is opened, not at once.

## Verification

- `cd backend && uv run pytest`: 242 passed (5 new in `tests/test_voice_choice.py`).
- `cd frontend && npm test`: 121 passed (3 new store tests); `npm run build` succeeded.
- In the running app (headless Chrome against a temporary data folder): the Settings page listed
  the six voices with "(63 MB to download)" after the missing ones; choosing Kerstin showed the
  download banner, downloaded its two files into `tts/`, marked it downloaded and chosen, and
  "Hear it" was answered by `/api/speech` with WAV audio. The page was looked at in a screenshot.
- Not verified: hearing each voice in the app (samples of all six were rendered with Piper and
  listened to outside the app).
