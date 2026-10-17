"""audit.py - checks every rendered + queued sprite against the catalog's roles (run catalog.py and roles.py first).

    python audit.py                 -> Catalog/audit.txt (+ audit.tsv)
    python audit.py --redo-list     also writes Tools/upscale/sets/redo.txt (rendered files that should be redone)

Per sprite:
  recipe       what hd_batch's old name rule gave / gives vs what the role says it should be
  coverage     share of the layer's pixels that lie on its context layers (the body the AI sees under it).
               Under 80% = the AI upscales it floating on grey (what broke Evie's face).
  duplicate    identical pixels AND identical context to another sprite -> render once, copy the result
"""
import os, sys, json, sqlite3, collections, hashlib, argparse
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog import read_index, read_bytes, ARCHIVES, DB, CAT, WS

SETS = os.path.join(WS, "Tools", "upscale", "sets")
_idx = {}


def alpha_frame(rel, w, h, f=0):
    if not _idx:
        for a in ARCHIVES:
            for k, v in read_index(a).items():
                _idx[k] = (a, v)
    a, e = _idx[rel]
    im = cv2.imdecode(np.frombuffer(read_bytes(a, e), np.uint8), cv2.IMREAD_UNCHANGED)
    if im.ndim == 2 or im.shape[2] == 3:
        return np.ones((h, w), bool)
    al = im[:, f * w:(f + 1) * w, 3]
    rgb = im[:, f * w:(f + 1) * w, :3]
    shadow = (rgb.sum(2) == 0) & (al >= 115) & (al <= 140)
    return (al > 8) & ~shadow


def old_recipe(base, role):
    if "glow" in base:
        return "none"
    if "_face" in base:
        return "face"
    return "body" if role == "body" else "p"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--redo-list", action="store_true")
    a = ap.parse_args()
    db = sqlite3.connect(DB)
    rows = db.execute("""select s.rel, s.folder, s.base, s.w, s.h, s.n, s.opaque_px, s.hd, s.queued, s.pixhash,
                         r.role, r.recipe, r.context from sprites s join roles r using(rel)
                         where s.hd=1 or s.queued is not null""").fetchall()
    findings = collections.defaultdict(list)
    tsv = []
    ctxhash_cache = {}

    def ctx_sig(ctx):
        key = tuple(ctx)
        if key not in ctxhash_cache:
            hs = [db.execute("select pixhash from sprites where rel=?", (c,)).fetchone()[0] for c in ctx]
            ctxhash_cache[key] = hashlib.md5("|".join(hs).encode()).hexdigest()[:12]
        return ctxhash_cache[key]

    sigs = collections.defaultdict(list)
    for rel, fo, base, w, h, n, op, hd, queued, ph, role, recipe, ctx in rows:
        ctx = json.loads(ctx)
        cov = None
        if op > 0 and role not in ("glow", "shadow", "empty", "outfit_body", "body", "hairb"):
            lay = alpha_frame(rel, w, h)
            if lay.any():
                under = np.zeros_like(lay)
                for c in ctx:
                    under |= alpha_frame(c, w, h)
                cov = round(float((lay & under).sum() / lay.sum()), 2)
        orec = old_recipe(base, role)
        status = "rendered" if hd else "queued"
        if orec != recipe and recipe in ("face", "body", "p") and orec != "none":
            findings["recipe from the catalog differs from the old name rule (%s)" % status].append("%s: was %s -> now %s (%s)" % (rel, orec, recipe, role))
        if cov is not None and cov < 0.8 and role == "face":
            # only matters for eye/mouth layers: bodies, heads, arms, hair, skirts stick out past the body by nature
            findings["face floating, under 80%% on a body (%s)" % status].append("%s: %.0f%% on %s  [%s]" % (
                rel, cov * 100, [c.split('/')[-1] for c in ctx] or "nothing", role))
        sigs[(ph, ctx_sig(ctx))].append((rel, hd))
        tsv.append("\t".join(map(str, [rel, status, role, recipe, orec, cov, len(ctx)])))

    reuse = []
    for (ph, cs), group in sigs.items():
        done = [r for r, hd in group if hd]
        todo = [r for r, hd in group if not hd]
        if len(group) > 1 and todo:
            reuse.append((done[0] if done else todo[0], todo if done else todo[1:]))
    n_copy = sum(len(t) for _, t in reuse)

    with open(os.path.join(CAT, "audit.txt"), "w", encoding="utf8") as f:
        f.write("AUDIT of %d rendered + queued sprites\n\n" % len(rows))
        for k in sorted(findings):
            f.write("== %s: %d\n" % (k, len(findings[k])))
            for line in findings[k]:
                f.write("   " + line + "\n")
            f.write("\n")
        f.write("== render once, copy: %d queued sprites are identical (pixels + context) to another one\n" % n_copy)
        for src, dsts in reuse:
            f.write("   %s -> %s\n" % (src.split("/")[-1], ", ".join(d.split("/")[-1] for d in dsts)))
    with open(os.path.join(CAT, "audit.tsv"), "w", encoding="utf8") as f:
        f.write("rel\tstatus\trole\trecipe\told_recipe\tcoverage\tcontext_layers\n" + "\n".join(tsv) + "\n")
    for k in sorted(findings):
        print("%-40s %d" % (k, len(findings[k])))
    print("%-40s %d" % ("queued copies of another sprite", n_copy))
    if a.redo_list:
        redo = sorted(set(l.split(":")[0] for k in findings if "rendered" in k for l in findings[k]))
        with open(os.path.join(SETS, "redo.txt"), "w", encoding="utf8", newline="\n") as f:
            f.write("\n".join(redo) + "\n")
        print("redo list:", len(redo))


if __name__ == "__main__":
    main()
