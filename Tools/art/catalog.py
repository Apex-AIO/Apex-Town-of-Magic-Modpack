"""catalog.py - builds the art catalog: every character sprite of the game, read straight from the .rpa archives.

    python catalog.py            (re)build Catalog/art.db  (~1-3 min on 16 cores)

For every sprite sheet (images/CHAR/<folder>/<name>-<w>-<h>-<frames>.png) it stores:
  name parts     folder (character), base name, frame size, frame count
  pixels         visible pixels, bounding box, translucent pixels (glow), floor-shadow pixels, average colour,
                 skin-coloured share, an exact pixel hash (finds identical files), unique frames
  game info      which character the folder is (from the game's Enemy list, incl. "Male"), scripts that name it
  our status     HD made (@2/@4 in the mod), on a render list, seen in game (used_images logs)
Everything else (stacks, audits, atlas) reads this database.
"""
import os, sys, re, io, glob, json, time, sqlite3, hashlib, zlib, pickle
from multiprocessing import Pool
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.normpath(os.path.join(HERE, "..", ".."))
GAME = os.path.normpath(os.path.join(WS, "..", "game"))
CAT = os.path.join(WS, "Catalog")
DB = os.path.join(CAT, "art.db")
SCRIPTS = os.path.join(WS, "Extracted", "scripts")
MOD_IMG = os.path.join(WS, "Mods", "hd_sprites_mod", "images")
SETS = os.path.join(WS, "Tools", "upscale", "sets")
LOGS = os.path.join(WS, "Tools", "debug", "logs")
ARCHIVES = [os.path.join(GAME, "images1.rpa"), os.path.join(GAME, "images2.rpa")]
NAME_RX = re.compile(r"^images/CHAR/([^/]+)/(.+)-(\d+)-(\d+)-(\d+)\.png$")


def read_index(path):
    with open(path, "rb") as f:
        hdr = f.readline().decode().split()
        off, key = int(hdr[1], 16), int(hdr[2], 16)
        f.seek(off)
        idx = pickle.loads(zlib.decompress(f.read()), encoding="bytes")
    out = {}
    for k, v in idx.items():
        k = k.decode("utf8") if isinstance(k, bytes) else k
        o, l = v[0][0] ^ key, v[0][1] ^ key
        pre = v[0][2] if len(v[0]) > 2 else b""
        out[k] = (o, l, pre.encode("latin1") if isinstance(pre, str) else pre)
    return out


_fh = {}


def read_bytes(arch, entry):
    f = _fh.get(arch) or _fh.setdefault(arch, open(arch, "rb"))
    o, l, pre = entry
    f.seek(o)
    return pre + f.read(l - len(pre))


def skin_mask(rgb):
    """rough anime-skin detector (YCrCb box, bright enough)"""
    ycc = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)
    y, cr, cb = ycc[..., 0], ycc[..., 1], ycc[..., 2]
    return (cr >= 135) & (cr <= 180) & (cb >= 85) & (cb <= 135) & (y >= 90)


def analyse(job):
    rel, arch, entry = job
    m = NAME_RX.match(rel)
    folder, base, w, h, n = m.group(1), m.group(2), int(m.group(3)), int(m.group(4)), int(m.group(5))
    data = read_bytes(arch, entry)
    im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    rec = dict(rel=rel, folder=folder, base=base, w=w, h=h, n=n, bytes=len(data), archive=os.path.basename(arch))
    if im is None:
        rec.update(error="decode failed")
        return rec, []
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGRA)
    elif im.shape[2] == 3:
        im = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
    rgba = im[..., [2, 1, 0, 3]]
    H, W = rgba.shape[:2]
    rec.update(sheet_w=W, sheet_h=H)
    a = rgba[..., 3]
    vis = a > 8
    shadow = (rgba[..., 0] == 0) & (rgba[..., 1] == 0) & (rgba[..., 2] == 0) & (a >= 115) & (a <= 140)
    semi = vis & (a < 245) & ~shadow
    body = vis & ~shadow
    rec.update(opaque_px=int(body.sum()), shadow_px=int(shadow.sum()), semi_px=int(semi.sum()),
               pixhash=hashlib.md5(rgba.tobytes() + bytes(str(rgba.shape), "ascii")).hexdigest()[:16])
    if body.any():
        sel = rgba[body][:, :3]
        rec.update(mean_rgb="#%02x%02x%02x" % tuple(int(v) for v in sel.mean(0)),
                   skin_frac=round(float(skin_mask(np.ascontiguousarray(rgba[..., :3]))[body].mean()), 3))
    frames, seen = [], {}
    for f in range(n):
        x0 = f * w
        if x0 >= W:
            break
        fr = rgba[:, x0:x0 + w]
        fb = (fr[..., 3] > 8)
        key = hashlib.md5(fr.tobytes()).hexdigest()[:16]
        ys, xs = np.nonzero(fb)
        bbox = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if len(xs) else None
        frames.append(dict(rel=rel, f=f, px=int(fb.sum()), bbox=json.dumps(bbox), fhash=key, dup_of=seen.get(key)))
        seen.setdefault(key, f)
    ys, xs = np.nonzero(body)
    if len(xs):
        # bounding box inside a frame (union over frames)
        fx = xs % w
        rec.update(bbox=json.dumps((int(fx.min()), int(ys.min()), int(fx.max()) + 1, int(ys.max()) + 1)))
    rec.update(frames_unique=len(seen), frames_real=len(frames))
    return rec, frames


def characters():
    """image folder -> (display name, male?) from the game's Enemy definitions"""
    var_folder, var_props, var_name = {}, {}, {}
    for f in glob.glob(os.path.join(SCRIPTS, "initialize_variables_*.rpy")):
        txt = open(f, encoding="utf8", errors="replace").read()
        for m in re.finditer(r"(e_\w+)\s*=\s*Enemy\(([^\n]*)", txt):
            args = m.group(2)
            img = re.search(r"image\s*=\s*\"([^\"]+)\"", args)
            nm = re.search(r"name\s*=\s*\"([^\"]*)\"", args)
            if img:
                var_folder.setdefault(m.group(1), img.group(1))
                var_name.setdefault(m.group(1), nm.group(1) if nm else "")
        for m in re.finditer(r"(e_\w+)\.properties\s*=\s*\[([^\]]*)\]", txt):
            var_props.setdefault(m.group(1), m.group(2))
    out = {}
    for v, folder in var_folder.items():
        name, male, vars_ = out.get(folder, ("", False, []))
        out[folder] = (name or var_name.get(v, ""), male or '"Male"' in var_props.get(v, ""), vars_ + [v])
    return out


def script_refs(names):
    """sprite base name prefix -> scripts/labels that mention it (finds which scene uses a pose)"""
    refs = {}
    want = set(names)
    tok = re.compile(r"\"([a-z0-9_]+)\"")
    for f in glob.glob(os.path.join(SCRIPTS, "*.rpy")):
        label = "?"
        fn = os.path.basename(f)
        for line in open(f, encoding="utf8", errors="replace"):
            ml = re.match(r"\s*label\s+([\w.]+)", line)
            if ml:
                label = ml.group(1)
            for t in tok.findall(line):
                if t in want:
                    refs.setdefault(t, set()).add("%s:%s" % (fn, label))
    return refs


def main():
    t0 = time.time()
    os.makedirs(CAT, exist_ok=True)
    jobs = []
    for arch in ARCHIVES:
        for rel, entry in read_index(arch).items():
            if NAME_RX.match(rel):
                jobs.append((rel, arch, entry))
    print("sprites in the archives:", len(jobs), flush=True)
    recs, frames = [], []
    with Pool(max(2, (os.cpu_count() or 4) - 2)) as pool:
        for i, (r, fr) in enumerate(pool.imap_unordered(analyse, jobs, chunksize=64)):
            recs.append(r)
            frames.extend(fr)
            if (i + 1) % 5000 == 0:
                print("  %d / %d  (%.0fs)" % (i + 1, len(jobs), time.time() - t0), flush=True)

    chars = characters()
    names = set(r["base"] for r in recs)
    # pose-ish prefixes too (a script names "celica_bed_hoveropentouch", the files add layers to it)
    prefixes = set()
    for b in names:
        parts = b.split("_")
        for k in range(1, len(parts) + 1):
            prefixes.add("_".join(parts[:k]))
    refs = script_refs(prefixes)

    hd = set()
    for p in glob.glob(os.path.join(MOD_IMG, "CHAR", "*", "*@2.png")):
        hd.add("images/" + os.path.relpath(p, MOD_IMG).replace(os.sep, "/").replace("@2.png", ".png"))
    queued = {}
    for sf in glob.glob(os.path.join(SETS, "*.txt")):
        for l in open(sf, encoding="utf8"):
            l = l.strip()
            if l:
                queued.setdefault(l if l.startswith("images/") else "images/" + l, os.path.basename(sf)[:-4])
    seen = set()
    for lf in glob.glob(os.path.join(LOGS, "used_images*.txt")) + [os.path.join(GAME, "claude_debug", "used_images.txt")]:
        if os.path.exists(lf):
            for l in open(lf, encoding="utf8", errors="replace"):
                p = l.split("\t")[0].strip().replace("\\", "/")
                p = p if p.startswith("images/") else "images/" + p
                seen.add(re.sub(r"@\d+(?=\.png$)", "", p))

    if os.path.exists(DB):
        os.remove(DB)
    db = sqlite3.connect(DB)
    db.executescript("""
    CREATE TABLE sprites(rel TEXT PRIMARY KEY, folder TEXT, base TEXT, w INT, h INT, n INT, sheet_w INT, sheet_h INT,
        bytes INT, archive TEXT, opaque_px INT, shadow_px INT, semi_px INT, mean_rgb TEXT, skin_frac REAL, bbox TEXT,
        pixhash TEXT, frames_unique INT, frames_real INT, error TEXT,
        hd INT, queued TEXT, seen INT, dup_of TEXT, refs TEXT);
    CREATE TABLE frames(rel TEXT, f INT, px INT, bbox TEXT, fhash TEXT, dup_of INT, PRIMARY KEY(rel, f));
    CREATE TABLE characters(folder TEXT PRIMARY KEY, name TEXT, male INT, vars TEXT, sprites INT, frames INT);
    """)
    first_by_hash = {}
    for r in sorted(recs, key=lambda r: r["rel"]):
        h = r.get("pixhash")
        r["dup_of"] = first_by_hash.get(h) if h and r.get("opaque_px", 0) + r.get("shadow_px", 0) > 0 else None
        if h:
            first_by_hash.setdefault(h, r["rel"])
        parts = r["base"].split("_")
        rr = set()
        for k in range(len(parts), 1, -1):          # at least "<character>_<pose>": the bare name is everywhere
            rr |= {x for x in refs.get("_".join(parts[:k]), set())
                   if not x.endswith(":?") and not x.startswith("renpy_debug")}   # ":?" = not in a scene; debug menu
            if rr:
                break
        r.update(hd=int(r["rel"] in hd), queued=queued.get(r["rel"]), seen=int(r["rel"] in seen),
                 refs=json.dumps(sorted(rr)[:12]) if rr else None)
    cols = ["rel", "folder", "base", "w", "h", "n", "sheet_w", "sheet_h", "bytes", "archive", "opaque_px", "shadow_px",
            "semi_px", "mean_rgb", "skin_frac", "bbox", "pixhash", "frames_unique", "frames_real", "error", "hd", "queued",
            "seen", "dup_of", "refs"]
    db.executemany("INSERT INTO sprites VALUES (%s)" % ",".join("?" * len(cols)), [[r.get(c) for c in cols] for r in recs])
    db.executemany("INSERT INTO frames VALUES (?,?,?,?,?,?)",
                   [(f["rel"], f["f"], f["px"], f["bbox"], f["fhash"], f["dup_of"]) for f in frames])
    per = {}
    for r in recs:
        c = per.setdefault(r["folder"], [0, 0])
        c[0] += 1
        c[1] += r.get("frames_real") or 0
    db.executemany("INSERT INTO characters VALUES (?,?,?,?,?,?)",
                   [(fo, chars.get(fo, ("", False, []))[0], int(chars.get(fo, ("", False, []))[1]),
                     ",".join(chars.get(fo, ("", False, []))[2]), c[0], c[1]) for fo, c in per.items()])
    db.execute("CREATE INDEX sp_folder ON sprites(folder)")
    db.execute("CREATE INDEX sp_hash ON sprites(pixhash)")
    db.execute("CREATE INDEX fr_hash ON frames(fhash)")
    db.commit()
    print("catalog written: %s  (%d sprites, %d frames, %.0fs)" % (DB, len(recs), len(frames), time.time() - t0))


if __name__ == "__main__":
    main()
