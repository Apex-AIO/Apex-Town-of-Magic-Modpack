"""dither_test.py - prototype: pixel-art checkerboard dithering (Celica's blush, shading) turns into diagonal stripes
when upscaled.  Idea: before the upscale, replace a checkerboard (every other pixel transparent) with a smooth
see-through colour, so the upscaler draws a soft blush instead of stripes.

    python dither_test.py                         -> Catalog/dither_test.png  (vanilla | as now | smoothed first)
    python dither_test.py --count                 how many rendered/queued sprites contain checkerboard dithering
    python dither_test.py name1,name2             other sprites
"""
import os, sys, argparse, sqlite3
import numpy as np
import cv2
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "upscale"))
from catalog import DB, CAT
from qa import vanilla


def dither_mask(rgba):
    """opaque pixels whose 4 neighbours are transparent and diagonal neighbours opaque (checkerboard), + the holes"""
    a = rgba[..., 3] > 8
    p = np.pad(a, 1)
    up, dn, lf, rt = p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]
    d1, d2, d3, d4 = p[:-2, :-2], p[:-2, 2:], p[2:, :-2], p[2:, 2:]
    lone = a & ~up & ~dn & ~lf & ~rt                       # touches others only at the corners
    diag = d1.astype(int) + d2 + d3 + d4
    core = lone & (diag >= 3)                              # inside a real checkerboard (a 1-px diagonal LINE has 2)
    k = np.ones((3, 3), np.uint8)
    near = cv2.dilate(core.astype(np.uint8), k).astype(bool)
    cell = lone & near & (diag >= 1)                       # the checkerboard's own dots, incl. its edge dots
    n, lab, stats, _ = cv2.connectedComponentsWithStats(cv2.dilate(cell.astype(np.uint8), k))
    for i in range(1, n):                                  # tiny groups are details, not dithering
        if stats[i, cv2.CC_STAT_AREA] < 12:
            cell[lab == i] = False
    area = cv2.morphologyEx(cell.astype(np.uint8), cv2.MORPH_CLOSE, k)       # the dithered area incl. its holes
    return cell, area.astype(bool) | cell


def smooth_dither(rgba):
    cell, area = dither_mask(rgba)
    if not cell.any():
        return rgba, 0
    out = rgba.copy()
    n, lab = cv2.connectedComponents(area.astype(np.uint8))
    for i in range(1, n):
        reg = lab == i
        dots = reg & cell
        if dots.sum() < 3:
            continue
        col = rgba[dots][:, :3].mean(0)
        dens = dots.sum() / reg.sum()                     # ~0.5 for a checkerboard
        out[reg, :3] = col.round().astype(np.uint8)
        out[reg, 3] = int(round(255 * dens * (rgba[dots][:, 3].mean() / 255)))
    return out, int(cell.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="?", default="celica_squat_rub_face_aroused-530-530-6,celica_face_blush-530-530-1")
    ap.add_argument("--count", action="store_true")
    a = ap.parse_args()
    db = sqlite3.connect(DB)
    if a.count:
        rows = db.execute("select rel, w from sprites where (hd=1 or queued is not null) and opaque_px>0").fetchall()
        hit = [(r, smooth_dither(np.ascontiguousarray(vanilla(r)[:, :w]))[1]) for r, w in rows]
        hit = [h for h in hit if h[1] >= 6]
        print("%d of %d rendered/queued sprites contain checkerboard dithering" % (len(hit), len(rows)))
        for r, c in sorted(hit, key=lambda x: -x[1])[:15]:
            print("   %4d dots  %s" % (c, r.split("/")[-1]))
        return
    import spandrel
    from compare_upscalers import upscale4, MODEL_DIR, ALPHA_MODEL, DEV
    from refine_compare import color_match
    from PIL import Image
    L = spandrel.ModelLoader()                                  # the same models hd_batch.py uses
    model = L.load_from_file(os.path.join(MODEL_DIR, "4x-ReboutBlend.pth")).to(DEV).eval()
    amodel = L.load_from_file(os.path.join(MODEL_DIR, ALPHA_MODEL)).to(DEV).eval()
    tiles = []
    for name in a.names.split(","):
        rel, w, h = db.execute("select rel, w, h from sprites where rel like ?", ("%/" + name + ".png",)).fetchone()
        fr = np.ascontiguousarray(vanilla(rel)[:, :w])
        ys, xs = np.nonzero(fr[..., 3] > 8)
        x0, y0, x1, y1 = xs.min() - 6, ys.min() - 6, xs.max() + 7, ys.max() + 7
        crop = fr[y0:y1, x0:x1]
        sm, n = smooth_dither(crop)

        def up8(arr):
            img = Image.fromarray(arr, "RGBA")
            w_, h_ = img.size
            x4 = upscale4(model, amodel, img)
            return np.array(color_match(upscale4(model, amodel, x4.resize((w_ * 2, h_ * 2), Image.LANCZOS)), img))

        def onbg(arr):
            bg = np.full(arr.shape[:2] + (3,), 222, np.uint8)        # skin-ish light background like a face
            bg[...] = (233, 196, 178)
            al = arr[..., 3:4].astype(np.float32) / 255
            return (arr[..., :3] * al + bg * (1 - al)).astype(np.uint8)
        H = 8 * crop.shape[0]
        van = cv2.resize(onbg(crop), (8 * crop.shape[1], H), interpolation=cv2.INTER_NEAREST)
        a1 = onbg(up8(crop))
        a2 = onbg(up8(sm))
        row = np.concatenate([van, np.full((H, 6, 3), 255, np.uint8), a1, np.full((H, 6, 3), 255, np.uint8), a2], 1)
        lab = np.full((22, row.shape[1], 3), 20, np.uint8)
        cv2.putText(lab, "%s   (%d dither dots)   vanilla | upscaled as now | dither smoothed first" % (name, n), (4, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (235, 235, 235), 1)
        tiles.append(np.concatenate([lab, row], 0))
    W = max(t.shape[1] for t in tiles)
    out = np.concatenate([np.pad(t, ((0, 8), (0, W - t.shape[1]), (0, 0))) for t in tiles], 0)
    p = os.path.join(CAT, "dither_test.png")
    cv2.imwrite(p, cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
    print("written", p)


if __name__ == "__main__":
    main()
