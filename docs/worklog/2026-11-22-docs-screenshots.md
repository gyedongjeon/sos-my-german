---
title: "docs: add screenshots to the READMEs"
date: 2026-11-22
branch: docs/screenshots
request-source: chat session, 2026-11-22
---

## Request

Add screenshots of the app to the README.

## Changes

- Three screenshots in `docs/images/`, at the size of SOS My English's (1280 x 828 points at
  2x, 2560 x 1656 pixels), and in the same places in `README.md` and `README.ko.md`:
    - `practice.png`, under the introduction: the opening line of "Small talk", a spoken line
      with a mistake ("gestern ich gehe … an den Strand"), its correction explained in Korean,
      and the partner's reply being read aloud.
    - `home.png`, under "First setup" (in Korean, "사용 방법"): the topics of the first category.
    - `video.png`, new, under "Videos" (in Korean, under step 9): a video with automatic
      subtitles cut into sentences, with the translation turned on. It is taller (1280 x 1200
      points) and scrolled down, so that several sentences with their translation show below
      the player.
- **How they were made**: the app ran from this checkout against a temporary data folder, with a
  Gemini model and Korean as the feedback language, and headless Chrome was driven over the
  DevTools protocol. Nothing in the conversation was staged: the learner's line was spoken by
  the app's own Piper voice into Chrome's fake microphone, transcribed by Whisper, and corrected
  by the model. The video is "Learn Basic German Greetings & Farewells in Slow German" (Easy
  German), shown in YouTube's embedded player as in the app.

## Verification

- The three images were looked at; they are 2560 x 1656, 2560 x 1656, and 2560 x 2400 pixels.
- Each image path in both READMEs points at a file in `docs/images/`.
