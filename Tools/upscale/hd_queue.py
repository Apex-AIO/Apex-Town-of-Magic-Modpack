"""hd_queue.py - keeps the HD ledger and queues every NEW character image the game has used.  (no rendering)

Run after playing (the recorder in claude_debug.rpy writes game/claude_debug/used_images.txt):
    python hd_queue.py
What it does
  * reads every image the game loaded (game/claude_debug/used_images.txt + saved copies in Tools/debug/logs)
  * character pictures only (images/CHAR/...); male characters are skipped (the game tags them "Male");
    Celica, women and monsters/creatures are kept
  * status of each picture:  rendered (an @2 file exists in the HD mod) / queued (in a sets/*.txt list) /
    skipped (male) / NEW
  * NEW pictures are added to sets/pending.txt  ->  run_hd_pending.bat renders them (already-rendered files are
    always skipped by hd_batch.py, so nothing is ever rendered twice)
  * writes the full ledger: Upscale/hd_ledger.tsv  (every picture ever seen and its status)
"""
import os, re, sys, glob, shutil, time, collections

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.normpath(os.path.join(HERE, "..", ".."))
GAME = os.path.normpath(os.path.join(WS, "..", "game"))
SCRIPTS = os.path.join(WS, "Extracted", "scripts")
MOD = os.path.join(WS, "Mods", "hd_sprites_mod")
SETS = os.path.join(HERE, "sets")
LOGS = os.path.join(WS, "Tools", "debug", "logs")
LEDGER = os.path.join(WS, "Upscale", "hd_ledger.tsv")
USED = os.path.join(GAME, "claude_debug", "used_images.txt")


def norm(path):
    p = path.strip().replace("\\", "/").lstrip("/")
    if not p.startswith("images/"):
        p = "images/" + p
    return re.sub(r"@\d+(?=\.png$)", "", p)


def genders():
    """image folder -> True if the game tags that character "Male" (from the decompiled game scripts)"""
    var_folder, var_props = {}, {}
    for f in glob.glob(os.path.join(SCRIPTS, "initialize_variables_*.rpy")):
        txt = open(f, encoding="utf8", errors="replace").read()
        for m in re.finditer(r"(e_\w+)\s*=\s*Enemy\([^\n]*?image\s*=\s*\"([^\"]+)\"", txt):
            var_folder.setdefault(m.group(1), m.group(2))
        for m in re.finditer(r"(e_\w+)\.properties\s*=\s*\[([^\]]*)\]", txt):
            var_props.setdefault(m.group(1), m.group(2))
    male = {}
    for v, folder in var_folder.items():
        props = var_props.get(v, "")
        male[folder] = male.get(folder, False) or ('"Male"' in props)
    return male


def main():
    sources = [USED] + sorted(glob.glob(os.path.join(LOGS, "used_images*.txt")))
    seen = collections.OrderedDict()
    for src in sources:
        if not os.path.exists(src):
            continue
        for line in open(src, encoding="utf8", errors="replace"):
            f = line.split("\t")[0]
            if "CHAR/" not in f or not f.strip().endswith(".png"):
                continue
            seen.setdefault(norm(f), src)
    # keep a dated copy of this session's list (the recorder keeps adding to the live one)
    if os.path.exists(USED):
        os.makedirs(LOGS, exist_ok=True)
        shutil.copy2(USED, os.path.join(LOGS, "used_images_%s.txt" % time.strftime("%Y%m%d_%H%M")))

    male = genders()
    in_sets = {}
    for sf in glob.glob(os.path.join(SETS, "*.txt")):
        name = os.path.splitext(os.path.basename(sf))[0]
        for l in open(sf, encoding="utf8"):
            if l.strip():
                in_sets.setdefault(norm(l), name)

    rows, new = [], []
    for rel in seen:
        folder = rel.split("/")[2]
        rendered = os.path.exists(os.path.join(MOD, rel.replace("/", os.sep))[:-4] + "@2.png")
        if rendered:
            status = "rendered"
        elif male.get(folder, False):
            status = "skipped (male)"
        elif rel in in_sets:
            status = "queued (%s)" % in_sets[rel]
        else:
            status = "NEW"
            new.append(rel)
        rows.append((rel, folder, status))

    if new:
        pend = os.path.join(SETS, "pending.txt")
        have = set(norm(l) for l in open(pend, encoding="utf8")) if os.path.exists(pend) else set()
        with open(pend, "a", encoding="utf8") as o:
            for r in new:
                if r not in have:
                    o.write(r + "\n")
        for i, (rel, folder, status) in enumerate(rows):
            if status == "NEW":
                rows[i] = (rel, folder, "queued (pending) - new this run")

    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "w", encoding="utf8") as o:
        o.write("image\tcharacter\tstatus\n")
        for r in sorted(rows):
            o.write("\t".join(r) + "\n")

    # the to-do list = everything queued in any set that has no HD file yet (collected over every play session
    # since the last render - a picture is never listed twice)
    count = collections.Counter(s.split(" (")[0] for _, _, s in rows)
    todo = [(rel, folder) for rel, folder, s in rows if s.startswith("queued")]
    print("TO RENDER since the last ComfyUI run: %d pictures" % len(todo))
    for folder, n in collections.Counter(f for _, f in todo).most_common():
        added = sum(1 for r in new if r.split("/")[2] == folder)
        print("   %-24s %4d%s" % (folder, n, ("   (%d added by this check)" % added) if added else ""))
    print("added by this check: %d    already rendered: %d    skipped (male): %d    pictures seen in total: %d" % (
        len(new), count["rendered"], count["skipped"], len(rows)))
    # what the run will really do (art catalog: identical sprites are rendered once, glow/shadow/empty need no AI)
    try:
        sys.path.insert(0, os.path.join(WS, "Tools", "art"))
        import artdb
        keys, copies, no_ai, unknown = set(), 0, 0, 0
        done = {artdb.twin_key(r) for r, _, s in rows if s == "rendered"}
        for rel, _ in todo:
            i = artdb.info(rel)
            if i is None:
                unknown += 1
                continue
            if i["recipe"] in ("none", "shadow"):
                no_ai += 1
            k = artdb.twin_key(rel)
            if k in keys or k in done:
                copies += 1
            keys.add(k)
        print("the run: %d to render + %d copied from an identical sprite; %d need no AI (glow/shadow/empty)%s"
              % (len(todo) - copies, copies, no_ai, ("  [%d not in the art catalog - run Tools/art/catalog.py]" % unknown)
                 if unknown else ""))
    except Exception as e:
        print("(art catalog not available: %s)" % e)
    print("ledger:", LEDGER)


if __name__ == "__main__":
    main()
