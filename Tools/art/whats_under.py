"""whats_under.py - debugger: which sibling layers cover a sprite's pixels (same character, same frame layout).

    python whats_under.py celica_kissback_face_aroused-530-530-1      (name, with or without folder/.png)
    python whats_under.py <name> --all     every sibling with any overlap, not just the top 15

Prints for every sibling: how much of the layer it covers, its role, size - so you can see which file really is
the head/body under a face (the pipeline's context should be the covering, non-clothing, under-drawn layers).
"""
import os, sys, json, sqlite3, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog import DB
from audit import alpha_frame


def find(db, name):
    name = name.replace("\\", "/").split("/")[-1].replace(".png", "")
    r = db.execute("select rel, folder, base, w, h, n from sprites where rel like ?", ("%/" + name + ".png",)).fetchone()
    if not r:
        r = db.execute("select rel, folder, base, w, h, n from sprites where base=?", (name,)).fetchone()
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    db = sqlite3.connect(DB)
    r = find(db, a.name)
    if not r:
        sys.exit("not in the catalog: " + a.name)
    rel, fo, base, w, h, n = r
    role, recipe, ctx, pose = db.execute("select role, recipe, context, pose from roles where rel=?", (rel,)).fetchone()
    lay = alpha_frame(rel, w, h)
    print("%s  role=%s recipe=%s  %d px (frame 1)" % (rel, role, recipe, lay.sum()))
    print("pose:", pose, "  context now:", [c.split("/")[-1] for c in json.loads(ctx)])
    out = []
    for srel, sb, srole, op in db.execute("""select s.rel, s.base, r.role, s.opaque_px from sprites s join roles r using(rel)
                                            where s.folder=? and s.w=? and s.h=? and s.n=? and s.rel<>? and s.opaque_px>0""",
                                          (fo, w, h, n, rel)):
        if not (sb == pose or sb.startswith(pose + "_")):
            continue                                   # another pose that happens to share the frame layout
        al = alpha_frame(srel, w, h)
        cov = (lay & al).sum() / max(1, lay.sum())
        if cov > 0:
            out.append((cov, sb, srole, int(al.sum())))
    out.sort(reverse=True)
    for cov, sb, srole, px in out if a.all else out[:15]:
        print("  %5.0f%%  %-11s %7d px  %s" % (cov * 100, srole, px, sb))


if __name__ == "__main__":
    main()
