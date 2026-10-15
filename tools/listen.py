#!/usr/bin/env python3
"""cand/candidates.json -> cand/listen.html, the curator's listening page.

Every candidate gets a player and keep / drop / recut plus a note; beds play
their loop twice so the seam is heard. Marks stay in the browser's
localStorage; "Export" saves picks.json, which build-bank.py reads.
"""
import html, json, sys
from pathlib import Path

CAND = Path(__file__).resolve().parent.parent / "cand"

cands = json.load(open(CAND / "candidates.json"))
ONLY = sys.argv[1:]  # categories, to make a short page
if ONLY:
    cands = [c for c in cands if c["cat"] in ONLY]
cats = {}
for c in cands:
    cats.setdefault(c["cat"], []).append(c)

sections = []
for cat, items in cats.items():
    rows = []
    for c in items:
        f = c["file"].replace(".wav", ".x2.wav") if c["mode"] == "bed" else c["file"]
        fid = html.escape(c["file"])
        extra = f"loop {c['dur']}s ×2" if c["mode"] == "bed" else f"{c['dur']}s"
        rows.append(f"""<div class=row data-id="{fid}">
<audio controls preload=none src="{html.escape(f)}"></audio>
<div class=meta><b>{html.escape(c['title'][:60])}</b> <span>{extra} · {c['src']} <a href="{html.escape(c['page'])}" target=_blank>src</a> · {c['trim']}</span></div>
<div class=marks>{''.join(f'<label><input type=radio name="{fid}" value={v}>{t}</label>' for v, t in (("keep", "✓"), ("drop", "✗"), ("recut", "✂")))}
<input class=note placeholder=note></div></div>""")
    sections.append(f"<section><h2>{cat} <small>{len(items)} · {items[0]['mode']}</small> <span class=count></span></h2>{''.join(rows)}</section>")

page = f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Sample listening</title>
<style>
:root{{--bg:#fafaf7;--fg:#222;--mut:#777;--line:#ddd;--keep:#d8f0d8;--drop:#f3d6d6;--recut:#f6ecc8}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1b1b1d;--fg:#ddd;--mut:#999;--line:#333;--keep:#23402a;--drop:#4a2626;--recut:#4a4222}}}}
body{{background:var(--bg);color:var(--fg);font:14px system-ui;max-width:980px;margin:0 auto;padding:12px 16px 80px}}
h2{{position:sticky;top:0;background:var(--bg);margin:18px 0 4px;padding:6px 0;border-bottom:1px solid var(--line);font-size:17px}}
h2 small,.meta span{{color:var(--mut);font-weight:normal}}
.row{{display:grid;grid-template-columns:260px 1fr auto;gap:10px;align-items:center;padding:4px 6px;border-radius:6px}}
.row.keep{{background:var(--keep)}}.row.drop{{background:var(--drop)}}.row.recut{{background:var(--recut)}}
audio{{width:260px;height:32px}} .meta{{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}}
.marks label{{margin-right:6px;font-size:17px;cursor:pointer}} .note{{width:140px}}
#bar{{position:fixed;bottom:0;left:0;right:0;background:var(--bg);border-top:1px solid var(--line);padding:8px 16px;text-align:center}}
button{{font-size:15px;padding:4px 14px}} a{{color:inherit}}
@media (max-width:700px){{.row{{grid-template-columns:1fr}}audio{{width:100%}}}}
</style>
<h1>Sample listening</h1>
<p>✓ keep · ✗ drop · ✂ the sound is good but cut it differently (say how in the note). Beds play their loop twice — listen for the seam. Marks are kept in this browser; press <b>Export</b> when done.</p>
{''.join(sections)}
<div id=bar><span id=tot></span> <button id=exp>Export picks.json</button></div>
<script>
const KEY='syn-sample-picks';let st={{}};try{{st=JSON.parse(localStorage.getItem(KEY))||{{}}}}catch(e){{}}
const save=()=>{{try{{localStorage.setItem(KEY,JSON.stringify(st))}}catch(e){{}};paint()}};
function paint(){{let n=0;document.querySelectorAll('.row').forEach(r=>{{const s=st[r.dataset.id]||{{}};r.className='row '+(s.mark||'');if(s.mark)n++;
 const i=r.querySelector('input[value='+s.mark+']');if(i)i.checked=true;const t=r.querySelector('.note');if(document.activeElement!==t)t.value=s.note||''}});
 document.querySelectorAll('section').forEach(sec=>{{const rs=sec.querySelectorAll('.row');const d=[...rs].filter(r=>(st[r.dataset.id]||{{}}).mark).length;sec.querySelector('.count').textContent=d+'/'+rs.length}});
 document.getElementById('tot').textContent=n+' / '+document.querySelectorAll('.row').length+' marked'}}
document.querySelectorAll('.row').forEach(r=>{{const id=r.dataset.id;
 r.querySelectorAll('input[type=radio]').forEach(i=>i.onchange=()=>{{st[id]={{...(st[id]||{{}}),mark:i.value}};save()}});
 r.querySelector('.note').oninput=e=>{{st[id]={{...(st[id]||{{}}),note:e.target.value}};save()}};
 r.querySelector('audio').onplay=e=>document.querySelectorAll('audio').forEach(a=>{{if(a!==e.target)a.pause()}})}});
document.getElementById('exp').onclick=()=>{{const b=new Blob([JSON.stringify(st,null,1)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='picks.json';a.click()}};
paint();
</script>"""
out = CAND / ("listen-" + "-".join(ONLY) + ".html" if ONLY else "listen.html")
out.write_text(page)
print(out, len(cands))
