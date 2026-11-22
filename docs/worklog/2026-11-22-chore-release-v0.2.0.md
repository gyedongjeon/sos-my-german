---
title: "chore: release v0.2.0"
date: 2026-11-22
branch: chore/release-v0.2.0
request-source: chat session, 2026-11-22
---

## Request

Release the changes made since v0.1.0, so the installed app gets them.

## Changes

- The version is raised from `0.1.0` to `0.2.0` in `backend/pyproject.toml`,
  `frontend/package.json`, and `desktop/package.json`, with their lock files. It is a MINOR
  release: two features came in since v0.1.0, with two fixes.
    - **Translation of a video's sentences** into the feedback language, turned on and off on
      the video's page (#2).
    - **Automatic German subtitles cut into sentences**: the model adds the punctuation they lack,
      and every word keeps its spelling and time (#3).
    - **The learner's texts not in German**: the review, a correction's explanation, and a
      pattern verdict are no longer written in German now and then when another language is
      chosen (#3).
    - **The partner's voice chosen under Settings**, among three male and three female German
      voices (#5).
    - Screenshots in the READMEs (#4).
- A video saved with v0.1.0 from automatic subtitles keeps its lines; deleting and adding it
  again cuts it into sentences.

## Verification

- `.github/scripts/check-version.sh v0.2.0`: all packages are at 0.2.0.
- `cd backend && uv run pytest`: 242 passed, 12 live tests deselected.
- `cd frontend && npm test`: 121 passed; `npm run build` succeeded.
- `cd desktop && npm test`: 48 passed; `npx tsc --noEmit` succeeded.
- Not verified: the installed app of this version; it is built by the release workflow after
  the tag is pushed.
