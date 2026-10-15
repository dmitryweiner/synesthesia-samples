# synesthesia-samples

Recorded sounds for Synesthesia's sequencer layers (synesthesia-core
`PLAN-SAMPLES-SCRIPTS.md`): owls, birds, crickets, fire, creaks, bottles,
whales, elk, and VCSL percussion. Every file is CC0 or public domain, with
its source in `provenance.md`.

- `samples/<name>/<nn>.flac` — the bank's source: one sound name, its
  variants (`owl:1` is `samples/owl/01.flac`), mono, 16-bit, at the rate
  its spectrum needs (24/32/48 kHz).
- `manifest.json` — every sample with its rate, length, source page,
  author, licence and the trim of the original.
- `bank.bin` — what a host hands the core (`SYNB` v2: header, the
  manifest, the FLAC streams back to back); built, not committed.
- `sources/*.json`, `picks.json` — what was downloaded and what the
  curator kept, by ear.

## Rebuilding

```bash
python3 -m venv ~/.venvs/synsamples && ~/.venvs/synsamples/bin/pip install numpy scipy soundfile
# ffmpeg and flac on PATH
open tools/download.html                 # BigSoundBank and Freesound need a browser
~/.venvs/synsamples/bin/python tools/cut.py         # raw/ -> cand/ (candidates)
python3 tools/listen.py && open cand/listen.html    # mark, export picks.json
~/.venvs/synsamples/bin/python tools/build_bank.py  # picks -> samples/, manifest, provenance, bank.bin
```

VCSL is fetched by the commit pinned in `raw/vcsl/COMMIT`
(`c1ea7bcc3c7309650ab0da9d15c9cd1fbc4a4c7e`); Commons and NPS files are in
`sources/commons.json` and `sources/nps.json`.

Never add a file whose licence is not stated on its source page.

## Licence

The tools and the curation are CC0 (`LICENSE`). Every sample is CC0 or
public domain at its source; `provenance.md` names the source of each.
