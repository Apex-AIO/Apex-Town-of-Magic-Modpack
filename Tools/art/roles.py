"""roles.py - what every sprite IS, which HD recipe it needs, and which layers lie under it in the game.

    python roles.py          fills the "roles" table of Catalog/art.db (run catalog.py first; ~2-4 min)

Roles (data-driven - file names alone are not enough, many characters name their body "..._face_<expr>_<outfit>"):
  empty        nothing visible                                        -> nothing to render
  shadow       only the floor shadow (pose files of most NPCs)        -> shadow redrawn, no AI
  glow         glow overlays ("glow" in the name)                     -> no AI
  face         eyes / mouth layer ("_face", under 1500 px a frame)    -> gentle face recipe
  head_face    a head or body WITH its face baked in (bigger "_face") -> gentle face recipe (keeps the expression)
  ghost        see-through body (Nel)                                 -> gentle face recipe (as rendered so far)
  outfit_body  blank-face body for an expression: "<face file>_<outfit>" where <face file> is a small face layer
               (evie_face_normal + _nopanties)                        -> body recipe (P + feet LoRA)
  body         a pose's own base layer (Celica's naked body ...)      -> body recipe (P + feet LoRA)
  <kind>       Celica's other layers by name: breasts, clothing, arms, neck, head, hair, grab, other -> recipe P
Context = the layers drawn UNDER this one (so the AI sees the body, not grey).  Chosen by measuring: the pose's body
and breasts, plus the head type (forward/down/felt/up/raised/tilt/front/lowered/back) whose head covers the layer
best, with that head's neck and back hair; a non-Celica face lies on its outfit body.  "coverage" = share of the
layer's pixels that lie on its context (low on a face = it would be upscaled floating on grey).
"""
import os, re, sys, json, sqlite3, collections
from multiprocessing import Pool
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
WS = os.path.normpath(os.path.join(HERE, "..", ".."))
DB = os.path.join(WS, "Catalog", "art.db")

FACE_MAX_PX = 1500           # per frame: bigger "_face" layers carry a head/body with the face in it
CONTAINER_MIN_PX = 3000      # per frame: an outfit body is at least this big
OUTFIT_PREF = ["nopanties", "cephpanties", "normalpanties"]      # which outfit body to lay a face on (any works)
HEADS = "forward|down|felt|up|raised|tilt|front|lowered|back"    # Celica's head types (from the file names)
NEED_CONTEXT = ("face", "head_face", "ghost", "breasts", "clothing", "arms", "neck", "head", "hair", "grab", "other")

# layer kinds (the part of the name after the pose), in drawing order - hd_batch.py reads roles, not this table.
# Order checked against the game's real stacks (stacks_check.py): body, back hair, neck, breasts, clothing, arms,
# head, face, hair
KINDS = [
    (r"^$", "body", 0),
    (r"^_head\w*hair_\w*b$", "hairb", 1),
    (r"^_arms_\w*b$", "arms", 3),            # an arm behind the body ("..._arms_raisedb")
    (r"^_breasts", "breasts", 4),
    (r"^_(top|bottom|feet|socks|sleeves|head)_", "clothing", 5),
    (r"^_arms_", "arms", 8),
    (r"^_head(%s)neck$" % HEADS, "neck", 2),
    (r"^_head(%s)$" % HEADS, "head", 10),
    (r"^_(\w+_)?face_", "face", 11),
    (r"^_head\w*hair_", "hair", 12),
    (r"^_grab_", "grab", 13),
]
RANK = {k: r for _, k, r in KINDS}


def kind_of(suffix):
    for rx, k, rank in KINDS:
        if re.match(rx, suffix):
            return k, rank
    return "other", 6


def _cover_job(job):
    """pixels: pick the best-covering head type for each layer of one pose, return (rel, context, coverage)"""
    from audit import alpha_frame
    w, h, layers, heads, fixed_by_layer, no_heads = job
    cache = {}

    def al(rel):
        if rel not in cache:
            cache[rel] = alpha_frame(rel, w, h)
        return cache[rel]
    out = []
    for rel, rank in layers:
        lay = al(rel)
        tot = lay.sum()
        ctx = list(fixed_by_layer[rel])
        if heads and rank > RANK["breasts"] and tot and rel not in no_heads:
            best = None
            for t, files in heads.items():
                use = [f for r, f in files if r < rank]
                if not use:
                    continue
                cov = (lay & np.logical_or.reduce([al(f) for f in use])).sum() / tot
                if best is None or cov > best[0]:
                    best = (cov, use)
            if best and best[0] > 0:
                ctx += best[1]
        cov = None
        if tot:
            under = np.zeros_like(lay)
            for c in ctx:
                under |= al(c)
            cov = round(float((lay & under).sum() / tot), 3)
        out.append((rel, ctx, cov))
    return out


def main():
    db = sqlite3.connect(DB)
    rows = db.execute("select rel, folder, base, w, h, n, opaque_px, shadow_px, semi_px from sprites").fetchall()
    info = {r[0]: r for r in rows}
    group = collections.defaultdict(set)                 # (folder, w, h, n) -> bases with that frame layout
    for rel, fo, b, w, h, n, *_ in rows:
        group[(fo, w, h, n)].add(b)

    def rel_of(fo, b, w, h, n):
        return "images/CHAR/%s/%s-%d-%d-%d.png" % (fo, b, w, h, n)

    def visible(rel):
        return rel in info and info[rel][6] > 0

    def pose_of(fo, b, w, h, n):
        names, parts, pose = group[(fo, w, h, n)], b.split("_"), None
        for k in range(1, len(parts) + 1):
            p = "_".join(parts[:k])
            if p not in names:
                continue
            if pose is None:
                pose = p
            elif kind_of(p[len(pose):])[0] == "other":
                pose = p
        return pose or b

    # blank-face outfit bodies: <small face file>_<word>
    containers, by_stem = {}, collections.defaultdict(list)
    for rel, fo, b, w, h, n, op, sh, se in rows:
        if "_face_" not in b or "glow" in b or "_" not in b or op / max(1, n) < CONTAINER_MIN_PX:
            continue
        stem, word = b.rsplit("_", 1)
        s = info.get(rel_of(fo, stem, w, h, n))
        if s is not None and "_face_" in stem and s[6] / max(1, n) < FACE_MAX_PX:
            containers[rel] = stem
            by_stem[(fo, stem, w, h, n)].append((word, rel))

    res, jobs = {}, collections.defaultdict(lambda: ([], {}, {}))
    for rel, fo, b, w, h, n, op, sh, se in rows:
        pf = op / max(1, n)
        pose = pose_of(fo, b, w, h, n)
        k, rank = kind_of(b[len(pose):])
        if op == 0 and sh == 0:
            role, recipe = "empty", "none"
        elif op == 0:
            role, recipe = "shadow", "shadow"
        elif "glow" in b:
            role, recipe = "glow", "none"
        elif rel in containers:
            role, recipe = "outfit_body", "body"
        elif "_face" in b and se > 0.6 * op:
            role, recipe = "ghost", "face"
        elif "_face" in b and pf < FACE_MAX_PX:
            role, recipe = "face", "face"
        elif "_face" in b:
            role, recipe = "head_face", "face"
        else:
            role, recipe = (k, "body") if k == "body" else (k, "p")
        res[rel] = dict(role=role, recipe=recipe, pose=pose, ctx=[], cov=None, note="")
        if role not in NEED_CONTEXT:
            continue
        if role in ("face", "head_face", "ghost"):
            rank = RANK["face"]
        fixed, note = [], "pose rules"
        if fo != "celica" and role in ("face", "head_face", "ghost"):
            cands = sorted(by_stem.get((fo, re.sub(r"_talk$", "", b), w, h, n)) or [],
                           key=lambda c: OUTFIT_PREF.index(c[0]) if c[0] in OUTFIT_PREF else 9)
            if cands:
                fixed, note = [cands[0][1]], "on its outfit body"
        if not fixed:
            for suf, r in (("", 0), ("_breasts", 4)):
                c = rel_of(fo, pose + suf, w, h, n)
                if r < rank and c != rel and visible(c):
                    fixed.append(c)
            if "_face_" in b:
                # a face that belongs to another layer: "<pose>_grab_<x>_demoness_face_normal" lies on the demoness
                # grab layer "<pose>_grab_<x>_demoness" (the part of the name before "_face_")
                owner = rel_of(fo, b[:b.index("_face_")], w, h, n)
                if owner != rel and owner not in fixed and b[:b.index("_face_")] != pose and visible(owner):
                    fixed.append(owner)
                    note = "on its owner layer"
        layers, heads, fixed_by = jobs[(fo, w, h, n, pose)]
        layers.append((rel, rank))
        fixed_by[rel] = fixed
        res[rel]["note"] = note
        if not heads and fo == "celica":
            for t in HEADS.split("|"):
                files = []
                hb = [x for x in group[(fo, w, h, n)] if re.fullmatch(re.escape(pose) + r"_head%shair_\w*b" % t, x)]
                hb.sort(key=lambda x: (not x.endswith("_normalb"), x))
                for name, r in ((hb[0] if hb else None, 1), (pose + "_head%sneck" % t, 2), (pose + "_head%s" % t, 10)):
                    if name and visible(rel_of(fo, name, w, h, n)):
                        files.append((r, rel_of(fo, name, w, h, n)))
                if files:
                    heads[t] = files

    # a face on its outfit body needs nothing else; every other layer may get the best-covering head of its pose
    work = [(key[1], key[2], layers, heads, fixed, {l for l, _ in layers if res[l]["note"] == "on its outfit body"})
            for key, (layers, heads, fixed) in jobs.items()]
    work.sort(key=lambda j: -len(j[2]))
    print("measuring context for %d layers in %d poses ..." % (sum(len(j[2]) for j in work), len(work)), flush=True)
    with Pool(max(2, (os.cpu_count() or 4) - 2)) as pool:
        for part in pool.imap_unordered(_cover_job, work, chunksize=4):
            for rel, ctx, cov in part:
                res[rel]["ctx"], res[rel]["cov"] = ctx, cov

    db.execute("DROP TABLE IF EXISTS roles")
    db.execute("""CREATE TABLE roles(rel TEXT PRIMARY KEY, role TEXT, recipe TEXT, context TEXT, coverage REAL,
                  note TEXT, pose TEXT)""")
    db.executemany("INSERT INTO roles VALUES (?,?,?,?,?,?,?)",
                   [(rel, r["role"], r["recipe"], json.dumps(r["ctx"]), r["cov"], r["note"], r["pose"]) for rel, r in res.items()])
    db.commit()
    c = collections.Counter((r["role"], r["recipe"]) for r in res.values())
    for (role, recipe), v in sorted(c.items(), key=lambda x: -x[1]):
        cv = [r["cov"] for r in res.values() if r["role"] == role and r["cov"] is not None]
        low = sum(1 for x in cv if x < 0.8)
        print("  %-12s %-7s %6d   %s" % (role, recipe, v, ("coverage<80%%: %d" % low) if cv else ""))
    print("roles written:", len(res))


if __name__ == "__main__":
    main()
