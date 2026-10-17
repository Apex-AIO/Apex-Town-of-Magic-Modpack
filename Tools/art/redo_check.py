"""redo_check.py - which ALREADY RENDERED HD files were made with a worse context or the wrong recipe than the art
catalog now gives, and should be rendered again.

    python redo_check.py            report only
    python redo_check.py --write    also writes Tools/upscale/sets/redo.txt (run_hd_pending.bat redoes it first)

"Old" = what hd_batch.py's name rules gave before it read the catalog.  A rendered layer is redone when
  * its recipe changes (e.g. an outfit body that got the gentle face recipe, a head that got the feet LoRA), or
  * it is a face / head-with-face / see-through layer that floated: under 80% of it lay on its context before and
    the catalog's context covers at least 20 points more.
"""
import os, sys, sqlite3, collections, argparse
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "upscale"))
from catalog import DB, WS
from audit import alpha_frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    import hd_batch as H                     # for its old name rules (_context_by_name, pose_of)
    db = sqlite3.connect(DB)
    rows = db.execute("""select s.rel, s.w, s.h, s.base, r.role, r.recipe, r.coverage from sprites s join roles r using(rel)
                         where s.hd=1""").fetchall()
    redo, why = [], collections.Counter()
    for rel, w, h, base, role, recipe, cov in rows:
        old_recipe = "none" if "glow" in base else "face" if "_face" in base else "body" if base == H.pose_of(rel) else "p"
        if old_recipe != recipe and recipe in ("face", "body", "p") and old_recipe != "none":
            redo.append(rel)
            why["recipe %s -> %s" % (old_recipe, recipe)] += 1
            continue
        if role in ("face", "head_face", "ghost") and cov is not None:
            lay = alpha_frame(rel, w, h)
            under = np.zeros_like(lay)
            for c in H._context_by_name(rel, None):
                under |= alpha_frame(c, w, h)
            ocov = (lay & under).sum() / max(1, lay.sum())
            if ocov < 0.8 and cov - ocov >= 0.2:
                redo.append(rel)
                why["%s floated" % role] += 1
    import artdb                              # rendered twins of a redo file were copied from it: redo them too
    mod = os.path.join(WS, "Mods", "hd_sprites_mod")
    for r in list(redo):
        for tw in artdb.twins_of(r):
            if tw not in redo and os.path.exists(os.path.join(mod, tw.replace("/", os.sep))[:-4] + "@2.png"):
                redo.append(tw)
                why["twin of a redo file"] += 1
    print("%d rendered sprites checked, %d to redo" % (len(rows), len(redo)))
    for k, v in why.most_common():
        print("   %-28s %d" % (k, v))
    print("   by character:", dict(collections.Counter(r.split("/")[2] for r in redo)))
    if a.write:
        with open(os.path.join(WS, "Tools", "upscale", "sets", "redo.txt"), "w", encoding="utf8", newline="\n") as f:
            f.write("\n".join(redo) + "\n")
        print("written: Tools/upscale/sets/redo.txt")


if __name__ == "__main__":
    main()
