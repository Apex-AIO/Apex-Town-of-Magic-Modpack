"""artdb.py - small read-only access to the art catalog (Catalog/art.db) for other tools (hd_batch.py, hd_queue.py).

    from artdb import info, twin_key
    info("images/CHAR/evie/evie_face_normal-530-530-1.png")
      -> {"role": "face", "recipe": "face", "context": [...], "coverage": 1.0, "pixhash": "...", ...}  or None
    twin_key(rel) -> a key that is equal for two sprites with identical pixels AND identical layers under them
                     (= same HD result, render once and copy)
Everything returns None when the catalog doesn't exist or doesn't know the sprite, so callers fall back to their
own rules.
"""
import os, json, sqlite3, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.normpath(os.path.join(HERE, "..", "..", "Catalog", "art.db"))
_db = [None]


def _conn():
    if _db[0] is None and os.path.exists(DB):
        _db[0] = sqlite3.connect(DB)
    return _db[0]


def info(rel):
    db = _conn()
    if db is None:
        return None
    r = db.execute("""select s.pixhash, s.opaque_px, s.n, r.role, r.recipe, r.context, r.coverage, r.pose
                      from sprites s join roles r using(rel) where s.rel=?""", (rel,)).fetchone()
    if r is None:
        return None
    return dict(pixhash=r[0], opaque_px=r[1], n=r[2], role=r[3], recipe=r[4], context=json.loads(r[5] or "[]"),
                coverage=r[6], pose=r[7])


def twin_key(rel):
    i = info(rel)
    if i is None or not i["pixhash"]:
        return None
    db = _conn()
    hs = []
    for c in i["context"]:
        row = db.execute("select pixhash from sprites where rel=?", (c,)).fetchone()
        hs.append(row[0] if row else c)
    return hashlib.md5((i["pixhash"] + "|" + "|".join(hs) + "|" + i["recipe"]).encode()).hexdigest()


def twins_of(rel):
    """other sprites with the same twin key (same HD result)"""
    db = _conn()
    i = info(rel)
    if i is None:
        return []
    k = twin_key(rel)
    out = []
    for (r,) in db.execute("select rel from sprites where pixhash=? and rel<>?", (i["pixhash"], rel)):
        if twin_key(r) == k:
            out.append(r)
    return out
