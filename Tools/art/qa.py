"""qa.py - automatic quality check of the HD files: shrink each HD frame back to vanilla size and measure how far it
drifted from the original pixels.  A botched render (smeared eyes, a new mouth, a wrong colour) drifts a lot.

    python qa.py                       every rendered sprite -> Catalog/qa.tsv + Catalog/qa_worst.png (worst 24)
    python qa.py --only evie_face      just matching names
    python qa.py --sheet a,b,c         contact sheet of these sprites (vanilla | HD shrunk | HD) -> Catalog/qa_sheet.png

Scores (per sprite, worst frame):
  drift   mean colour difference on the visible pixels, 0-255 (recipe P repaints shading, so bodies drift ~10-25;
          a face should stay ~5-15)
  ssim    structure similarity of the grey image on the visible area (1 = same shapes; faces should stay > 0.8)
  alpha   how well the HD outline matches the vanilla outline (IoU, 1 = same)
"""
import os, sys, json, sqlite3, argparse
import numpy as np
import cv2
from skimage.metrics import structural_similarity
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog import read_index, read_bytes, ARCHIVES, DB, CAT, WS

MOD_IMG = os.path.join(WS, "Mods", "hd_sprites_mod", "images")
_idx = {}


def vanilla(rel):
    if not _idx:
        for a in ARCHIVES:
            for k, v in read_index(a).items():
                _idx[k] = (a, v)
    a, e = _idx[rel]
    im = cv2.imdecode(np.frombuffer(read_bytes(a, e), np.uint8), cv2.IMREAD_UNCHANGED)
    return cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA)


def hd(rel, s=2):
    p = os.path.join(MOD_IMG, rel[len("images/"):].replace("/", os.sep))[:-4] + "@%d.png" % s
    if not os.path.exists(p):
        return None
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    return None if im is None else cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA)


def score(rel, w, h, n):
    v, H = vanilla(rel), hd(rel)
    if H is None:
        return None
    s = H.shape[1] // max(1, v.shape[1])
    small = cv2.resize(H, (v.shape[1], v.shape[0]), interpolation=cv2.INTER_AREA)
    worst = None
    for f in range(n):
        vf, hf = v[:, f * w:(f + 1) * w], small[:, f * w:(f + 1) * w]
        va, ha = vf[..., 3] > 8, hf[..., 3] > 8
        shadow = (vf[..., :3].sum(2) == 0) & (vf[..., 3] >= 115) & (vf[..., 3] <= 140)
        m = va & ~shadow
        if m.sum() < 12:
            continue
        drift = float(np.abs(vf[..., :3].astype(np.int16) - hf[..., :3].astype(np.int16))[m].mean())
        ys, xs = np.nonzero(m)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        if y1 - y0 >= 7 and x1 - x0 >= 7:
            g1 = cv2.cvtColor(np.ascontiguousarray(vf[y0:y1, x0:x1, :3]), cv2.COLOR_RGB2GRAY)
            g2 = cv2.cvtColor(np.ascontiguousarray(hf[y0:y1, x0:x1, :3]), cv2.COLOR_RGB2GRAY)
            g1 = np.where(m[y0:y1, x0:x1], g1, 128).astype(np.uint8)
            g2 = np.where(m[y0:y1, x0:x1], g2, 128).astype(np.uint8)
            ssim = float(structural_similarity(g1, g2, win_size=7))
        else:
            ssim = 1.0
        iou = float((va & ha).sum() / max(1, (va | ha).sum()))
        cand = (drift, ssim, iou, f)
        if worst is None or (drift - 40 * ssim) > (worst[0] - 40 * worst[1]):
            worst = cand
    return worst


def sheet(rels, out, db):
    tiles = []
    for rel in rels:
        w, h, n = db.execute("select w, h, n from sprites where rel=?", (rel,)).fetchone()
        v, H = vanilla(rel), hd(rel)
        if H is None:
            continue
        a = v[..., 3] > 8
        ys, xs = np.nonzero(a[:, :w])
        if not len(xs):
            continue
        pad = 6
        x0, y0, x1, y1 = max(xs.min() - pad, 0), max(ys.min() - pad, 0), min(xs.max() + pad, w), min(ys.max() + pad, h)
        s = H.shape[1] // v.shape[1]
        z = max(1, min(8, 260 // max(1, max(x1 - x0, y1 - y0))))
        def onbg(im):
            bg = np.full(im.shape[:2] + (3,), 70, np.uint8)
            al = im[..., 3:4].astype(np.float32) / 255
            return (im[..., :3] * al + bg * (1 - al)).astype(np.uint8)
        van = cv2.resize(onbg(v[y0:y1, x0:x1]), ((x1 - x0) * z, (y1 - y0) * z), interpolation=cv2.INTER_NEAREST)
        small = cv2.resize(H, (v.shape[1], v.shape[0]), interpolation=cv2.INTER_AREA)
        sm = cv2.resize(onbg(small[y0:y1, x0:x1]), van.shape[1::-1], interpolation=cv2.INTER_NEAREST)
        big = cv2.resize(onbg(H[y0 * s:y1 * s, x0 * s:x1 * s]), van.shape[1::-1], interpolation=cv2.INTER_AREA)
        row = np.concatenate([van, np.full((van.shape[0], 4, 3), 255, np.uint8), sm,
                              np.full((van.shape[0], 4, 3), 255, np.uint8), big], 1)
        lab = np.full((18, row.shape[1], 3), 20, np.uint8)
        cv2.putText(lab, rel.split("/")[-1][:90], (3, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (230, 230, 230), 1)
        tiles.append(np.concatenate([lab, row], 0))
    if not tiles:
        return
    W = max(t.shape[1] for t in tiles)
    tiles = [np.pad(t, ((0, 6), (0, W - t.shape[1]), (0, 0))) for t in tiles]
    cv2.imwrite(out, cv2.cvtColor(np.concatenate(tiles, 0), cv2.COLOR_RGB2BGR))
    print("sheet:", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--sheet", default="")
    a = ap.parse_args()
    db = sqlite3.connect(DB)
    if a.sheet:
        names = [x.strip() for x in a.sheet.split(",") if x.strip()]
        rels = []
        for nme in names:
            r = db.execute("select rel from sprites where rel like ?", ("%/" + nme.replace(".png", "") + "%",)).fetchone()
            if r:
                rels.append(r[0])
        sheet(rels, os.path.join(CAT, "qa_sheet.png"), db)
        return
    rows = db.execute("""select s.rel, s.w, s.h, s.n, r.role from sprites s join roles r using(rel)
                         where s.hd=1 and r.role not in ('glow','shadow','empty')""").fetchall()
    rows = [r for r in rows if a.only in r[0]]
    res = []
    for rel, w, h, n, role in rows:
        sc = score(rel, w, h, n)
        if sc:
            res.append((rel, role) + sc)
    with open(os.path.join(CAT, "qa.tsv"), "w", encoding="utf8") as f:
        f.write("rel\trole\tdrift\tssim\talpha_iou\tworst_frame\n")
        for r in sorted(res, key=lambda r: r[3]):
            f.write("%s\t%s\t%.1f\t%.3f\t%.3f\t%d\n" % r)
    by = {}
    for r in res:
        by.setdefault(r[1], []).append(r)
    print("%-11s %5s %8s %8s %8s" % ("role", "n", "drift", "ssim", "iou"))
    for role, rr in sorted(by.items()):
        print("%-11s %5d %8.1f %8.3f %8.3f" % (role, len(rr), np.median([x[2] for x in rr]),
                                                np.median([x[3] for x in rr]), np.median([x[4] for x in rr])))
    worst = sorted(res, key=lambda r: r[3])[:24]
    print("lowest structure (ssim):")
    for r in worst[:12]:
        print("   %.3f  drift %.1f  %s (%s)" % (r[3], r[2], r[0].split("/")[-1], r[1]))
    sheet([r[0] for r in worst], os.path.join(CAT, "qa_worst.png"), db)


if __name__ == "__main__":
    main()
