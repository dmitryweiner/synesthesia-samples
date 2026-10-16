---
name: add-sample
description: Add a new sample to the Synesthesia bank — a new variant of an existing sound name (another owl) or a whole new name — from a CC0 / public-domain source: record the source, download it to raw/, cut candidates, let the user pick by ear, rebuild samples/, manifest, provenance.md, the listening page index.html and bank.bin. Use when the user asks to add, find or replace a sample or sound ("add a woodpecker", "one more owl", "a better rain bed").
---

# Add a sample

The pipeline is `sources/*.json → raw/ → tools/cut.py → cand/ → picks.json →
tools/build_bank.py → samples/, manifest.json, provenance.md, index.html,
bank.bin` (README "Rebuilding"). `raw/`, `cand/` and `bank.bin` are not
committed; everything else is. There are no speakers on this machine: the
user's ears pick, you prepare the choice.

Python with numpy/scipy/soundfile is `~/.venvs/synsamples/bin/python`
(call it `PY` below); `ffmpeg` and `flac` are on PATH.

## 1. A source whose licence is stated

**Never add a file whose licence is not stated on its source page.** Only
CC0 or public domain — not CC-BY, not "free for use", not "royalty free".
Open the page, read the licence there, and keep its URL.

| source | how it gets to raw/ | where it is recorded |
|---|---|---|
| BigSoundBank (all CC0) | browser download (ZIP with FLAC/WAV); `tools/download.html` shows the form | `sources/bigsoundbank.json`, under a group key: `{id, q, title, len, page, desc}` |
| Freesound (filter licence = CC0) | browser download, logged in; keep the file name `<id>__<user>__<title>.<ext>` | `sources/freesound.json`: `{id, page, download, cat, round}` |
| Wikimedia Commons (PD/CC0 only) | `curl -L` the original URL | `sources/commons.json`: `{cat, file, title, page, url, license, author, credit, desc}`; `file` is `raw/commons/<cat>__<name>.<ext>` |
| NPS sound libraries (public domain) | `curl -L` | `sources/nps.json`: `{file, url, page, author, license}` (cut.py treats all as `elk`; give it a `cat` and read it in cut.py for another animal) |
| VCSL (CC0) | already in `raw/vcsl` at the pinned commit | nothing; cut.py takes one file per articulation |

Downloads that need the browser: ask the user to download (or, with their
yes, drive Chrome), then move the file into `raw/<source>/`. Bump `round`
(Freesound) to mark the batch.

## 2. Teach the cutter and the builder the category

- `tools/cut.py`, `CATS`: a new category gets `(mode, merge gap s, max
  event s, events per source)`. `hits` are one-shots (a call, a knock);
  `bed` is a loopable 10 s ambience (rain, crickets). Copy the nearest
  existing line. For BigSoundBank put the id into `BSB_OTHER` (or its
  group into `BSB_GROUP`).
- `tools/build_bank.py`: the category's sound name goes into `NAME`; when
  a category holds several names (BigSoundBank's `bird`, `chime`, `water`,
  `bottle`) map the source id in `BY_ID`.

## 3. Cut and listen

```bash
$PY tools/cut.py                          # all of raw/ -> cand/, deterministic: old candidates keep their names
python3 tools/listen.py <category> ...    # cand/listen-<category>.html, only the new categories
open cand/listen-<category>.html
```

Read the new entries in `cand/candidates.json` (`snr_db`, `dur`, `trim`)
and drop the obviously bad ones yourself before asking. Then the user
listens, marks ✓/✗/✂ and exports `picks.json`; the page keeps marks in
localStorage under one key for every listen page, so their export may hold
older marks too. A ✂ (recut) means changing that category's `CATS` line
and cutting again.

## 4. Merge the picks — append, never reorder

Variants are numbered in the order of `picks.json` (`owl:3` is the fourth
owl kept). Presets refer to sounds by name **and index**, so add the new
`{"<cand file>": {"mark": "keep"}}` entries **at the end** of the
committed `picks.json`; the existing variants keep their numbers. Removing
or replacing an existing variant renumbers the ones after it — say so to
the user and get a yes first.

## 5. Build and check

```bash
$PY tools/build_bank.py     # samples/, manifest.json, provenance.md, index.html, bank.bin
git status --short          # only the new samples/<name>/NN.flac and the generated files change
git diff --stat samples/    # an existing .flac changing means the order moved: stop and look
```

`build_bank.py` regenerates `index.html` (the listening page,
`tools/gallery.py`) every time; never edit `index.html` or `provenance.md`
by hand. If only the page's look changed, `$PY tools/gallery.py`.

Check in `provenance.md` that the new rows name the right page, author and
licence. Open `index.html` (serve the repo, e.g. `python3 -m http.server`,
and open `/index.html`) so the user can hear the result in context.

## 6. A new name needs the core too

A new variant of an existing name is playable as soon as the bank ships.
A **new name** is silent until synesthesia-core's catalogue lists it:
`seqSounds` (`syn-core/src/schema.rs`, `assets/schema.json`, the tests in
`syn-core/tests/catalogue.rs`, and `PLAN-SAMPLES-SCRIPTS.md`'s name list).
New names are appended after the bank names and before the synth drums
`bd sd hh oh cp` — that shifts the drums' indices, so it is the core's
change to make and agree there. Tell the user; do not edit the core from
here unasked.

## 7. Commit; the release is the user's call

Commit `sources/`, `tools/`, `picks.json`, `samples/`, `manifest.json`,
`provenance.md`, `index.html` with a message naming what was added and from
where. The apps ship the bank as a release asset by tag and sha256
(README): a new bank is a new tag `bank-vN` with `bank.bin` attached and a
bump of the pins in the web app and Android. Publishing a release and
bumping other repositories is outward-facing — propose it, with the new
sha256 (`shasum -a 256 bank.bin`), and wait for the user's yes.
