---
title: "docs: point to SOS My Language, which this app has moved into"
date: 2026-11-24
branch: docs/moved-to-sos-my-language
request-source: chat session, 2026-11-24
---

## Request

`sos-my-english` and `sos-my-german` were brought together in one app, `sos-my-language`, whose
first version (v0.1.0) was released on 2026-11-24. Say so at the top of this repository's READMEs
and point to the new repository, before this one is archived.

## Changes

- `README.md` and `README.ko.md` open with a note: SOS My German has moved into SOS My Language, which
  teaches English and German in one app; new versions are released there and this repository is
  no longer developed; with a link to the new repository and to its latest release.
- The note also says that the new app is a separate one that starts empty: what was saved in
  SOS My German is not carried over. `sos-my-language` was started without a way to import the data of
  the two earlier apps.
- Nothing else is changed: the rest of the READMEs still describes this app as it is at its last
  version, for those who keep using it.

## Verification

- Both links of the note were requested: the repository answers, and `releases/latest` leads to
  the v0.1.0 release of `sos-my-language`.
- The note is written as a GitHub alert (`> [!IMPORTANT]`); how it is drawn was not looked at
  before the pull request was opened.
- No code is changed, so no tests were run locally.
