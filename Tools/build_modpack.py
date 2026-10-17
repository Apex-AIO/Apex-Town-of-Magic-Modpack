"""build_modpack.py - packs every module of Apex's Modpack into ONE file: Apex_Modpack.rpa (drag & drop into game/).

    python Tools/build_modpack.py            build + install into this game (the game must be closed)
    python Tools/build_modpack.py --no-install

Steps
  1. reads Mods/modpack.json (modules, revisions, which file goes where in the archive)
  2. writes apex_build_info.rpy (versions + "last updated" dates = newest file of each module / of everything)
  3. compiles the scripts with the game's own Ren'Py (so players never need the .rpy sources)
  4. writes the archive: compiled scripts + icons + HD pictures
  5. Dist/Apex_Modpack_v<version>.zip  =  game/Apex_Modpack.rpa + "READ ME - Install.txt"
     and (unless --no-install) puts the .rpa into this game's game folder, replacing the loose mod files
"""
import os, sys, json, time, glob, shutil, pickle, zlib, random, subprocess, zipfile, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.normpath(os.path.join(WS, ".."))
GAME = os.path.join(ROOT, "game")
MODS = os.path.join(WS, "Mods")
DIST = os.path.join(WS, "Dist")
RPA_NAME = "Apex_Modpack.rpa"
STAGE = "apex_modpack"                     # folder (in game/ while compiling, and inside the archive)
PY = os.path.join(ROOT, "lib", "py3-windows-x86_64", "python.exe")
LOOSE = ["tom_mod_guard", "nel_taunt", "stutter_fix", "appearance_unlock", "morning_dildo", "hscene_loop",
         "hd_sprites", "apex_modpack_manager", "apex_build_info"]       # old loose installs of the same scripts


def expand(files):
    """{source: archive path} -> [(source file, archive path)]; a source ending in / is a whole folder"""
    out = []
    for src, dst in files.items():
        full = os.path.join(MODS, src)
        if src.endswith("/"):
            for dp, _, fns in os.walk(full):
                for fn in sorted(fns):
                    p = os.path.join(dp, fn)
                    out.append((p, dst + os.path.relpath(p, full).replace(os.sep, "/")))
        else:
            if not os.path.exists(full):
                sys.exit("missing file: " + full)
            out.append((full, dst))
    return out


def newest(paths):
    return datetime.date.fromtimestamp(max(os.path.getmtime(p) for p in paths)).isoformat() if paths else None


def write_rpa(path, entries):
    """entries: [(archive name, bytes or file path)] -> Ren'Py RPA-3.0 archive"""
    key = random.randint(0x10000000, 0x7fffffff)
    index = {}
    with open(path, "wb") as f:
        f.write(b"RPA-3.0 %016x %08x\n" % (0, 0))
        for name, data in entries:
            if not isinstance(data, bytes):
                with open(data, "rb") as s:
                    data = s.read()
            off = f.tell()
            f.write(data)
            index[name] = [(off ^ key, len(data) ^ key, b"")]
        ioff = f.tell()
        f.write(zlib.compress(pickle.dumps(index, protocol=2)))
        f.seek(0)
        f.write(b"RPA-3.0 %016x %08x\n" % (ioff, key))


def check_manifest(man):
    """catch mistakes in modpack.json before anything is built"""
    import re
    guard = open(os.path.join(MODS, "_shared", "tom_mod_guard.rpy"), encoding="utf8").read()
    tested = re.search(r'TOM_TESTED_GAME = "([^"]+)"', guard).group(1)
    errs = []
    if tested != man["made_for_game"]:
        errs.append("made_for_game %s but the guard's TOM_TESTED_GAME is %s" % (man["made_for_game"], tested))
    ids = [m["id"] for m in man["modules"]]
    if len(ids) != len(set(ids)):
        errs.append("two modules have the same id")
    for m in man["modules"]:
        keys = set()
        for s in (m.get("settings") or []) + (m.get("subs") or []):
            k, d = s.get("key"), s.get("default")
            if not k or k in keys:
                errs.append("%s: missing or repeated setting key %r" % (m["id"], k))
            keys.add(k)
            if s.get("type") == "bool":
                if not isinstance(d, bool):
                    errs.append("%s.%s: a bool needs true/false as default" % (m["id"], k))
            elif not (isinstance(d, (int, float)) and s.get("min", d) <= d <= s.get("max", d) and s.get("step", 1) > 0):
                errs.append("%s.%s: default must be a number between min and max (and step > 0)" % (m["id"], k))
        for mo in re.finditer(r"\{(\w+)\}", m["desc"] + " ".join(s.get("desc", "") for s in m.get("subs") or [])):
            if mo.group(1) not in keys:
                errs.append("%s: {%s} in a description is not one of its settings" % (m["id"], mo.group(1)))
    if errs:
        sys.exit("modpack.json problems:\n  " + "\n  ".join(errs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-install", action="store_true")
    a = ap.parse_args()
    if "TownOfMagic.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout:
        sys.exit("Close Town of Magic first (the game keeps its archives open).")
    man = json.load(open(os.path.join(MODS, "modpack.json"), encoding="utf8"))

    core = expand(man["core"]["files"])
    mods = [(m, expand(m["files"])) for m in man["modules"]]
    every = [p for p, _ in core] + [p for _, fl in mods for p, _ in fl] + [os.path.join(MODS, "modpack.json")]
    build = dict(name=man["name"], version=man["version"], made_for_game=man["made_for_game"], tip_url=man["tip_url"],
                 core_rev=man["core"]["rev"], date=newest(every), built=time.strftime("%Y-%m-%d %H:%M"),
                 modules=[dict(id=m["id"], title=m["title"], rev=m["rev"], desc=m["desc"], wip=m.get("wip", ""),
                               settings=m.get("settings", []), subs=m.get("subs", []),
                               date=newest([p for p, _ in fl])) for m, fl in mods])
    check_manifest(man)
    info = ("# written by Tools/build_modpack.py - do not edit\ninit -20 python:\n    APEX_BUILD = %r\n" % (build,))

    # --- stage the scripts in game/apex_modpack and compile them with the game's Ren'Py
    if os.path.exists(os.path.join(GAME, RPA_NAME)):
        os.replace(os.path.join(GAME, RPA_NAME), os.path.join(GAME, RPA_NAME + ".old"))   # else: defined twice
    for n in LOOSE:
        for ext in (".rpy", ".rpyc"):
            p = os.path.join(GAME, n + ext)
            if os.path.exists(p):
                os.remove(p)
    shutil.rmtree(os.path.join(GAME, "clothing_remover"), ignore_errors=True)
    stage = os.path.join(GAME, STAGE)
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    scripts, others = [], []
    for src, dst in core + [x for _, fl in mods for x in fl]:
        (scripts if dst.endswith(".rpy") else others).append((src, dst))
    for src, dst in scripts:
        shutil.copy2(src, os.path.join(stage, os.path.basename(dst)))
    with open(os.path.join(stage, "apex_build_info.rpy"), "w", encoding="utf8") as f:
        f.write(info)
    print("compiling with the game's Ren'Py ...", flush=True)
    errs = os.path.join(ROOT, "errors.txt")
    if os.path.exists(errs):
        os.remove(errs)                      # an old error report must not fail this build
    r = subprocess.run([PY, os.path.join(ROOT, "TownOfMagic.py"), ROOT, "compile"], capture_output=True, text=True)
    if r.returncode != 0 or os.path.exists(errs):
        print(r.stdout[-3000:], r.stderr[-3000:])
        if os.path.exists(errs):
            print(open(errs, encoding="utf-8-sig", errors="replace").read()[:4000].encode("ascii", "replace").decode())
        shutil.rmtree(stage, ignore_errors=True)
        if os.path.exists(os.path.join(GAME, RPA_NAME + ".old")):
            os.replace(os.path.join(GAME, RPA_NAME + ".old"), os.path.join(GAME, RPA_NAME))
        sys.exit("COMPILE FAILED - nothing was packed")

    entries = []
    for fn in sorted(os.listdir(stage)):
        if fn.endswith(".rpyc"):
            with open(os.path.join(stage, fn), "rb") as s:
                entries.append(("%s/%s" % (STAGE, fn), s.read()))
    entries += [(dst, src) for src, dst in others]
    shutil.rmtree(stage)

    # --- archive + zip
    out = os.path.join(DIST, "Apex_Modpack_v%s" % man["version"])
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, "game"))
    rpa = os.path.join(out, "game", RPA_NAME)
    write_rpa(rpa, entries)
    shutil.copy2(os.path.join(MODS, "apex_modpack_manager", "READ ME - Install.txt"), out)
    zpath = out + ".zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:          # pictures are already compressed
        z.write(os.path.join(out, "READ ME - Install.txt"), "READ ME - Install.txt")
        z.write(rpa, "game/" + RPA_NAME)
    old = os.path.join(GAME, RPA_NAME + ".old")
    if not a.no_install:
        shutil.copy2(rpa, os.path.join(GAME, RPA_NAME))
        if os.path.exists(old):
            os.remove(old)
    elif os.path.exists(old):
        os.replace(old, os.path.join(GAME, RPA_NAME))

    n_scripts = sum(1 for n, _ in entries if n.endswith(".rpyc"))
    print("archive: %d files (%d scripts), %.1f MB" % (len(entries), n_scripts, os.path.getsize(rpa) / 1e6))
    shutil.rmtree(out)                                                  # the zip is the deliverable
    print("last updated:", build["date"])
    for m in build["modules"]:
        print("   r%-4s %-40s %s" % (m["rev"], m["title"], m["date"]))
    print("zip:", zpath)
    print("installed into this game" if not a.no_install else "not installed (--no-install)")


def cleanup_after_failure():
    """a failed build must never leave half-built scripts in game/ or the game without its modpack"""
    shutil.rmtree(os.path.join(GAME, STAGE), ignore_errors=True)
    old = os.path.join(GAME, RPA_NAME + ".old")
    if os.path.exists(old):
        os.replace(old, os.path.join(GAME, RPA_NAME))


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        if not (isinstance(e, SystemExit) and e.code in (0, None)):
            cleanup_after_failure()
        raise
