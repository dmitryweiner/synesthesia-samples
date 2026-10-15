#!/usr/bin/env python3
"""Cut listening candidates from the raw pool.

raw/{bigsoundbank,freesound,vcsl} -> cand/<category>/<name>.wav (48 kHz mono,
16-bit) + cand/candidates.json. Hits are found on a 10 ms RMS envelope and
trimmed with short fades, peak-normalized to -1 dBFS; beds are the steadiest
window of a recording made into a loop with a 1 s equal-power crossfade,
RMS-normalized to -20 dBFS. The candidates are drafts for the listening
pass, not the bank: build-bank.py works from the picks.
"""
import json, re, subprocess, sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "raw", ROOT / "cand"
SR = 48000

# category -> (mode, merge gap s, max event s, events per source)
CATS = {
    "owl": ("hits", 0.35, 4.0, 3),
    "bird": ("hits", 0.25, 4.0, 3),
    "great-tit": ("hits", 0.25, 4.0, 3),
    "creak": ("hits", 0.15, 3.0, 3),
    "bottle": ("hits", 0.10, 3.0, 3),
    "twig": ("hits", 0.08, 1.5, 3),
    "chime": ("hits", 0.40, 6.0, 2),
    "crickets": ("bed", 0, 10.0, 1),
    "fire": ("bed", 0, 10.0, 1),
    "water": ("bed", 0, 10.0, 1),
    "frogs": ("bed", 0, 10.0, 1),
    "frog": ("hits", 0.15, 2.0, 5),
    "night": ("bed", 0, 10.0, 1),
    # round 2 (2026-10-15)
    "oriole": ("hits", 0.25, 4.0, 3),
    "kookaburra": ("hits", 0.30, 6.0, 3),
    "lyrebird": ("hits", 0.25, 5.0, 4),
    "pigeon": ("hits", 0.30, 4.0, 3),
    "dove": ("hits", 0.30, 4.0, 3),
    "potoo": ("hits", 0.40, 5.0, 3),
    "nightingale": ("hits", 0.25, 5.0, 3),
    "canary": ("hits", 0.25, 5.0, 3),
    "goldfinch": ("hits", 0.25, 4.0, 3),
    "wings": ("hits", 0.10, 2.0, 3),
    "whale": ("hits", 0.60, 8.0, 3),
    "bearded-seal": ("hits", 0.60, 10.0, 3),
    "elk": ("hits", 0.50, 6.0, 3),
}

BSB_GROUP = {"owls": "owl", "insects": "crickets", "fire": "fire", "creaks": "creak",
             "bottles": "bottle", "birds": "bird", "pigeon-wings": "wings"}
BSB_OTHER = {"0819": "frog", "0997": "frogs", "1301": "twig", "1299": "twig", "1300": "twig",
             "0823": "water", "0864": "water", "1290": "water", "0555": "night", "2687": "chime",
             "2086": "chime", "3360": "chime", "0292": "chime", "1880": "night", "1470": "night"}


def load(path):
    # ffmpeg, not libsndfile: BigSoundBank's FLACs carry a wrong MD5 signature,
    # which libsndfile rejects on some files; the frames themselves decode clean.
    sr = int(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate",
         "-of", "csv=p=0", str(path)], check=True, capture_output=True, text=True).stdout.strip().rstrip(","))
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-f", "f32le", "-"],
        check=True, capture_output=True).stdout
    x = np.frombuffer(raw, dtype="<f4").astype(np.float64)
    if sr != SR:
        g = np.gcd(sr, SR)
        x = resample_poly(x, SR // g, sr // g)
    x -= x.mean()  # DC
    return x


def env_db(x, hop):
    n = len(x) // hop
    if n == 0:
        return np.array([-120.0])
    f = x[: n * hop].reshape(n, hop)
    return 10 * np.log10((f ** 2).mean(axis=1) + 1e-12)


def fade(y, a_s=0.002, r_s=0.03):
    a, r = int(a_s * SR), min(int(r_s * SR), len(y) // 2)
    y = y.copy()
    y[:a] *= np.linspace(0, 1, a)
    y[len(y) - r:] *= np.linspace(1, 0, r) ** 2
    return y


def hits(x, gap, maxlen, k):
    hop = SR // 100
    e = env_db(x, hop)
    floor = np.percentile(e, 10)
    peak = e.max()
    thr = max(floor + 12, peak - 40)
    on = e > thr
    ev, i = [], 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and (on[j] or (np.any(on[j:j + int(gap * 100)]) and j - i < maxlen * 100)):
                j += 1
            ev.append((i, j))
            i = j
        else:
            i += 1
    out = []
    for i, j in ev:
        dur = (j - i) / 100
        if dur < 0.04:
            continue
        snr = e[i:j].max() - floor
        a = max(0, i * hop - int(0.01 * SR))
        b = min(len(x), j * hop + int(0.08 * SR), a + int(maxlen * SR))
        out.append((snr, a, b))
    out.sort(reverse=True)
    picks = sorted(out[:k], key=lambda t: t[1])
    return [(fade(x[a:b]), a / SR, b / SR, s) for s, a, b in picks]


def bed(x, L):
    X = int(1.0 * SR)
    n = int(L * SR) + X
    if len(x) < n:  # a short recording: the whole of it, a shorter crossfade
        X = min(X, len(x) // 4)
        n = len(x)
    hop = SR // 10
    e = env_db(x, hop)
    w = n // hop
    best, bi = None, 0
    for s in range(0, max(1, len(e) - w), 5):
        seg = e[s:s + w]
        score = seg.std() + 0.5 * abs(seg.mean() - np.median(e))
        if best is None or score < best:
            best, bi = score, s
    a = bi * hop
    seg = x[a:a + n]
    Ls = n - X
    t = np.linspace(0, np.pi / 2, X)
    y = seg[:Ls].copy()
    y[:X] = seg[:X] * np.sin(t) + seg[Ls:Ls + X] * np.cos(t)
    return y, a / SR, (a + n) / SR, best


def norm_peak(y, db=-1.0):
    p = np.abs(y).max()
    return y * (10 ** (db / 20) / p) if p > 0 else y


def norm_rms(y, db=-20.0):
    r = np.sqrt((y ** 2).mean())
    y = y * (10 ** (db / 20) / r) if r > 0 else y
    p = np.abs(y).max()
    return y * (0.95 / p) if p > 0.95 else y


def vcsl_picks():
    """One file per articulation: rr1 (or the first), a middle dynamic."""
    groups = {}
    for p in sorted((RAW / "vcsl").rglob("*.wav")):
        inst = p.relative_to(RAW / "vcsl").parts[2]
        stem = p.stem
        key = re.sub(r"(_|^)(v\d|vl\d|rr\d|f+|mp|p|mf|Mid|Sum|quiet|loud|\d+_\d+)(?=_|$)", "", stem)
        groups.setdefault((inst, key), []).append(p)
    per_inst = {}
    for (inst, key), files in groups.items():
        rr1 = [f for f in files if "rr2" not in f.stem and "rr3" not in f.stem and "rr4" not in f.stem] or files
        per_inst.setdefault(inst, []).append(rr1[len(rr1) // 2])
    for inst, files in per_inst.items():
        step = max(1, len(files) // 4)
        yield inst, files[::step][:4]


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def main():
    OUT.mkdir(exist_ok=True)
    bsb = json.load(open(ROOT / "sources/bigsoundbank.json"))
    jobs = []  # (category, source dict, path)
    for g, items in bsb.items():
        for it in items:
            p = next((RAW / "bigsoundbank").glob(f"*(ID {it['id']})*"), None)
            if p is None:
                print(f"missing: bigsoundbank {it['id']}", file=sys.stderr)
                continue
            cat = BSB_OTHER.get(it["id"]) or BSB_GROUP.get(g)
            jobs.append((cat, dict(src="bigsoundbank", id=it["id"], title=it["title"], page=it["page"],
                                   author="Joseph SARDIN", license="CC0"), p))
    fs = {x["id"]: x for x in json.load(open(ROOT / "sources/freesound.json"))}
    for p in sorted((RAW / "freesound").iterdir()):
        i = p.name.split("__")[0]
        jobs.append((fs[i]["cat"], dict(src="freesound", id=i, title=p.stem.split("__")[2], page=fs[i]["page"],
                                     author=p.stem.split("__")[1], license="CC0"), p))
    for x in json.load(open(ROOT / "sources/commons.json")):
        jobs.append((x["cat"], dict(src="commons", id=x["title"], title=x["title"], page=x["page"],
                                    author=x["author"] or x.get("provenance", ""), license=x["license"]),
                     ROOT / x["file"]))
    for x in json.load(open(ROOT / "sources/nps.json")):
        n = Path(x["file"]).stem
        jobs.append(("elk", dict(src="nps", id=n, title=n, page=x["page"], author=x["author"],
                                 license="Public domain"), ROOT / x["file"]))
    commit = (RAW / "vcsl/COMMIT").read_text().strip()
    for inst, files in vcsl_picks():
        cat = "vcsl-" + slug(inst)
        for p in files:
            rel = p.relative_to(RAW / "vcsl").as_posix()
            jobs.append((cat, dict(src="vcsl", id=rel, title=p.stem,
                                   page=f"https://github.com/sgossner/VCSL/blob/{commit}/{rel}",
                                   author="Versilian Studios (VCSL)", license="CC0"), p))
    cands = []
    for cat, meta, p in jobs:
        x = load(p)
        if cat.startswith("vcsl-"):
            mode = "bed" if "ocean" in cat else "hits"
            spec = ("bed", 0, 10.0, 1) if mode == "bed" else ("hits", 0.5, 6.0, 1)
        else:
            spec = CATS[cat]
        d = OUT / cat
        d.mkdir(exist_ok=True)
        base = f"{meta['src'][:3]}-{slug(meta['id'] if meta['src'] != 'vcsl' else meta['title'])}"
        if spec[0] == "hits":
            for n, (y, a, b, snr) in enumerate(hits(x, spec[1], spec[2], spec[3])):
                f = d / f"{base}-{n}.wav"
                sf.write(str(f), norm_peak(y), SR, subtype="PCM_16")
                cands.append(dict(meta, file=f.relative_to(OUT).as_posix(), cat=cat, mode="hits",
                                  trim=f"{a:.2f}-{b:.2f}s", dur=round(b - a, 2), snr_db=round(snr, 1)))
        else:
            y, a, b, score = bed(x, spec[2])
            y = norm_rms(y)
            f = d / f"{base}.wav"
            sf.write(str(f), y, SR, subtype="PCM_16")
            sf.write(str(d / f"{base}.x2.wav"), np.concatenate([y, y]), SR, subtype="PCM_16")
            cands.append(dict(meta, file=f.relative_to(OUT).as_posix(), cat=cat, mode="bed",
                              trim=f"{a:.2f}-{b:.2f}s", dur=round(len(y) / SR, 2), steadiness=round(score, 2)))
        print(f"{cat:22s} {p.name[:60]}", file=sys.stderr)
    json.dump(cands, open(OUT / "candidates.json", "w"), indent=1, ensure_ascii=False)
    print(len(cands), "candidates")


if __name__ == "__main__":
    main()
