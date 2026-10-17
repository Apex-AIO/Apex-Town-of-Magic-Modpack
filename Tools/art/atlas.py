"""atlas.py - a local web page to browse the art catalog: characters -> poses -> layers, each with
    vanilla | the layer on what the AI sees under it (context, faded) | the HD result (if made)
and its role, recipe, context coverage, frames, twins and the game scenes that use it.

    python atlas.py                    sprites seen in game, queued or rendered  -> Catalog/atlas/index.html
    python atlas.py --folder evie      every sprite of one character (any folder)
    python atlas.py --all              everything (29k sprites - big)
Local only: the thumbnails are the game's own art (Catalog/ is never published).
"""
import os, sys, json, html, base64, shutil, sqlite3, argparse, collections
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog import DB, CAT
from qa import vanilla, hd

OUT = os.path.join(CAT, "atlas")
T = 128                                                   # thumbnail box


def checker(h, w, c1=58, c2=72, s=8):
    yy, xx = np.mgrid[0:h, 0:w]
    return np.where(((yy // s + xx // s) % 2)[..., None] == 0, c1, c2).astype(np.uint8).repeat(3, 2)


def over(dst, src, k=1.0):
    a = src[..., 3:4].astype(np.float32) / 255 * k
    return (src[..., :3] * a + dst * (1 - a)).astype(np.uint8)


def thumb(img, box, scale_to, nearest):
    x0, y0, x1, y1 = box
    crop = img[y0:y1, x0:x1]
    z = scale_to / max(1, max(x1 - x0, y1 - y0))
    size = (max(1, int((x1 - x0) * z)), max(1, int((y1 - y0) * z)))
    return cv2.resize(crop, size, interpolation=cv2.INTER_NEAREST if nearest else cv2.INTER_AREA)


def make_thumbs(rel, w, h, ctx, name):
    v = vanilla(rel)
    fr = v[:, :w]
    al = fr[..., 3] > 8
    if not al.any():
        return None
    ys, xs = np.nonzero(al)
    pad = 4
    box = (max(xs.min() - pad, 0), max(ys.min() - pad, 0), min(xs.max() + pad + 1, w), min(ys.max() + pad + 1, h))
    bw, bh = box[2] - box[0], box[3] - box[1]
    files = {}
    base = checker(bh, bw)
    img = over(base, fr[box[1]:box[3], box[0]:box[2]])
    files["v"] = thumb(np.dstack([img, np.full(img.shape[:2], 255, np.uint8)]), (0, 0, bw, bh), T, True)
    cimg = checker(bh, bw)
    for c in ctx:
        try:
            cv = vanilla(c)[:, :w][box[1]:box[3], box[0]:box[2]]
            cimg = over(cimg, cv, 0.45)
        except Exception:
            pass
    cimg = over(cimg, fr[box[1]:box[3], box[0]:box[2]])
    files["c"] = thumb(np.dstack([cimg, np.full(cimg.shape[:2], 255, np.uint8)]), (0, 0, bw, bh), T, True)
    H = hd(rel)
    if H is not None:
        s = H.shape[0] // v.shape[0]
        hf = H[:, :w * s][box[1] * s:box[3] * s, box[0] * s:box[2] * s]
        himg = over(checker(hf.shape[0], hf.shape[1], s=8 * s), hf)
        files["h"] = thumb(np.dstack([himg, np.full(himg.shape[:2], 255, np.uint8)]), (0, 0, hf.shape[1], hf.shape[0]), T, False)
    out = {}
    for k, im in files.items():
        # embedded in the page (data URI): the pages work anywhere, no image folder to keep next to them
        ok, png = cv2.imencode(".png", cv2.cvtColor(im[..., :3], cv2.COLOR_RGB2BGR))
        out[k] = "data:image/png;base64," + base64.b64encode(png.tobytes()).decode("ascii")
    return out


CSS = """
:root{--bg:#141118;--card:#201b27;--fg:#e8e4ee;--mut:#9a92a6;--acc:#ffd24d;--line:#3a3245}
body{background:var(--bg);color:var(--fg);font:13px/1.4 system-ui,Segoe UI,sans-serif;margin:0;padding:16px}
a{color:var(--acc)} h1{font-size:22px;margin:0 0 4px} h2{font-size:16px;margin:22px 0 8px;color:var(--acc)}
.mut{color:var(--mut)} input{background:#0d0b10;color:var(--fg);border:1px solid var(--line);padding:6px 8px;width:320px}
.grid{display:flex;flex-wrap:wrap;gap:10px}.card{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px;width:410px}
.card img{image-rendering:pixelated;background:#222;margin-right:4px;vertical-align:top;max-width:128px;max-height:128px}
.card img.hd{image-rendering:auto}.n{font-weight:600;word-break:break-all}.tag{display:inline-block;padding:0 6px;border-radius:9px;
background:#2f2838;margin:2px 3px 0 0;font-size:11px}.bad{background:#5a2330}.ok{background:#22462b}.q{background:#4a3d18}
table{border-collapse:collapse}td,th{padding:3px 10px;border-bottom:1px solid var(--line);text-align:left}
"""
JS = """
function f(){const q=document.getElementById('q').value.toLowerCase();document.querySelectorAll('.card').forEach(c=>{
c.style.display=c.dataset.k.includes(q)?'':'none'});}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    shutil.rmtree(os.path.join(OUT, "t"), ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    db = sqlite3.connect(DB)
    where = "1=1" if a.all else ("s.folder=?" if a.folder else "(s.seen=1 or s.hd=1 or s.queued is not null)")
    args = (a.folder,) if a.folder and not a.all else ()
    rows = db.execute("""select s.rel, s.folder, s.base, s.w, s.h, s.n, s.frames_unique, s.hd, s.queued, s.seen, s.refs,
                         s.pixhash, r.role, r.recipe, r.context, r.coverage, r.pose
                         from sprites s join roles r using(rel) where %s order by s.folder, r.pose, s.base""" % where, args).fetchall()
    twins = collections.Counter(db.execute("select pixhash from sprites").fetchall())
    names = dict(db.execute("select folder, name from characters"))
    by_folder = collections.defaultdict(list)
    for i, r in enumerate(rows):
        rel, fo, base, w, h, n, fu, hdm, q, seen, refs, ph, role, recipe, ctx, cov, pose = r
        if role in ("empty",):
            continue
        th = make_thumbs(rel, w, h, json.loads(ctx), "%s_%05d" % (fo, i)) if role != "shadow" else None
        by_folder[fo].append((r, th))
        if (i + 1) % 200 == 0:
            print("  %d / %d" % (i + 1, len(rows)), flush=True)
    index = ["<h1>Town of Magic - art atlas</h1><p class=mut>%d sprites shown. Each card: original | the layer on the "
             "layers under it (what the AI sees, faded) | HD result. Built by Tools/art/atlas.py.</p>"
             "<table><tr><th>character</th><th>folder</th><th>sprites</th><th>HD made</th><th>queued</th></tr>" % len(rows)]
    for fo, items in sorted(by_folder.items(), key=lambda x: -len(x[1])):
        cards = []
        for r, th in items:
            rel, fo_, base, w, h, n, fu, hdm, q, seen, refs, ph, role, recipe, ctx, cov, pose = r
            tags = ['<span class=tag>%s</span>' % role, '<span class=tag>recipe %s</span>' % recipe,
                    '<span class="tag %s">%s</span>' % ("ok" if hdm else "q" if q else "", "HD made" if hdm else "queued: " + q if q else "seen" if seen else "not seen")]
            if cov is not None:
                tags.append('<span class="tag %s">on context %d%%</span>' % ("bad" if cov < .8 and role in ("face", "head_face") else "", cov * 100))
            if n > 1:
                tags.append('<span class=tag>%d frames (%d unique)</span>' % (n, fu))
            if twins[(ph,)] > 1:
                tags.append('<span class=tag>%d identical files</span>' % twins[(ph,)])
            imgs = "".join('<img %s src="%s" title="%s">' % ('class=hd' if k == "h" else "", th[k], t)
                           for k, t in (("v", "original"), ("c", "on its context"), ("h", "HD")) if th and k in th)
            sc = ", ".join(json.loads(refs))[:220] if refs else ""
            ctxs = ", ".join(c.split("/")[-1].rsplit("-", 3)[0][len(pose):] or "<pose>" for c in json.loads(ctx))
            key = (base + " " + role + " " + recipe + " " + (q or "") + " " + sc).lower()
            cards.append('<div class=card data-k="%s"><div class=n>%s</div><div>%s</div><div>%s</div>'
                         '<div class=mut>pose %s &middot; context: %s</div>%s</div>' % (
                html.escape(key), html.escape(base), imgs, "".join(tags), html.escape(pose), html.escape(ctxs or "none"),
                ('<div class=mut>scenes: %s</div>' % html.escape(sc)) if sc else ""))
        page = ('<!doctype html><meta charset=utf8><title>%s - atlas</title><style>%s</style><script>%s</script>'
                '<p><a href="index.html">&larr; all characters</a></p><h1>%s <span class=mut>(%s)</span></h1>'
                '<p><input id=q oninput="f()" placeholder="filter: name, role, recipe, queued, scene..."></p>'
                '<div class=grid>%s</div>' % (fo, CSS, JS, html.escape(names.get(fo, fo)), fo, "".join(cards)))
        open(os.path.join(OUT, "char_%s.html" % fo), "w", encoding="utf8").write(page)
        hdn = sum(1 for r, _ in items if r[7])
        qn = sum(1 for r, _ in items if r[8] and not r[7])
        index.append('<tr><td><a href="char_%s.html">%s</a></td><td class=mut>%s</td><td>%d</td><td>%d</td><td>%d</td></tr>'
                     % (fo, html.escape(names.get(fo, fo)), fo, len(items), hdn, qn))
    index.append("</table>")
    open(os.path.join(OUT, "index.html"), "w", encoding="utf8").write(
        '<!doctype html><meta charset=utf8><title>Art atlas</title><style>%s</style>%s' % (CSS, "".join(index)))
    print("atlas:", os.path.join(OUT, "index.html"))


if __name__ == "__main__":
    main()
