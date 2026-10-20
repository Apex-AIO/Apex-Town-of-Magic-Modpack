# apex_mods_loader.rpe.py - Apex's Modpack Manager: loads YOUR mods from the "mods" folder next to the "game" folder.
#
# Ren'Py runs *.rpe.py files in game/ very early, before it looks at any game file.  This loader:
#   * finds every mod folder in  <Town of Magic>/mods/  (folders starting with "_" or "." are ignored)
#   * reads its mod_info.txt (name, author, version, description, settings ...)
#   * for every mod that is switched ON: its scripts (.rpy/.rpyc) load under their own names (mods/<mod>/...), and
#     every other file (pictures, sounds) is visible to the game by its path inside the mod folder - so a mod's
#     images/CHAR/celica/celica_top_normal-530-530-1.png REPLACES the game's picture of that name
#   * catches errors from a mod: the game keeps running, the mod is switched off, and the Mod Manager explains what
#     went wrong in plain words (also written to <mod folder>/ERROR REPORT.txt)
#   * if the game crashed while starting because of a mod (a typo in a script), that mod is switched off on the next
#     start and the crash is explained
# Everything it knows is in renpy.apex_mods (read by apex_modpack_manager.rpy).  It never stops the game: any problem
# in here is written to mods/_manager/loader_log.txt.

import os, io, re, json, time, traceback as _tb
import renpy

APEX_LOADER_VERSION = 1
# files that can replace / add game files by their path inside the mod (pictures, sounds, fonts, videos)
ASSET_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".svg", ".ogg", ".mp3", ".wav", ".opus", ".flac",
              ".ttf", ".otf", ".webm", ".mp4", ".avi", ".mkv", ".json")


def _apex_mods_loader():
    base = renpy.config.basedir
    mods = os.path.join(base, "mods")
    data = os.path.join(mods, "_manager")
    state = dict(version=APEX_LOADER_VERSION, root=mods, mods=[], files={}, block=[], conflicts=[], errors=[], log=[],
                 settings_file=os.path.join(data, "settings.json"), crash_recovered=[])
    renpy.apex_mods = state

    def log(msg):
        state["log"].append(msg)
        try:
            os.makedirs(data, exist_ok=True)
            with io.open(os.path.join(data, "loader_log.txt"), "a", encoding="utf8") as f:
                f.write(u"%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
        except Exception:
            pass

    if not os.path.isdir(mods):
        return
    if os.environ.get("APEX_NO_USER_MODS"):
        return                                       # the modpack's own build: never compile anyone's mods into it
    os.makedirs(data, exist_ok=True)

    # ---- settings (which mods are on, their gear settings) - kept in a file, persistent data isn't loaded yet
    settings = {"enabled": {}, "values": {}, "auto_off": {}}
    try:
        with io.open(state["settings_file"], encoding="utf8") as f:
            s = json.load(f)
        if isinstance(s, dict):
            for k in settings:
                if isinstance(s.get(k), dict):
                    settings[k] = s[k]
    except Exception:
        pass
    state["settings"] = settings

    def save_settings():
        try:
            tmp = state["settings_file"] + ".tmp"
            with io.open(tmp, "w", encoding="utf8") as f:
                json.dump(settings, f, indent=2, sort_keys=True)
            os.replace(tmp, state["settings_file"])
        except Exception as e:
            log("could not save settings: %r" % (e,))
    state["save_settings"] = save_settings

    # ---- crash recovery: the last start never reached the main menu and Ren'Py wrote an error that names a mod
    boot_file = os.path.join(data, "boot.json")
    try:
        with io.open(boot_file, encoding="utf8") as f:
            boot = json.load(f)
    except Exception:
        boot = {}
    if boot.get("starting"):
        for fn in ("errors.txt", "traceback.txt"):
            p = os.path.join(base, fn)
            try:
                if os.path.getmtime(p) >= boot.get("time", 0) - 5:
                    text = io.open(p, encoding="utf8", errors="replace").read()
                    for m in set(re.findall(r"mods[/\\]([^/\\\r\n\"']+)[/\\]", text)):
                        if not m.startswith("_") and settings["enabled"].get(m, True):
                            settings["enabled"][m] = False
                            settings["auto_off"][m] = {"when": time.strftime("%Y-%m-%d %H:%M"), "why": "crash",
                                                       "report": text[-6000:], "file": fn}
                            state["crash_recovered"].append(m)
                            log("the last start crashed in mod '%s' (%s) - switched it off" % (m, fn))
            except Exception:
                pass
        save_settings()
    try:
        with io.open(boot_file, "w", encoding="utf8") as f:
            json.dump({"starting": True, "time": time.time()}, f)
    except Exception:
        pass

    # ---- find the mods
    def read_info(folder):
        info = {"name": os.path.basename(folder), "author": "", "version": "", "description": "", "made_for_game": "",
                "settings": [], "warnings": []}
        p = os.path.join(folder, "mod_info.txt")
        if not os.path.exists(p):
            info["warnings"].append("No mod_info.txt - the folder name is used as the mod's name.")
            return info
        for n, line in enumerate(io.open(p, encoding="utf8", errors="replace"), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                info["warnings"].append("mod_info.txt line %d has no '=': %s" % (n, line[:60]))
                continue
            k, v = [x.strip() for x in line.split("=", 1)]
            k = k.lower().replace(" ", "_")
            if k == "setting":
                parts = [x.strip() for x in v.split("|")]
                if len(parts) < 3:
                    info["warnings"].append("mod_info.txt line %d: a setting needs at least: key | type | default" % n)
                    continue
                info["settings"].append({"key": parts[0], "type": parts[1].lower(), "default": parts[2],
                                         "min": parts[3] if len(parts) > 3 else "", "max": parts[4] if len(parts) > 4 else "",
                                         "label": parts[5] if len(parts) > 5 else parts[0]})
            else:
                info[k] = v
        return info

    names_seen = {}
    for entry in sorted(os.listdir(mods), key=lambda x: x.lower()):
        folder = os.path.join(mods, entry)
        if not os.path.isdir(folder) or entry.startswith(("_", ".")):
            continue
        info = read_info(folder)
        if entry.lower() == "game" or os.path.isdir(os.path.join(folder, "game")):
            # mods downloaded from the forums have no mod_info.txt: that is normal, not a problem
            info["warnings"] = [w for w in info["warnings"] if not w.startswith("No mod_info.txt")]
        info["id"] = entry
        info["folder"] = folder
        on = bool(settings["enabled"].get(entry, True))          # a new mod dropped in starts ON
        info["enabled"] = on
        info["auto_off"] = settings["auto_off"].get(entry)
        info["scripts"], info["assets"] = [], []
        # Mods downloaded for this game come as a "game" folder (the zip's game\... goes into the game folder).  A mod folder
        # with a "game" folder inside - or a folder that is itself called "game" - is loaded the same way: every file in it,
        # scripts included, takes the place of the game file with the same path (a modified copy of a game script REPLACES
        # the original; a new file is added).
        gameroot = None
        if os.path.isdir(os.path.join(folder, "game")):
            gameroot = os.path.join(folder, "game")
        elif entry.lower() == "game":
            gameroot = folder
        info["game_style"] = gameroot is not None
        if gameroot == folder:
            info["warnings"].append("This folder is called 'game', so it is loaded like a mod's game folder. Tip: put it inside a folder named after the mod (mods\\<ModName>\\game) so you can tell mods apart.")
        if on:
            for dp, dns, fns in os.walk(gameroot or folder):
                dns[:] = [d for d in dns if not d.startswith((".", "_"))]
                for fn in fns:
                    full = os.path.join(dp, fn)
                    rel = os.path.relpath(full, gameroot or folder).replace("\\", "/")
                    low = fn.lower()
                    if low in ("mod_info.txt", "error report.txt", "log.txt") or low.endswith((".bak", ".tmp")):
                        continue
                    if gameroot and low.endswith((".rpy", ".rpyc", "_ren.py", ".rpym", ".rpymc")):
                        # a game-style script takes the game's own path.  Its compiled twin is not listed (Ren'Py finds it
                        # next to it); the game's own compiled copy inside the archive is blocked by name instead.
                        stem = rel[:-4] if low.endswith(".rpy") else rel[:-7] if low.endswith("_ren.py") else rel[:-5] if low.endswith(".rpym") else None
                        if stem is None and os.path.exists(full[:-1]):
                            # the mod's compiled twin: Ren'Py reads "<name>.rpyc" through the game's file system, which would
                            # hand it the ORIGINAL game's compiled script from the archive - so it must be listed too
                            if rel not in names_seen:
                                names_seen[rel] = entry
                                state["files"][rel] = (gameroot, full)
                            continue
                        if rel in names_seen:
                            state["conflicts"].append((rel, names_seen[rel], entry))
                            continue
                        names_seen[rel] = entry
                        state["files"][rel] = (gameroot, full)
                        if stem is not None:
                            state["block"].append(stem + (".rpymc" if low.endswith(".rpym") else ".rpyc"))
                        info["scripts"].append(rel)
                        continue
                    if low.endswith((".rpy", ".rpyc", "_ren.py", ".rpym", ".rpymc")):
                        # scripts: their own name, so two mods can both have "script.rpy"
                        if low.endswith(".rpyc") and os.path.exists(full[:-1]):
                            continue                                     # Ren'Py pairs it with the .rpy itself
                        name = "mods/%s/%s" % (entry, rel)
                        state["files"][name] = (base, full)
                        info["scripts"].append(rel)
                    else:
                        if not gameroot:
                            state["files"]["mods/%s/%s" % (entry, rel)] = (base, full)       # always reachable by own path
                        if not low.endswith(ASSET_EXTS):
                            continue                                     # notes / docs: only by their own path
                        if rel in names_seen:
                            state["conflicts"].append((rel, names_seen[rel], entry))
                            continue
                        names_seen[rel] = entry
                        state["files"][rel] = (gameroot or folder, full)            # and by the game's path (replaces / adds)
                        info["assets"].append(rel)
        state["mods"].append(info)
        log("mod '%s' (%s): %s, %d scripts, %d files" % (entry, info["name"], "ON" if on else "off",
                                                         len(info["scripts"]), len(info["assets"])))

    if not state["files"]:
        return

    # ---- make the files visible to Ren'Py: in its file list (first, so a mod's picture wins) and when opened
    lower = {k.lower(): k for k in state["files"]}

    def scan(add, seen):
        # (folder, name): Ren'Py opens folder + "/" + name, and writes a script's .rpyc next to it
        for name, (dn, full) in state["files"].items():
            add(dn, name, renpy.loader.game_files, seen)
            renpy.loader.loadable_cache[name] = True     # Ren'Py looks names up in their real spelling too
        for name in state["block"]:
            seen.add(name)                               # the game's compiled copy of a script a mod replaces is not listed

    def open_cb(name):
        k = state["files"].get(name) or state["files"].get(lower.get(name.lower(), ""))
        if k:
            try:
                return renpy.loader.open_file(k[1], "rb")
            except Exception:
                return None
        return None

    renpy.loader.scandirfiles_callbacks.insert(0, scan)
    renpy.loader.file_open_callbacks.insert(0, open_cb)


def _apex_mod_of(text):
    m = re.findall(r"mods[/\\]([^/\\\r\n\"']+)[/\\]", text or "")
    return m[-1] if m else None


# plain-words explanations for the errors modders hit most
_HINTS = [
    (r"NameError: name '([^']+)' is not defined",
     "The game doesn't know the name '{0}'. Check the spelling (capitals matter), and that it's defined BEFORE it's "
     "used (a lower 'init' number runs first)."),
    (r"AttributeError: '([^']+)' object has no attribute '([^']+)'",
     "'{1}' doesn't exist on this {0}. Check the spelling, or look up the right name in the guide."),
    (r"Couldn't find file '([^']+)'",
     "The file '{0}' is missing. Check the file name (capitals and spaces matter) and that it's inside your mod's "
     "folder at that path."),
    (r"is not a known label|label '([^']+)' ",
     "The script jumps or calls to a label that doesn't exist. Check the label's name."),
    (r"IndentationError|unexpected indent|unindent does not match",
     "A line is indented wrongly. Use 4 spaces per level (not tabs) and keep lines in one block lined up."),
    (r"SyntaxError|expected ':'|invalid syntax|end of line expected",
     "A line isn't written correctly. Common causes: a missing ':' at the end of a line that starts a block, an "
     "unclosed quote \" or bracket (, or a typo in a keyword."),
    (r"TypeError: (\w+)\(\) (got an unexpected keyword argument '[^']+'|missing \d+ required)",
     "A function was given the wrong settings: {1}. Compare with the example in the template or guide."),
    (r"KeyError: (.+)", "The name {0} isn't in that list/dictionary. Check the spelling."),
    (r"ZeroDivisionError", "Something was divided by zero - check numbers that can be 0."),
]


def apex_explain(text):
    for rx, msg in _HINTS:
        m = re.search(rx, text or "")
        if m:
            g = [x or "" for x in m.groups()] + ["", ""]
            return msg.format(*g)
    return "Read the last lines of the report below: they name the file and line where it went wrong."


_APEX_SEEN = set()


def _apex_exception_handler(short, full, traceback_fn=None):
    """Ren'Py calls this for any error while the game runs.  Errors from a mod in the mods folder are recorded,
    that mod is switched off for the next start, and the game carries on.  Everything else: Ren'Py as usual."""
    try:
        if "apex_modpack/" in full and hash(full[-600:]) not in _APEX_SEEN and len(_APEX_SEEN) < 50:
            # an error inside one of Apex's own mods: keep a copy next to the game's own traceback.txt (each different error once)
            _APEX_SEEN.add(hash(full[-600:]))
            with io.open(os.path.join(renpy.config.gamedir, "apex_mod_errors.txt"), "a", encoding="utf8") as f:
                f.write(u"==== %s  UNCAUGHT ERROR in Apex's mods (the game showed its error screen)\n%s\n"
                        % (time.strftime("%Y-%m-%d %H:%M:%S"), full.rstrip()))
    except Exception:
        pass
    try:
        st = getattr(renpy, "apex_mods", None)
        mod = _apex_mod_of(full)
        if not st or not mod or mod.startswith("_"):
            return False
        reported = st.setdefault("reported", set())
        if mod in reported:
            return True            # already reported this session (a callback that fails every frame): no more files, no more pop-ups
        reported.add(mod)
        where = re.findall(r'File "(mods/[^"]+)", line (\d+)', full)
        rec = {"mod": mod, "when": time.strftime("%Y-%m-%d %H:%M:%S"), "short": short.strip()[-1500:],
               "where": "%s line %s" % where[-1] if where else "", "hint": apex_explain(full)}
        st["errors"].append(rec)
        st["settings"]["enabled"][mod] = False
        st["settings"]["auto_off"][mod] = {"when": rec["when"], "why": "error", "report": full[-6000:], "hint": rec["hint"],
                                           "where": rec["where"]}
        st["save_settings"]()
        folder = os.path.join(st["root"], mod)
        if os.path.isdir(folder):
            with io.open(os.path.join(folder, "ERROR REPORT.txt"), "w", encoding="utf8") as f:
                f.write(u"Your mod '%s' had an error on %s and was switched off.\n\n" % (mod, rec["when"]))
                f.write(u"WHERE:  %s\nWHAT TO DO:  %s\n\nFULL REPORT (the last lines matter most):\n\n%s\n"
                        % (rec["where"] or "see below", rec["hint"], full))
        try:
            renpy.exports.notify("Mod '%s' had an error and was switched off - see Apex's Modpack Manager." % mod)
        except Exception:
            pass
        return True
    except Exception:
        return False


try:
    _apex_mods_loader()
except Exception:
    try:
        p = os.path.join(renpy.config.basedir, "mods", "_manager", "loader_log.txt")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with io.open(p, "a", encoding="utf8") as f:
            f.write(u"LOADER ERROR (no user mods loaded this time):\n%s\n" % _tb.format_exc())
    except Exception:
        pass

renpy.apex_explain = apex_explain
renpy.apex_exception_handler = _apex_exception_handler
