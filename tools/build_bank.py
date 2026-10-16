#!/usr/bin/env python3
"""picks.json + cand/ -> samples/<name>/<nn>.flac, manifest.json, provenance.md, index.html, bank.bin.

Each kept candidate becomes one variant of a sound name (the names the core's
`seqSounds` catalogue lists; `owl:1` is the second owl). Its sample rate is
measured, not chosen by hand: the share of energy above 15.5 kHz and above
11 kHz decides 48, 32 or 24 kHz (RATE_RULE_DB), so a bell keeps its air and a
whale does not pay for silence. The FLACs here are the source of truth;
bank.bin is built from them and is what a host hands the core:

    bank.bin = "SYNB" | u32 version (2) | u32 manifest_len | manifest JSON (UTF-8)
             | the FLAC streams back to back (each entry's "offset"/"bytes")

All integers little-endian. Rebuilding from the same picks gives the same bytes.
"""
import hashlib, json, re, struct, subprocess, sys, tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

import gallery

ROOT = Path(__file__).resolve().parent.parent
CAND, SAMPLES = ROOT / "cand", ROOT / "samples"
RATE_RULE_DB = -30.0
VERSION = 2

# candidate category -> sound name; a mixed category is split by source id
NAME = {"vcsl-" + k: v for k, v in {
    "frame-drum": "frame-drum", "darbuka": "darbuka", "conga": "conga", "bongos": "bongo",
    "woodblock": "woodblock", "triangles": "triangle", "slit-drum": "slit-drum",
    "sleigh-bells": "sleigh-bells", "shaker-large": "shaker", "mark-trees": "mark-trees",
    "hand-bells-nepalese": "hand-bell", "cowbells": "cowbell"}.items()}
NAME.update({"night": "night", "fire": "fire", "owl": "owl", "great-tit": "great-tit", "creak": "creak",
             "lyrebird": "lyrebird", "kookaburra": "kookaburra", "canary": "canary", "goldfinch": "goldfinch",
             "oriole": "oriole", "dove": "dove", "pigeon": "pigeon", "potoo": "potoo", "wings": "wings",
             "whale": "whale", "elk": "elk", "nightingale": "nightingale", "frog": "frog"})
BY_ID = {  # bigsoundbank ids in mixed categories
    "3086": "nightingale", "3087": "nightingale", "3088": "nightingale",
    "3476": "blackbird", "3486": "blackbird", "3494": "blackbird", "3503": "blackbird",
    "1667": "robin", "1669": "robin", "1670": "robin", "1673": "robin",
    "2764": "crow", "3461": "crow", "3463": "crow",
    "2246": "cicada", "0823": "stream", "1290": "rain",
    "2687": "chimes", "2086": "chimes", "3360": "pendulum", "0292": "bell",
    "1939": "bottle-blow", "846527": "bottle-blow", "0487": "bottle-clink", "1393": "bottle-clink",
}


def name_of(c):
    if c["id"] in BY_ID:
        return BY_ID[c["id"]]
    if c["cat"] == "crickets":
        return "crickets"
    return NAME[c["cat"]]


def rate_of(y, sr):
    p = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2
    f = np.fft.rfftfreq(len(y), 1 / sr)
    e = p.sum() + 1e-30
    db = lambda lo: 10 * np.log10(p[f > lo].sum() / e + 1e-12)
    return 48000 if db(15500) > RATE_RULE_DB else 32000 if db(11000) > RATE_RULE_DB else 24000


def main():
    picks = json.load(open(sys.argv[1] if len(sys.argv) > 1 else ROOT / "picks.json"))
    cands = {c["file"]: c for c in json.load(open(CAND / "candidates.json"))}
    kept = [cands[k] for k, v in picks.items() if v.get("mark") == "keep"]
    missing = [k for k, v in picks.items() if v.get("mark") == "keep" and k not in cands]
    assert not missing, f"picked but not cut: {missing}"
    sounds = {}
    for c in kept:
        sounds.setdefault(name_of(c), []).append(c)
    for old in SAMPLES.glob("*/*.flac"):
        old.unlink()
    manifest, blobs, offset = {"version": VERSION, "sounds": {}}, [], 0
    with tempfile.TemporaryDirectory() as tmp:
        for name in sorted(sounds):
            entries = []
            for n, c in enumerate(sounds[name]):
                y, sr = sf.read(str(CAND / c["file"]))
                r = rate_of(y, sr)
                if r != sr:
                    g = np.gcd(r, sr)
                    y = resample_poly(y, r // g, sr // g)
                pcm = np.round(np.clip(y, -1, 1 - 1 / 32768) * 32767).astype("<i2")
                wav = Path(tmp) / "x.wav"
                sf.write(str(wav), pcm, r, subtype="PCM_16")
                dst = SAMPLES / name / f"{n:02d}.flac"
                dst.parent.mkdir(parents=True, exist_ok=True)
                # no padding, no seektable, no MD5 needed; --no-utf8-convert etc. keep it reproducible
                subprocess.run(["flac", "-8", "-f", "-s", "--no-padding", "--no-seektable", "-o", str(dst), str(wav)],
                               check=True)
                b = dst.read_bytes()
                entries.append(dict(
                    file=f"samples/{name}/{n:02d}.flac", sr=r, frames=len(pcm), offset=offset, bytes=len(b),
                    sha256=hashlib.sha256(b).hexdigest()[:16], mode=c["mode"],
                    src=c["src"], page=c["page"], author=c["author"], license=c["license"],
                    title=c["title"], trim=c["trim"], cand=c["file"]))
                blobs.append(b)
                offset += len(b)
            manifest["sounds"][name] = entries
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    mj = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()
    bank = b"SYNB" + struct.pack("<II", VERSION, len(mj)) + mj + b"".join(blobs)
    (ROOT / "bank.bin").write_bytes(bank)
    write_provenance(manifest)
    gallery.write(manifest)
    n = sum(len(v) for v in manifest["sounds"].values())
    secs = sum(e["frames"] / e["sr"] for v in manifest["sounds"].values() for e in v)
    by_sr = {}
    for v in manifest["sounds"].values():
        for e in v:
            by_sr[e["sr"]] = by_sr.get(e["sr"], 0) + 1
    print(f"{len(manifest['sounds'])} names, {n} samples, {secs:.0f} s, rates {dict(sorted(by_sr.items()))}, "
          f"bank.bin {len(bank) / 1e6:.2f} MB (manifest {len(mj) / 1e3:.0f} kB)")


def write_provenance(manifest):
    lic = {"bigsoundbank": "CC0 (stated on the sound's page)", "freesound": "CC0 (stated on the sound's page)",
           "vcsl": "CC0 (VCSL README)", "commons": "as stated on the file page", "nps": "Public domain (NPS)"}
    lines = ["# Provenance", "", "Every sample in `samples/`, where it came from and under what terms, as the",
             "source page stated when it was picked (2026-10-14/15). Generated by `tools/build_bank.py`",
             "from `manifest.json`; do not edit by hand.", "",
             "| file | rate | source | author | licence | trim of the original |", "|---|---|---|---|---|---|"]
    for name, entries in manifest["sounds"].items():
        for e in entries:
            l = e["license"] if e["src"] == "commons" else lic[e["src"]]
            t = re.sub(r"[|\n]", " ", e["title"])[:60]
            lines.append(f"| `{e['file']}` | {e['sr'] // 1000} kHz | [{t}]({e['page']}) | "
                         f"{re.sub(r'[|]', ' ', e['author'])[:60]} | {l} | {e['trim']} |")
    (ROOT / "provenance.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
