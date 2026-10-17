"""bg_catalog.py - catalogues the game's backgrounds (images/BG, images/BGANIM, images/EVENT) into Catalog/art.db,
table "backgrounds".  Read straight from the .rpa archives.

    python bg_catalog.py          (~20 s)  -> table + Catalog/backgrounds.txt summary

Per file: folder, location key (l_alchemyshop), variant (day / evening / night / glow / frame number ...),
size, kind (full = opaque picture, overlay = partly see-through, e.g. glows, doors, clouds), animation set and
frame number (name1, name2 ... in a set), exact duplicates, the location's in-game name, seen in game, HD made.
"""
import os, re, sys, glob, json, sqlite3, hashlib, collections
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog import read_index, read_bytes, ARCHIVES, DB, CAT, SCRIPTS, LOGS, GAME, WS

FOLDERS = ("images/BG/", "images/BGANIM/", "images/EVENT/")
TIMES = ("day", "evening", "night", "morning", "dawn", "dusk")
HD_DIR = os.path.join(WS, "Mods", "hd_sprites_mod")


def location_names():
    out = {}
    for f in glob.glob(os.path.join(SCRIPTS, "initialize_variables_locations*.rpy")) + glob.glob(os.path.join(SCRIPTS, "*.rpy")):
        txt = open(f, encoding="utf8", errors="replace").read()
        for m in re.finditer(r"\b(l_\w+)\s*=\s*Location\(([^\n]*)", txt):
            nm = re.search(r"name\s*=\s*\"([^\"]*)\"", m.group(2))
            if nm:
                out.setdefault(m.group(1), nm.group(1))
    return out


def seen_set():
    seen = set()
    for lf in glob.glob(os.path.join(LOGS, "used_images*.txt")) + [os.path.join(GAME, "claude_debug", "used_images.txt")]:
        if os.path.exists(lf):
            for l in open(lf, encoding="utf8", errors="replace"):
                p = l.split("\t")[0].strip().replace("\\", "/")
                p = p if p.startswith("images/") else "images/" + p
                seen.add(p)
    return seen


def main():
    idx = {}
    for a in ARCHIVES:
        for k, v in read_index(a).items():
            if k.startswith(FOLDERS) and k.endswith(".png"):
                idx[k] = (a, v)
    names = location_names()
    seen = seen_set()
    rows, hashes = [], {}
    stems = collections.Counter()
    for rel in idx:
        stem = re.sub(r"\d+$", "", os.path.basename(rel)[:-4])
        if stem != os.path.basename(rel)[:-4]:
            stems[(os.path.dirname(rel), stem)] += 1
    for rel in sorted(idx):
        a, e = idx[rel]
        im = cv2.imdecode(np.frombuffer(read_bytes(a, e), np.uint8), cv2.IMREAD_UNCHANGED)
        h, w = im.shape[:2]
        if im.ndim == 3 and im.shape[2] == 4:
            al = im[..., 3]
            vis = float((al > 8).mean())
            solid = float((al > 245).mean())
        else:
            vis = solid = 1.0
        kind = "full" if solid > 0.98 else "overlay"
        ph = hashlib.md5(im.tobytes()).hexdigest()[:16]
        base = os.path.basename(rel)[:-4]
        folder = rel.split("/")[1]
        m = re.match(r"^(l_[a-z0-9]+)", base)
        loc = m.group(1) if m else base.split("_")[0]
        rest = base[len(loc):].lstrip("_")
        num = re.search(r"(\d+)$", base)
        stem = re.sub(r"\d+$", "", base)
        anim = stem if num and stems[(os.path.dirname(rel), stem)] >= 2 else None
        variant = rest or "base"
        time = next((t for t in TIMES if re.search(r"(^|_)%s(\d*$|_)" % t, rest)), None)
        hd = os.path.exists(os.path.join(HD_DIR, rel.replace("/", os.sep))[:-4] + "@2.png")
        rows.append(dict(rel=rel, folder=folder, loc=loc, loc_name=names.get(loc, ""), variant=variant, time=time,
                         w=w, h=h, kind=kind, visible=round(vis, 3), anim=anim, frame=int(num.group(1)) if anim else None,
                         pixhash=ph, dup_of=hashes.get(ph), seen=int(rel in seen), hd=int(hd)))
        hashes.setdefault(ph, rel)
    db = sqlite3.connect(DB)
    db.execute("DROP TABLE IF EXISTS backgrounds")
    cols = list(rows[0])
    db.execute("CREATE TABLE backgrounds(%s)" % ", ".join(c + (" TEXT PRIMARY KEY" if c == "rel" else "") for c in cols))
    db.executemany("INSERT INTO backgrounds VALUES (%s)" % ",".join("?" * len(cols)), [[r[c] for c in cols] for r in rows])
    db.commit()

    by = collections.defaultdict(list)
    for r in rows:
        by[r["folder"]].append(r)
    lines = []
    for fo, rr in by.items():
        sizes = collections.Counter("%dx%d" % (r["w"], r["h"]) for r in rr)
        lines.append("== %s: %d files   kinds %s   sizes %s" % (fo, len(rr), dict(collections.Counter(r["kind"] for r in rr)),
                                                               sizes.most_common(6)))
        lines.append("   duplicates %d, animation frames %d in %d sets, seen in game %d, HD made %d" % (
            sum(1 for r in rr if r["dup_of"]), sum(1 for r in rr if r["anim"]), len({r["anim"] for r in rr if r["anim"]}),
            sum(r["seen"] for r in rr), sum(r["hd"] for r in rr)))
    locs = collections.defaultdict(list)
    for r in rows:
        if r["folder"] == "BG":
            locs[r["loc"]].append(r)
    lines.append("\n== %d locations (BG); time-of-day variants %d" % (len(locs), sum(1 for r in rows if r["time"])))
    for loc, rr in sorted(locs.items(), key=lambda x: (-sum(r["seen"] for r in x[1]), x[0])):
        lines.append("   %-28s %-30s files %2d  seen %2d  variants: %s" % (loc, rr[0]["loc_name"][:30], len(rr), sum(r["seen"] for r in rr),
                                                                      ", ".join(sorted(r["variant"] for r in rr))[:110]))
    text = "\n".join(lines)
    open(os.path.join(CAT, "backgrounds.txt"), "w", encoding="utf8").write(text + "\n")
    print("\n".join(lines[:8]))
    print("full list: Catalog/backgrounds.txt")


if __name__ == "__main__":
    main()
