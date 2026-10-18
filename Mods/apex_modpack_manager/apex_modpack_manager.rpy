# apex_modpack_manager.rpy  -  Apex's Modpack Manager: the main-menu hub for every mod
#
# Pages (sidebar):  Overview | Apex's Mods | Your Mods | HD Project | Mod Tools | About & Support
# * Apex's Mods: the mods that ship in Apex_Modpack.rpa - switch on/off, sub-mods (tree), settings (gear).
#   Choices live in persistent (apex_mm_off / apex_mm_settings / apex_mm_test_version); tom_mod_guard.rpy reads
#   them once at start-up, so changes apply after a restart.
# * Your Mods: everyone's own mods in <Town of Magic>/mods/<mod folder>/ (loaded by game/apex_mods_loader.rpe.py,
#   helped by apex_modkit.rpy).  Their on/off state and settings live in mods/_manager/settings.json (read before
#   the game starts).  Errors are caught, explained in plain words, and the mod is switched off.
# * Leaving with unapplied changes, or quitting, asks "Restart now to apply changes?".
# * Game version check: game newer than the pack -> every Apex mod off until "Test modpack" is switched on.
# The mod list, settings, revisions, dates and the HD progress come from APEX_BUILD (Tools/build_modpack.py).

init -10 python:
    if "APEX_BUILD" not in globals():
        APEX_BUILD = None

init 1 python:
    import builtins as _apex_b      # dict/list here are Ren'Py's own types: check against the real ones

    def apex_mm_modules():
        # alphabetical, A to Z (ignoring "The", capitals and punctuation)
        return sorted((APEX_BUILD or {}).get("modules", []), key=lambda m: _apex_sort_key(m.get("title", m.get("id", ""))))

    def _apex_sort_key(s):
        import re as _re
        s = _re.sub(r"[^a-z0-9 ]", "", str(s).lower()).strip()
        return s[4:] if s.startswith("the ") else s

    def apex_mm_off_now():
        off = persistent.apex_mm_off
        return set(x for x in off if isinstance(x, str)) if isinstance(off, (_apex_b.list, _apex_b.tuple, _apex_b.set, _apex_b.frozenset)) else set()

    # what was switched off when the game started (the guard's list = what is actually running)
    APEX_MM_BOOT_OFF = TOM_BOOT_OFF

init 999 python:
    import renpy.exports as _apex_exports
    import os as _apex_os, io as _apex_io, re as _apex_re, json as _apex_json, shutil as _apex_shutil, copy as _apex_copy

    # the HD mod isn't running -> Ren'Py must not pick up the @2/@4 files on its own either
    if not tom_mod_status.get("hd_sprites", "").startswith("on"):
        config.automatic_oversampling = None

    apex_mm_ui = {"page": "overview", "detail": None, "new_name": "", "template": None, "check": None, "export": ""}
    apex_in_name = DictInputValue(apex_mm_ui, "new_name", default=False)       # click the box to type
    apex_in_export = DictInputValue(apex_mm_ui, "export", default=False)

    # ================= Apex's mods: settings (the gear) and sub-mods =================
    def apex_mm_spec(mid, key):
        return tom_setting_spec(mid, key)

    def _apex_clean(mid, key, v):
        """a value made valid for its setting, or None"""
        s = apex_mm_spec(mid, key)
        if s is None:
            return None
        d = s.get("default")
        if isinstance(d, bool):
            return v if isinstance(v, bool) else None
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")):
            return None
        v = min(max(v, s.get("min", v)), s.get("max", v))
        return int(round(v)) if isinstance(d, int) else round(float(v), 4)

    def _apex_norm(settings):
        """{mod: {key: value}} without invalid values and without values equal to the default"""
        out = {}
        if not isinstance(settings, _apex_b.dict):
            return out
        for mid, d in settings.items():
            if not isinstance(d, _apex_b.dict):
                continue
            for k, v in d.items():
                c = _apex_clean(mid, k, v)
                if c is not None and c != apex_mm_spec(mid, k).get("default"):
                    out.setdefault(mid, {})[k] = c
        return out

    APEX_MM_BOOT_SETTINGS = _apex_norm(TOM_BOOT_SETTINGS)

    def apex_mm_get(mid, key):
        v = _apex_norm(persistent.apex_mm_settings).get(mid, {}).get(key)
        if v is None:
            v = (apex_mm_spec(mid, key) or {}).get("default")
        return v

    def apex_mm_boot_value(mid, key):
        v = APEX_MM_BOOT_SETTINGS.get(mid, {}).get(key)
        return (apex_mm_spec(mid, key) or {}).get("default") if v is None else v

    def apex_mm_set(mid, key, v):
        sets = _apex_norm(persistent.apex_mm_settings)
        c = _apex_clean(mid, key, v)
        if c is None:
            return
        if c == apex_mm_spec(mid, key).get("default"):
            sets.get(mid, {}).pop(key, None)
        else:
            sets.setdefault(mid, {})[key] = c
        persistent.apex_mm_settings = dict((m, d) for m, d in sets.items() if d)
        renpy.save_persistent()
        renpy.restart_interaction()

    def apex_mm_step(mid, key, direction):
        s = apex_mm_spec(mid, key)
        if s is None:
            return
        v = apex_mm_get(mid, key)
        if isinstance(s.get("default"), bool):
            apex_mm_set(mid, key, not v)
        else:
            apex_mm_set(mid, key, v + direction * s.get("step", 1))

    def apex_mm_module(mid):
        for m in apex_mm_modules():
            if m["id"] == mid:
                return m
        return {}

    def apex_mm_reset(mid):
        sets = _apex_norm(persistent.apex_mm_settings)
        mine = sets.get(mid, {})
        for s in (apex_mm_module(mid).get("settings") or []):
            mine.pop(s["key"], None)                 # sub-mod switches are left as they are
        persistent.apex_mm_settings = dict((k, d) for k, d in sets.items() if d)
        renpy.save_persistent()
        renpy.restart_interaction()

    def apex_mm_is_default(mid):
        return all(apex_mm_get(mid, s["key"]) == s.get("default") for s in (apex_mm_module(mid).get("settings") or []))

    def apex_mm_fmt(s, v):
        t = s.get("type")
        if t in ("bool", "on/off", "onoff", "yes/no") or isinstance(v, bool):
            return "On" if v else "Off"
        if t in ("one_in", "1 in n"):
            return "1 in %d" % v
        if t == "percent":
            return "%d%%" % v
        if t in ("number", "decimal") and isinstance(v, float):
            return ("%.2f" % v).rstrip("0").rstrip(".")
        if t == "seconds":
            return "%d s" % v
        return "%s%s" % (v, s.get("unit", ""))

    def apex_mm_safe(text):
        # mod texts are plain text: no Ren'Py text tags or [variables]
        return (str(text) if text is not None else "").replace("{", "{{").replace("[", "[[")

    def apex_mm_text(mid, text):
        """a description with {key} replaced by that setting's chosen value"""
        def sub(mo):
            s = apex_mm_spec(mid, mo.group(1))
            return apex_mm_fmt(s, apex_mm_get(mid, mo.group(1))) if s else mo.group(0)
        return apex_mm_safe(_apex_re.sub(r"\{(\w+)\}", sub, text or ""))

    # ================= version check and "Test modpack" =================
    def apex_mm_version():
        return tom_version_info()

    def apex_mm_test_wanted():
        vi = apex_mm_version()
        return vi["newer"] and persistent.apex_mm_test_version == vi["game"]

    def apex_mm_set_test(on):
        persistent.apex_mm_test_version = apex_mm_version()["game"] if on else None
        renpy.save_persistent()
        renpy.restart_interaction()

    apex_mm_seen_warning = [False]          # the "outdated modpack" message is shown once per launch

    # ================= Apex's mods: on / off =================
    def apex_mm_is_on(mid):
        return mid not in apex_mm_off_now()

    def apex_mm_toggle(mid):
        off = apex_mm_off_now()
        if mid in off:
            off.discard(mid)
        else:
            off.add(mid)
        persistent.apex_mm_off = sorted(off)
        renpy.save_persistent()
        renpy.restart_interaction()

    APEX_OK, APEX_WARN, APEX_BAD, APEX_INFO, APEX_DIM = "#3ddc84", "#f5b83d", "#ff5c6c", "#38d6f2", "#7d7590"

    def apex_mm_status(m):
        """(text, colour) for one of Apex's mods"""
        mid = m["id"]
        st = tom_mod_status.get(mid, "")
        want_on = apex_mm_is_on(mid)
        if mid == "hd_sprites" and want_on and st.startswith("on") and not apex_hd_installed():
            return ("HD pictures not installed", APEX_WARN)
        if st.startswith("off: outdated"):
            if want_on and apex_mm_test_wanted():
                return ("On after restart (testing)", APEX_WARN)
            return ("Off: outdated modpack", APEX_INFO)
        if st.startswith("off: needs"):
            return (("Needs " + st[len("off: needs "):]).replace("Needs the ", "Needs ") if want_on else "Off", APEX_WARN if want_on else APEX_DIM)
        if st.startswith("off: game"):
            return ("Paused: game update", APEX_BAD)
        if st.startswith("off: tom_mods_off"):
            return ("Off: tom_mods_off.txt", APEX_BAD)
        if not st:
            return ("Not loaded", APEX_BAD)
        running = st.startswith("on")
        if want_on and not running:
            return ("On after restart", APEX_WARN)
        if running and not want_on:
            return ("Off after restart", APEX_WARN)
        if running and any(apex_mm_get(mid, s["key"]) != apex_mm_boot_value(mid, s["key"])
                           for s in (m.get("settings") or [])):
            return ("New settings after restart", APEX_WARN)
        if running:
            return ("Running", APEX_OK)
        return ("Off", APEX_DIM)

    def apex_mm_sub_status(m, s):
        mid, key = m["id"], s["key"]
        if not apex_mm_is_on(mid):
            return ("Off with its mod", APEX_DIM)
        if apex_mm_get(mid, key) != apex_mm_boot_value(mid, key):
            return ("Changes after restart", APEX_WARN)
        if not tom_mod_status.get(mid, "").startswith("on"):
            return ("", APEX_DIM)
        return ("Running", APEX_OK) if apex_mm_get(mid, key) else ("Off", APEX_DIM)

    APEX_MM_CATEGORIES = ("Characters", "Clothing", "Engine", "UI")
    APEX_MM_CAT_ICON = {"Characters": "heart", "Clothing": "star", "Engine": "wrench", "UI": "overview"}

    def apex_mm_rows():
        """Apex's mods as a tree: ("cat", name, on, total) / ("group", name) / ("mod", module), A to Z at every level"""
        mods = apex_mm_modules()
        cats = sorted(set(m.get("category") or "Other" for m in mods), key=lambda c: (APEX_MM_CATEGORIES + (c,)).index(c))
        rows = []
        for c in cats:
            ms = [m for m in mods if (m.get("category") or "Other") == c]
            rows.append(("cat", c, sum(1 for m in ms if apex_mm_is_on(m["id"])), len(ms)))
            if c in apex_mm_ui.setdefault("closed", []):
                continue
            for m in ms:
                if not m.get("group"):
                    rows.append(("mod", m))
            for g in sorted(set(m["group"] for m in ms if m.get("group")), key=_apex_sort_key):
                rows.append(("group", g))
                rows.extend(("mod", m) for m in ms if m.get("group") == g)
        return rows

    def apex_mm_toggle_cat(c):
        closed = apex_mm_ui.setdefault("closed", [])
        if c in closed:
            closed.remove(c)
        else:
            closed.append(c)
        renpy.restart_interaction()

    def apex_mm_count_on():
        return sum(1 for m in apex_mm_modules() if apex_mm_is_on(m["id"]))

    def apex_mm_date(d):
        try:
            import datetime
            return datetime.date(*[int(x) for x in d.split("-")]).strftime("%d %b %Y").lstrip("0")
        except Exception:
            return d or "?"

    def apex_hd_installed():
        try:
            return renpy.loadable("images/CHAR/celica/celica-530-530-1@2.png")
        except Exception:
            return False

    # ================= Your mods (the mods folder) =================
    def apex_um_list():
        return sorted(APEX_MODS.get("mods", []), key=lambda m: _apex_sort_key(m.get("name") or m.get("id", "")))

    def _apex_um_s():
        return APEX_MODS.setdefault("settings", {"enabled": {}, "values": {}, "auto_off": {}})

    APEX_UM_BOOT = {"enabled": dict((m["id"], m["enabled"]) for m in apex_um_list()),
                    "values": _apex_copy.deepcopy(_apex_um_s().get("values", {}))}

    def apex_um_save():
        f = APEX_MODS.get("save_settings")
        if f:
            f()

    def apex_um_get_info(mid):
        for m in apex_um_list():
            if m["id"] == mid:
                return m
        return None

    def apex_um_is_on(mid):
        return bool(_apex_um_s()["enabled"].get(mid, True))

    def apex_um_toggle(mid):
        s = _apex_um_s()
        on = not apex_um_is_on(mid)
        s["enabled"][mid] = on
        if on:
            s["auto_off"].pop(mid, None)               # switching it back on: forget the old error
        apex_um_save()
        renpy.restart_interaction()

    def apex_um_error(mid):
        """the latest error of this mod (this session, or what switched it off), or None"""
        for e in reversed(APEX_MODS.get("errors", [])):
            if e["mod"] == mid:
                return {"when": e["when"], "where": e["where"], "hint": e["hint"], "report": e["short"], "why": "error"}
        a = _apex_um_s()["auto_off"].get(mid)
        if a:
            rep = a.get("report", "")
            hint = a.get("hint") or (_apex_renpy_explain(rep) if rep else "")
            where = a.get("where") or ""
            if not where:
                w = _apex_re.findall(r'File "(mods/[^"]+)", line (\d+)', rep)
                where = ("%s line %s" % w[-1]) if w else ""
            return {"when": a.get("when", ""), "where": where, "hint": hint, "report": rep[-1800:], "why": a.get("why", "error")}
        return None

    def _apex_renpy_explain(text):
        try:
            import renpy as _r
            return _r.apex_explain(text)
        except Exception:
            return ""

    def apex_um_warnings(mid):
        out = list((apex_um_get_info(mid) or {}).get("warnings", []))
        out += apex_mod_warnings.get(mid, [])
        for rel, a, b in APEX_MODS.get("conflicts", []):
            if mid in (a, b):
                out.append("'%s' is also in mod '%s' - only the first (%s) is used." % (rel, b if mid == a else a, a))
        return out

    def apex_um_status(m):
        mid = m["id"]
        on_now, on_boot = apex_um_is_on(mid), APEX_UM_BOOT["enabled"].get(mid, False)
        err = apex_um_error(mid)
        if err and not on_now:
            return ("Crashed the game - switched off" if err["why"] == "crash" else "Error - switched off", APEX_BAD)
        if on_now and not on_boot:
            return ("On after restart", APEX_WARN)
        if on_boot and not on_now:
            return ("Off after restart", APEX_WARN)
        if on_boot and apex_um_values(mid) != APEX_UM_BOOT["values"].get(mid, {}):
            return ("New settings after restart", APEX_WARN)
        if on_boot:
            return ("Problems found" if apex_um_warnings(mid) else "Running", APEX_WARN if apex_um_warnings(mid) else APEX_OK)
        return ("Off", APEX_DIM)

    def apex_um_values(mid):
        v = _apex_um_s().get("values", {}).get(mid, {})
        return v if isinstance(v, _apex_b.dict) else {}

    def apex_um_spec(mid, key):
        for s in (apex_um_get_info(mid) or {}).get("settings", []):
            if s["key"] == key:
                return s
        return None

    def apex_um_get(mid, key):
        s = apex_um_spec(mid, key)
        if s is None:
            return None
        v = apex_um_values(mid).get(key)
        c = _ak_conv(s, v if v is not None else s["default"])
        return c if c is not None else _ak_conv(s, s["default"])

    def apex_um_step(mid, key, direction):
        s = apex_um_spec(mid, key)
        if s is None:
            return
        v = apex_um_get(mid, key)
        t = s["type"]
        if t in ("on/off", "onoff", "bool", "yes/no"):
            nv = not v
        elif t in ("text",):
            return
        else:
            lo = float(s["min"]) if s.get("min") not in ("", None) else None
            hi = float(s["max"]) if s.get("max") not in ("", None) else None
            stepv = 5 if t == "percent" else (0.1 if t == "decimal" else 1)
            nv = (v or 0) + direction * stepv
            if lo is not None:
                nv = max(lo, nv)
            if hi is not None:
                nv = min(hi, nv)
            nv = round(nv, 3) if t == "decimal" else int(round(nv))
        _apex_um_s()["values"].setdefault(mid, {})[key] = nv
        apex_um_save()
        renpy.restart_interaction()

    def apex_um_reset(mid):
        _apex_um_s()["values"].pop(mid, None)
        apex_um_save()
        renpy.restart_interaction()

    def apex_um_counts():
        lst = apex_um_list()
        running = sum(1 for m in lst if APEX_UM_BOOT["enabled"].get(m["id"]) and not apex_um_error(m["id"]))
        bad = sum(1 for m in lst if apex_um_error(m["id"]))
        return len(lst), running, bad

    def apex_mods_root():
        return APEX_MODS.get("root") or _apex_os.path.join(config.basedir, "mods")

    def apex_open(path):
        try:
            if not _apex_os.path.exists(path):
                _apex_os.makedirs(path)
            _apex_os.startfile(path)
        except Exception as e:
            renpy.notify("Couldn't open %s (%s)" % (path, e))

    def apex_templates():
        out = []
        root = _apex_os.path.join(apex_mods_root(), "_templates")
        if _apex_os.path.isdir(root):
            for d in sorted(_apex_os.listdir(root)):
                p = _apex_os.path.join(root, d, "mod_info.txt")
                if _apex_os.path.exists(p):
                    info = {"id": d, "name": d, "description": ""}
                    for line in _apex_io.open(p, encoding="utf8", errors="replace"):
                        if "=" in line and not line.strip().startswith("#"):
                            k, v = [x.strip() for x in line.split("=", 1)]
                            if k.lower() in ("name", "description"):
                                info[k.lower()] = v
                    out.append(info)
        return out

    def apex_create_mod(template_id):
        name = _apex_re.sub(r"[^A-Za-z0-9 _'\-]+", "", apex_mm_ui.get("new_name") or "").strip()[:40]
        if not template_id:
            renpy.notify("Pick a template first.")
            return
        if not name:
            renpy.notify("Type a name for your mod first.")
            return
        root = apex_mods_root()
        dst = _apex_os.path.join(root, name)
        n = 2
        while _apex_os.path.exists(dst):
            dst = _apex_os.path.join(root, "%s %d" % (name, n))
            n += 1
        try:
            _apex_shutil.copytree(_apex_os.path.join(root, "_templates", template_id), dst)
            p = _apex_os.path.join(dst, "mod_info.txt")
            lines = _apex_io.open(p, encoding="utf8").read().splitlines()
            lines = [("name = %s" % _apex_os.path.basename(dst)) if l.strip().lower().startswith("name") and "=" in l else l
                     for l in lines]
            _apex_io.open(p, "w", encoding="utf8").write("\n".join(lines) + "\n")
            apex_mm_ui["new_name"] = ""
            renpy.notify("Created mods/%s - restart the game to load it." % _apex_os.path.basename(dst))
            apex_open(dst)
        except Exception as e:
            renpy.notify("Couldn't create the mod: %s" % e)

    def _apex_png_size(data):
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            import struct
            return struct.unpack(">II", data[16:24])
        return None

    def apex_check_mods():
        """plain-words health check of every mod in the mods folder"""
        res = []
        try:
            import renpy.loader as L
            arch = {}
            for fn, index in L.archives:
                for k in index:
                    arch[k] = fn
        except Exception:
            arch = {}
        for m in apex_um_list():
            mid, found = m["id"], []
            for w in apex_um_warnings(mid):
                found.append((APEX_WARN, w))
            err = apex_um_error(mid)
            if err:
                found.append((APEX_BAD, "Error%s: %s" % ((" in " + err["where"]) if err["where"] else "", err["hint"])))
            mfg = (m.get("made_for_game") or "").strip()
            if mfg and mfg != config.version:
                found.append((APEX_WARN, "Made for game %s, you have %s." % (mfg, config.version)))
            if not m.get("enabled"):
                found.append((APEX_DIM, "Switched off - its files weren't loaded, so they weren't checked."))
            replaced = added = 0
            for rel in m.get("assets", []):
                if rel.lower().endswith(".png") and rel.startswith("images/"):
                    if rel in arch:
                        replaced += 1
                        try:
                            import renpy.loader as L
                            orig = L.load_from_archive(rel).read(32)
                            mine = _apex_io.open(_apex_os.path.join(m["folder"], rel), "rb").read(32)
                            a, b = _apex_png_size(orig), _apex_png_size(mine)
                            if a and b and a != b:
                                found.append((APEX_WARN, "%s is %dx%d but the game's picture is %dx%d, so it will look shifted or "
                                                         "cut. Keep the same size." % (rel, b[0], b[1], a[0], a[1])))
                        except Exception:
                            pass
                    else:
                        added += 1
            if replaced or added:
                found.append((APEX_INFO, "%d picture(s) replace game pictures, %d are new." % (replaced, added)))
            if not found:
                found.append((APEX_OK, "No problems found."))
            res.append((m.get("name", mid), found))
        if not res:
            res.append(("No mods", [(APEX_DIM, "The mods folder has no mods yet. Create one from a template.")]))
        apex_mm_ui["check"] = res
        renpy.restart_interaction()

    def apex_mm_export():
        part = (apex_mm_ui.get("export") or "").strip()
        if len(part) < 3:
            renpy.notify("Type at least 3 letters of a picture name first.")
            return
        n = apex_export(part)
        renpy.notify("Exported %d picture(s) to mods/_exported." % n)
        if n:
            apex_open(_apex_os.path.join(apex_mods_root(), "_exported"))

    # ================= HD project progress (written by the build) =================
    def apex_hd_progress():
        return (APEX_BUILD or {}).get("hd_progress") or {}

    # ================= pending changes / restart =================
    def apex_mm_pending():
        if apex_mm_off_now() != set(APEX_MM_BOOT_OFF):
            return True
        if _apex_norm(persistent.apex_mm_settings) != APEX_MM_BOOT_SETTINGS:
            return True
        for m in apex_um_list():
            auto = _apex_um_s()["auto_off"].get(m["id"])
            if apex_um_is_on(m["id"]) != APEX_UM_BOOT["enabled"].get(m["id"], False) and not (auto and not apex_um_is_on(m["id"])):
                return True
            if APEX_UM_BOOT["enabled"].get(m["id"]) and apex_um_values(m["id"]) != APEX_UM_BOOT["values"].get(m["id"], {}):
                return True
        vi = apex_mm_version()
        return vi["newer"] and apex_mm_test_wanted() != vi["approved"]

    def apex_mm_attention():
        """(colour, icon, text) items for the Overview page"""
        out = []
        vi = apex_mm_version()
        if apex_mm_pending():
            out.append((APEX_WARN, "restart", "You changed mods or settings. Restart to apply them."))
        if vi["newer"] and not apex_mm_test_wanted():
            out.append((APEX_INFO, "warn", "Your game (%s) is newer than this modpack (%s): Apex's mods are off. "
                                           "Switch on Test modpack below to try them." % (vi["game"], vi["made_for"])))
        for m in apex_um_list():
            e = apex_um_error(m["id"])
            if e:
                out.append((APEX_BAD, "warn", "Your mod '%s' %s and was switched off. Open Your Mods for details."
                            % (m.get("name", m["id"]), "crashed the game" if e["why"] == "crash" else "had an error")))
        for mid, st in sorted(tom_mod_status.items()):
            if st.startswith("off: game"):
                out.append((APEX_BAD, "warn", "%s paused itself: a game update changed what it uses."
                            % apex_mm_module(mid).get("title", mid)))
        if apex_mm_is_on("hd_sprites") and not apex_hd_installed():
            out.append((APEX_WARN, "sparkle", "HD x8 is on, but the HD pictures aren't installed (download the HD pack)."))
        return out

    def apex_mm_restart():
        renpy.quit(relaunch=True)

    # quitting with changes that aren't applied yet -> offer to restart instead
    _apex_orig_quit = _apex_exports.quit
    _apex_asking = [False]

    def _apex_quit(relaunch=False, status=0, save=False):
        if not relaunch and not _apex_asking[0]:
            try:
                if apex_mm_pending():
                    _apex_asking[0] = True
                    try:
                        relaunch = bool(renpy.invoke_in_new_context(renpy.call_screen, "apex_mm_restart_prompt",
                                                                    quitting=True))
                    finally:
                        _apex_asking[0] = False
            except Exception:
                pass
        return _apex_orig_quit(relaunch=relaunch, status=status, save=save)

    if APEX_BUILD is not None and getattr(_apex_exports.quit, "__name__", "") != "_apex_quit":
        _apex_exports.quit = _apex_quit

    if APEX_BUILD is not None and "apex_mm_menu_button" not in config.always_shown_screens:
        config.always_shown_screens.append("apex_mm_menu_button")

    # ================= look: tinted, rounded pieces from apex_modpack/ui =================
    _apex_ui_cache = {}

    def apex_ui(kind, color="#ffffff", alpha=1.0):
        """kind: panel / ring / pill / bar (9-slice frames)  or an icon name (ic_*) / knob / dot / glow"""
        key = (kind, color, alpha)
        d = _apex_ui_cache.get(key)
        if d is None:
            img = "apex_modpack/ui/%s.png" % kind
            m = TintMatrix(color) * OpacityMatrix(alpha) if alpha < 1 else TintMatrix(color)
            t = Transform(img, matrixcolor=m)
            if kind in ("panel", "panel_ring"):
                d = Frame(t, 12, 12)
            elif kind in ("pill",):
                d = Frame(t, 12, 12)
            elif kind == "bar":
                d = Frame(t, 6, 6)
            elif kind == "thin":
                d = Frame(t, 4, 4)
            else:
                d = t
            _apex_ui_cache[key] = d
        return d

    APEX_C = dict(bg="#0b0910", side="#110d17", panel="#19141f", panel2="#211a2a", line="#2c2438", text="#ece8f3",
                  muted="#9b93aa", dim="#6d6580", gold="#ffc94d", purple="#9b6bff")


# ================================================================ styles
style apex_mm_text is default:
    font gui.text_font
    size 13
    color "#ece8f3"
    outlines []

style apex_mm_vscrollbar:
    xsize 5
    base_bar Solid("#00000000")
    thumb Frame(Transform("apex_modpack/ui/bar.png", matrixcolor=TintMatrix("#5b4a7a")), 2, 2)
    hover_thumb Frame(Transform("apex_modpack/ui/bar.png", matrixcolor=TintMatrix("#9b6bff")), 2, 2)
    unscrollable "hide"

style apex_mm_button is default
style apex_mm_button_text is apex_mm_text
style apex_mm_frame is default
style apex_mm_viewport is default
style apex_mm_input is apex_mm_text

transform apex_fade:
    alpha 0.0
    linear 0.18 alpha 1.0

transform apex_rise:
    alpha 0.0 yoffset 8
    easein 0.22 alpha 1.0 yoffset 0


# ================================================================ main menu button
screen apex_mm_menu_button():
    zorder 50
    if main_menu and renpy.get_screen("main_menu") and not renpy.get_screen("apex_modpack_manager"):
        $ vi = apex_mm_version()
        $ total, running, bad = apex_um_counts()
        vbox:
            xpos gui.navigation_xpos
            ypos 104
            spacing 2
            button:
                padding (4, 2)
                background None
                hover_background Solid("#9933ff33")
                action ShowMenu("apex_modpack_manager")
                vbox:
                    text "Apex's Modpack" size 20 color "#ffd24d" hover_color "#ffffff"
                    text "Manager" size 20 color "#ffd24d" hover_color "#ffffff"
            if vi["locked"] and not apex_mm_test_wanted():
                text "Outdated: Apex's mods off" size 11 color "#4de1ff" xpos 4
            else:
                text ("%d of %d mods on" % (apex_mm_count_on(), len(apex_mm_modules())) + (" + %d of yours" % running if total else "")) size 11 color "#9a9a9a" xpos 4
            if bad:
                text ("%d of your mods had an error" % bad) size 11 color "#ff6b6b" xpos 4
            if apex_mm_pending():
                text "Restart to apply changes" size 11 color "#ffd24d" xpos 4
            add Solid("#9933ff") xsize 170 ysize 1 ypos 12 xpos 4

        if vi["locked"] and not apex_mm_seen_warning[0]:
            use apex_mm_outdated_warning


# ================================================================ small building blocks
screen apex_chip(label, color):
    frame:
        padding (9, 2)
        background apex_ui("pill", color, 0.16)
        hbox:
            spacing 5
            add apex_ui("dot", color) yalign 0.5 zoom 0.6
            text label size 11 color color bold True yalign 0.5

screen apex_switch(on, action, enabled=True):
    button:
        xsize 42 ysize 22 padding (0, 0)
        background None
        action action
        fixed:
            xsize 42 ysize 22
            add apex_ui("pill", (APEX_OK if on else "#4a4258") if enabled else "#2c2636") xsize 42 ysize 22
            add apex_ui("knob", "#ffffff" if enabled else "#77708a") xpos (22 if on else 2) ypos 2

screen apex_btn(label, action, icon=None, kind="secondary", w=None):
    $ bgc = {"primary": APEX_C["gold"], "secondary": "#2a2236", "danger": "#ff5c6c", "ghost": "#000000"}[kind]
    $ fgc = "#16111c" if kind == "primary" else "#ffffff"
    button:
        padding (14, 7)
        if w:
            xsize w
        background apex_ui("panel", bgc, 1.0 if kind != "ghost" else 0.0)
        hover_background apex_ui("panel", "#ffd97a" if kind == "primary" else "#3a2f4c")
        action action
        hbox:
            spacing 7
            xalign 0.5
            if icon:
                add apex_ui("ic_" + icon, fgc) yalign 0.5 zoom 0.8
            text label size 13 bold True color fgc yalign 0.5 layout "nobreak"

screen apex_page_head(title, subtitle):
    vbox:
        spacing 3
        text title size 26 bold True color APEX_C["text"]
        text subtitle size 13 color APEX_C["muted"]


# ================================================================ the manager
screen apex_modpack_manager():
    tag menu
    modal True
    style_prefix "apex_mm"
    $ page = apex_mm_ui["page"]
    $ vi = apex_mm_version()
    $ total, running, bad = apex_um_counts()

    add gui.main_menu_background at Transform(blur=18)
    add Solid("#0b0910ea")

    # ---------------- sidebar
    fixed:
        xsize 214 ysize 600
        add Solid(APEX_C["side"])
        add Solid(APEX_C["line"]) xpos 213 xsize 1 ysize 600
        vbox:
            xpos 18 ypos 20 xsize 180
            hbox:
                spacing 10
                fixed:
                    xsize 38 ysize 38
                    add apex_ui("glow", APEX_C["purple"], 0.55) zoom 1.1 xalign 0.5 yalign 0.5
                    add apex_ui("knob", APEX_C["gold"]) zoom 1.9 xalign 0.5 yalign 0.5
                    text "A" size 22 bold True color "#16111c" xalign 0.5 yalign 0.48
                vbox:
                    yalign 0.5
                    text "APEX'S MODPACK" size 14 bold True color APEX_C["gold"]
                    text "MOD MANAGER" size 10 color APEX_C["muted"] kerning 2
            null height 22
            for pid, label, ic, badge, bcol in (
                    ("overview", "Overview", "overview", None, None),
                    ("apex", "Apex's Mods", "star", "%d/%d" % (apex_mm_count_on(), len(apex_mm_modules())), APEX_C["muted"]),
                    ("yours", "Your Mods", "puzzle", (str(bad) if bad else (str(total) if total else None)), APEX_BAD if bad else APEX_C["muted"]),
                    ("hd", "HD Project", "sparkle", ("%d%%" % apex_hd_progress().get("overall_pct", 0)) if apex_hd_progress() else None, APEX_C["muted"]),
                    ("tools", "Mod Tools", "wrench", None, None),
                    ("about", "About & Support", "heart", None, None)):
                $ act = (page == pid)
                button:
                    xsize 180 ysize 38 padding (12, 0)
                    background (apex_ui("panel", APEX_C["purple"], 0.20) if act else None)
                    hover_background apex_ui("panel", "#ffffff", 0.06)
                    action SetDict(apex_mm_ui, "page", pid)
                    fixed:
                        xsize 156 ysize 38
                        if act:
                            add apex_ui("bar", APEX_C["gold"]) xpos -12 ysize 22 xsize 3 yalign 0.5
                        hbox:
                            spacing 10 yalign 0.5
                            add apex_ui("ic_" + ic, APEX_C["gold"] if act else APEX_C["muted"]) yalign 0.5 zoom 0.85
                            text label size 13 bold act color (APEX_C["text"] if act else "#c4bccf") yalign 0.5 layout "nobreak"
                        if badge:
                            frame:
                                xalign 1.0 yalign 0.5 padding (5, 1)
                                background apex_ui("pill", bcol, 0.18)
                                text badge size 9 bold True color bcol
        vbox:
            xpos 18 yalign 1.0 yoffset -18 xsize 180 spacing 10
            frame:
                xfill True padding (12, 10)
                background apex_ui("panel", APEX_C["panel"])
                vbox:
                    spacing 2
                    text "GAME VERSION" size 9 color APEX_C["dim"] kerning 1.5
                    hbox:
                        spacing 6
                        add apex_ui("dot", {"match": APEX_OK, "minor": APEX_WARN}.get(vi["level"], APEX_BAD)) yalign 0.5 zoom 0.8
                        text vi["game"] size 14 bold True color APEX_C["text"]
                    text ("Made for %s" % vi["made_for"]) size 10 color APEX_C["muted"]
            if apex_mm_pending():
                use apex_btn("Restart now", Function(apex_mm_restart), "restart", "primary", 180)
            use apex_btn("Back", If(apex_mm_pending(), Show("apex_mm_restart_prompt", quitting=False), Return()), "back", "secondary", 180)

    # ---------------- page
    frame:
        xpos 214 xsize 852 ysize 600 padding (30, 24, 22, 18)
        background None
        if page == "overview":
            use apex_mm_p_overview
        elif page == "apex":
            use apex_mm_p_apex
        elif page == "yours":
            use apex_mm_p_yours
        elif page == "hd":
            use apex_mm_p_hd
        elif page == "tools":
            use apex_mm_p_tools
        else:
            use apex_mm_p_about

    key "game_menu" action If(apex_mm_pending(), Show("apex_mm_restart_prompt", quitting=False), Return())


# ---------------------------------------------------------------- page: overview
screen apex_mm_p_overview():
    $ vi = apex_mm_version()
    $ total, running, bad = apex_um_counts()
    $ hp = apex_hd_progress()
    $ att = apex_mm_attention()
    vbox:
        spacing 16
        at apex_rise
        use apex_page_head("Overview", "Everything in one place: switch mods on or off, change their settings, add your own.")
        hbox:
            spacing 12
            for title, big, small, col, ic, go in (
                    ("APEX'S MODS", "%d / %d" % (apex_mm_count_on(), len(apex_mm_modules())), "switched on", APEX_C["gold"], "star", "apex"),
                    ("YOUR MODS", "%d" % total if total else "None yet", ("%d running" % running) + (", %d error" % bad if bad else "") if total else "add your own", APEX_BAD if bad else APEX_C["purple"], "puzzle", "yours"),
                    ("GAME", vi["game"], {"match": "Compatible", "minor": "Version mismatch"}.get(vi["level"], "Different version"), {"match": APEX_OK, "minor": APEX_WARN}.get(vi["level"], APEX_BAD), "info", "about"),
                    ("HD PROJECT", ("%d%%" % hp.get("overall_pct", 0)) if hp else "-", "of the game upscaled" if hp else "no data", APEX_INFO, "sparkle", "hd")):
                button:
                    xsize 188 ysize 104 padding (16, 14)
                    background apex_ui("panel", APEX_C["panel"])
                    hover_background apex_ui("panel", APEX_C["panel2"])
                    action SetDict(apex_mm_ui, "page", go)
                    fixed:
                      xsize 156 ysize 76
                      add apex_ui("glow", col, 0.22) xalign 1.0 yalign 0.0 xoffset 30 yoffset -30 zoom 1.6
                      vbox:
                        spacing 4
                        hbox:
                            spacing 6
                            add apex_ui("ic_" + ic, col) zoom 0.7 yalign 0.5
                            text title size 10 bold True color APEX_C["muted"] kerning 1.5 yalign 0.5
                        text big size 26 bold True color APEX_C["text"]
                        text small size 11 color col
        frame:
            xfill True padding (18, 14)
            background apex_ui("panel", APEX_C["panel"])
            vbox:
                spacing 10
                text "NEEDS YOUR ATTENTION" size 10 bold True color APEX_C["muted"] kerning 1.5
                if not att:
                    hbox:
                        spacing 8
                        add apex_ui("ic_check", APEX_OK) zoom 0.8 yalign 0.5
                        text "All good - nothing needs your attention." size 13 color APEX_C["text"] yalign 0.5
                for col, ic, msg in att:
                    hbox:
                        spacing 9
                        add apex_ui("ic_" + ic, col) zoom 0.75 yalign 0.0 yoffset 1
                        text apex_mm_safe(msg) size 13 color APEX_C["text"] xsize 700
                if vi["newer"]:
                    hbox:
                        spacing 10
                        text "Test modpack on this game version?" size 13 color APEX_INFO yalign 0.5
                        use apex_switch(apex_mm_test_wanted(), Function(apex_mm_set_test, not apex_mm_test_wanted()))
        hbox:
            spacing 10
            use apex_btn("Open mods folder", Function(apex_open, apex_mods_root()), "folder")
            use apex_btn("Create a mod", SetDict(apex_mm_ui, "page", "tools"), "plus")
            use apex_btn("Modding guide", Function(apex_open, _apex_os.path.join(apex_mods_root(), "_guide", "Modding Guide.html")), "book")
            if apex_mm_pending():
                use apex_btn("Restart now", Function(apex_mm_restart), "restart", "primary")


# ---------------------------------------------------------------- page: Apex's mods
screen apex_mm_p_apex():
    $ vi = apex_mm_version()
    vbox:
        spacing 14
        at apex_rise
        use apex_page_head("Apex's Mods", "The mods that come with the pack. The gear changes a mod's settings. Changes apply after a restart.")
        if vi["newer"] and not apex_mm_test_wanted():
            frame:
                xfill True padding (14, 10)
                background apex_ui("panel", APEX_INFO, 0.12)
                text "Your game is newer than this modpack, so these mods are off. Overview -> Test modpack to try them anyway." size 12 color APEX_INFO
        viewport:
            xsize 800 ysize 470
            mousewheel True draggable True scrollbars "vertical" spacing 6
            vbox:
                spacing 8
                for r in apex_mm_rows():
                    if r[0] == "cat":
                        $ _closed = r[1] in apex_mm_ui.get("closed", [])
                        button:
                            xsize 788 padding (14, 8)
                            background apex_ui("panel", APEX_C["purple"], 0.22)
                            hover_background apex_ui("panel", APEX_C["purple"], 0.4)
                            action Function(apex_mm_toggle_cat, r[1])
                            hbox:
                                spacing 10
                                text ("▸" if _closed else "▾") size 16 color APEX_C["gold"] yalign 0.5
                                text r[1].upper() size 16 bold True color APEX_C["gold"] yalign 0.5
                                text "%d of %d on" % (r[2], r[3]) size 11 color APEX_C["muted"] yalign 0.5
                    elif r[0] == "group":
                        hbox:
                            spacing 8
                            null width 14
                            text "› " + apex_mm_safe(r[1]) size 14 bold True color APEX_C["purple"]
                    else:
                        use apex_mm_mod_row(r[1])


screen apex_mm_mod_row(m):
        $ on = apex_mm_is_on(m["id"])
        $ st, stc = apex_mm_status(m)
        frame:
            xsize 788 padding (16, 12)
            background apex_ui("panel", APEX_C["panel"])
            hbox:
                spacing 14
                use apex_switch(on, Function(apex_mm_toggle, m["id"]))
                vbox:
                    xsize 470 spacing 3
                    hbox:
                        spacing 8
                        text apex_mm_safe(m["title"]) size 15 bold True color (APEX_C["text"] if on else APEX_C["muted"])
                        text ("r" + m["rev"]) size 11 color APEX_C["purple"] yalign 1.0
                        if m.get("wip"):
                            frame:
                                padding (7, 1) yalign 0.5
                                background apex_ui("pill", "#ff9a3c", 0.18)
                                text apex_mm_safe(m["wip"]) size 9 bold True color "#ff9a3c"
                    text apex_mm_text(m["id"], m["desc"]) size 12 color APEX_C["muted"]
                frame:
                    xsize 200 yalign 0.5 padding (0, 0) background None
                    hbox:
                        xalign 1.0 spacing 8
                        use apex_chip(st, stc)
                        if m.get("settings"):
                            button:
                                padding (5, 5) yalign 0.5
                                background apex_ui("panel", "#2a2236")
                                hover_background apex_ui("panel", APEX_C["purple"], 0.5)
                                action Show("apex_mm_settings", mid=m["id"], user=False)
                                add "apex_modpack/gear.png" zoom 0.8
        $ subs = m.get("subs") or []
        for i, s in enumerate(subs):
            $ son = bool(apex_mm_get(m["id"], s["key"]))
            $ sst, sstc = apex_mm_sub_status(m, s)
            frame:
                xsize 788 padding (16, 8)
                background apex_ui("panel", APEX_C["panel"], 0.55)
                hbox:
                    spacing 12
                    null width 10
                    text ("└" if i == len(subs) - 1 else "├") size 18 color APEX_C["dim"] yalign 0.5
                    use apex_switch(son, Function(apex_mm_step, m["id"], s["key"], 1), on)
                    vbox:
                        xsize 420 spacing 1
                        text apex_mm_safe(s["title"]) size 13 bold True color (APEX_C["text"] if (on and son) else APEX_C["muted"])
                        text apex_mm_text(m["id"], s.get("desc", "")) size 11 color APEX_C["muted"]
                    frame:
                        xsize 200 yalign 0.5 padding (0, 0) background None
                        if sst:
                            frame:
                                xalign 1.0 padding (0, 0) background None
                                use apex_chip(sst, sstc)


# ---------------------------------------------------------------- page: your mods
screen apex_mm_p_yours():
    $ lst = apex_um_list()
    vbox:
        spacing 14
        at apex_rise
        fixed:
            xsize 800 ysize 54
            use apex_page_head("Your Mods", "Mods from the  mods  folder. New mods start ON after a restart.")
            hbox:
                xalign 1.0 yalign 0.2 spacing 8
                use apex_btn("Open folder", Function(apex_open, apex_mods_root()), "folder")
                use apex_btn("Create a mod", SetDict(apex_mm_ui, "page", "tools"), "plus", "primary")
        if not lst:
            frame:
                xsize 800 padding (30, 34)
                background apex_ui("panel", APEX_C["panel"])
                vbox:
                    xalign 0.5 spacing 10
                    add apex_ui("ic_puzzle", APEX_C["purple"]) zoom 2.2 xalign 0.5
                    text "No mods yet" size 20 bold True color APEX_C["text"] xalign 0.5
                    text "Put a mod's folder into the  mods  folder, or make your own from a template in Mod Tools." size 13 color APEX_C["muted"] xalign 0.5 text_align 0.5
                    hbox:
                        xalign 0.5 spacing 10
                        use apex_btn("Open mods folder", Function(apex_open, apex_mods_root()), "folder")
                        use apex_btn("Modding guide", Function(apex_open, _apex_os.path.join(apex_mods_root(), "_guide", "Modding Guide.html")), "book")
        else:
            viewport:
                xsize 800 ysize 470
                mousewheel True draggable True scrollbars "vertical" spacing 6
                vbox:
                    spacing 8
                    for m in lst:
                        $ on = apex_um_is_on(m["id"])
                        $ st, stc = apex_um_status(m)
                        frame:
                            xsize 788 padding (16, 12)
                            background apex_ui("panel", APEX_C["panel"])
                            hbox:
                                spacing 14
                                use apex_switch(on, Function(apex_um_toggle, m["id"]))
                                vbox:
                                    xsize 470 spacing 3
                                    hbox:
                                        spacing 8
                                        text apex_mm_safe(m.get("name") or m["id"]) size 15 bold True color (APEX_C["text"] if on else APEX_C["muted"])
                                        if m.get("version"):
                                            text ("v" + apex_mm_safe(m["version"])) size 11 color APEX_C["purple"] yalign 1.0
                                        if m.get("author"):
                                            text ("by " + apex_mm_safe(m["author"])) size 11 color APEX_C["dim"] yalign 1.0
                                    text apex_mm_safe(m.get("description") or "No description in mod_info.txt.") size 12 color APEX_C["muted"]
                                frame:
                                    xsize 200 yalign 0.5 padding (0, 0) background None
                                    hbox:
                                        xalign 1.0 spacing 8
                                        use apex_chip(st, stc)
                                        if m.get("settings"):
                                            button:
                                                padding (5, 5) yalign 0.5
                                                background apex_ui("panel", "#2a2236")
                                                hover_background apex_ui("panel", APEX_C["purple"], 0.5)
                                                action Show("apex_mm_settings", mid=m["id"], user=True)
                                                add "apex_modpack/gear.png" zoom 0.8
                                        button:
                                            padding (6, 6) yalign 0.5
                                            background apex_ui("panel", "#2a2236")
                                            hover_background apex_ui("panel", APEX_C["purple"], 0.5)
                                            action Show("apex_mm_um_details", mid=m["id"])
                                            add apex_ui("ic_info", "#ffffff") zoom 0.7


# ---------------------------------------------------------------- details of one of your mods
screen apex_mm_um_details(mid):
    modal True
    zorder 200
    style_prefix "apex_mm"
    $ m = apex_um_get_info(mid) or {}
    $ err = apex_um_error(mid)
    $ warns = apex_um_warnings(mid)
    add Solid("#000000b8")
    frame:
        xalign 0.5 yalign 0.5 xsize 760 padding (26, 22)
        background apex_ui("panel", APEX_C["panel2"])
        at apex_rise
        vbox:
            spacing 12
            hbox:
                xfill True
                vbox:
                    text apex_mm_safe(m.get("name") or mid) size 22 bold True color APEX_C["text"]
                    text apex_mm_safe(" · ".join(x for x in ("v" + m["version"] if m.get("version") else "", "by " + m["author"] if m.get("author") else "", "folder: mods/" + mid) if x)) size 12 color APEX_C["muted"]
                button:
                    xalign 1.0 padding (6, 6)
                    background apex_ui("panel", "#2a2236")
                    hover_background apex_ui("panel", APEX_BAD, 0.6)
                    action Hide("apex_mm_um_details")
                    add apex_ui("ic_close", "#ffffff") zoom 0.7
            viewport:
                xsize 708 ysize 330
                mousewheel True scrollbars "vertical" spacing 4
                vbox:
                    spacing 10
                    text apex_mm_safe(m.get("description") or "No description.") size 13 color APEX_C["text"]
                    if err:
                        frame:
                            xsize 696 padding (14, 12)
                            background apex_ui("panel", APEX_BAD, 0.14)
                            vbox:
                                spacing 6
                                text ("This mod crashed the game while it started, so it was switched off." if err["why"] == "crash" else "This mod had an error, so it was switched off.") size 13 bold True color APEX_BAD
                                if err["where"]:
                                    text ("Where:  " + apex_mm_safe(err["where"])) size 12 color APEX_C["text"]
                                text ("What to do:  " + apex_mm_safe(err["hint"])) size 12 color APEX_C["text"]
                                text "Technical details (last lines matter most):" size 11 color APEX_C["muted"]
                                text apex_mm_safe(err["report"][-900:]) size 10 color "#c9b8c0"
                    if warns:
                        frame:
                            xsize 696 padding (14, 12)
                            background apex_ui("panel", APEX_WARN, 0.12)
                            vbox:
                                spacing 4
                                text "Problems found" size 13 bold True color APEX_WARN
                                for w in warns:
                                    text ("•  " + apex_mm_safe(w)) size 12 color APEX_C["text"]
                    text "FILES" size 10 bold True color APEX_C["muted"] kerning 1.5
                    text ("%d script(s), %d other file(s) (pictures, sounds)" % (len(m.get("scripts", [])), len(m.get("assets", [])))) size 12 color APEX_C["text"]
                    for f in (m.get("scripts", []) + m.get("assets", []))[:40]:
                        text ("   " + apex_mm_safe(f)) size 11 color APEX_C["muted"]
            hbox:
                spacing 10
                use apex_btn("Open folder", Function(apex_open, m.get("folder", apex_mods_root())), "folder")
                if err and _apex_os.path.exists(_apex_os.path.join(m.get("folder", ""), "ERROR REPORT.txt")):
                    use apex_btn("Open error report", Function(apex_open, _apex_os.path.join(m.get("folder", ""), "ERROR REPORT.txt")), "doc")
                if err and not apex_um_is_on(mid):
                    use apex_btn("Switch back on", Function(apex_um_toggle, mid), "restart", "primary")
    key "game_menu" action Hide("apex_mm_um_details")


# ---------------------------------------------------------------- page: HD project
screen apex_mm_p_hd():
    $ hp = apex_hd_progress()
    vbox:
        spacing 14
        at apex_rise
        use apex_page_head("HD Project", "AI-upscaled HD pictures for big windows. Very early work in progress - more with every release.")
        if not hp:
            text "No progress data in this build." size 13 color APEX_C["muted"]
        else:
            frame:
                xsize 800 padding (20, 16)
                background apex_ui("panel", APEX_C["panel"])
                vbox:
                    spacing 8
                    hbox:
                        xfill True
                        text "WHOLE GAME" size 10 bold True color APEX_C["muted"] kerning 1.5
                        text ("%s of %s pictures" % (format(hp["done"], ","), format(hp["total"], ","))) size 12 color APEX_C["muted"] xalign 1.0
                    hbox:
                        spacing 14
                        text ("%d%%" % hp.get("overall_pct", 0)) size 30 bold True color APEX_INFO yalign 0.5
                        fixed:
                            xsize 680 ysize 14 yalign 0.5
                            add apex_ui("bar", "#2a2236") xsize 680 ysize 14
                            add apex_ui("bar", APEX_INFO) xsize max(14, int(680 * hp["done"] / max(1, hp["total"]))) ysize 14
                    hbox:
                        spacing 8
                        use apex_chip("HD pictures installed" if apex_hd_installed() else "HD pictures not installed", APEX_OK if apex_hd_installed() else APEX_WARN)
                        use apex_chip("HD x8 mod " + ("on" if apex_mm_is_on("hd_sprites") else "off"), APEX_OK if apex_mm_is_on("hd_sprites") else APEX_DIM)
            viewport:
                xsize 800 ysize 330
                mousewheel True scrollbars "vertical" spacing 6
                vbox:
                    spacing 6
                    for cat in hp.get("categories", []):
                        frame:
                            xsize 788 padding (16, 10)
                            background apex_ui("panel", APEX_C["panel"])
                            vbox:
                                spacing 6
                                hbox:
                                    xfill True
                                    text apex_mm_safe(cat["name"]) size 14 bold True color APEX_C["text"]
                                    text ("%s / %s  (%d%%)" % (format(cat["done"], ","), format(cat["total"], ","), cat["pct"])) size 12 color APEX_C["muted"] xalign 1.0
                                fixed:
                                    xsize 756 ysize 8
                                    add apex_ui("thin", "#2a2236") xsize 756 ysize 8
                                    if cat["done"]:
                                        add apex_ui("thin", APEX_C["gold"]) xsize max(8, int(756 * cat["done"] / max(1, cat["total"]))) ysize 8
                                for row in cat.get("rows", [])[:14]:
                                    hbox:
                                        spacing 10
                                        text apex_mm_safe(row["name"]) size 12 color APEX_C["text"] xsize 200
                                        fixed:
                                            xsize 420 ysize 6 yalign 0.5
                                            add apex_ui("thin", "#2a2236") xsize 420 ysize 6
                                            if row["done"]:
                                                add apex_ui("thin", APEX_C["purple"]) xsize max(8, int(420 * row["done"] / max(1, row["total"]))) ysize 6
                                        text ("%d / %d" % (row["done"], row["total"])) size 11 color APEX_C["muted"]


# ---------------------------------------------------------------- page: mod tools
screen apex_mm_p_tools():
    $ tpl = apex_templates()
    vbox:
        spacing 14
        at apex_rise
        use apex_page_head("Mod Tools", "Make your own mod in minutes, check your mods for problems, and find help.")
        viewport:
            xsize 800 ysize 490
            mousewheel True scrollbars "vertical" spacing 6
            vbox:
                spacing 10
                frame:
                    xsize 788 padding (18, 14)
                    background apex_ui("panel", APEX_C["panel"])
                    vbox:
                        spacing 10
                        hbox:
                            spacing 8
                            add apex_ui("ic_plus", APEX_C["gold"]) zoom 0.85 yalign 0.5
                            text "Create a new mod" size 15 bold True color APEX_C["text"] yalign 0.5
                        text "1. Type a name.   2. Pick what kind of mod.   3. Create - its folder opens, ready to edit. Restart the game to load it." size 12 color APEX_C["muted"]
                        hbox:
                            spacing 10
                            text "Name:" size 13 color APEX_C["text"] yalign 0.5
                            button:
                                xsize 360 padding (10, 6)
                                background apex_ui("panel", "#0f0c14")
                                hover_background apex_ui("panel", "#1c1626")
                                action apex_in_name.Toggle()
                                input value apex_in_name length 40 size 13 color APEX_C["text"] allow "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 _'-"
                        for t in tpl:
                            $ sel = (apex_mm_ui.get("template") == t["id"])
                            button:
                                xsize 752 padding (12, 8)
                                background apex_ui("panel", APEX_C["purple"] if sel else "#241d30", 0.35 if sel else 1.0)
                                hover_background apex_ui("panel", APEX_C["purple"], 0.25)
                                action SetDict(apex_mm_ui, "template", t["id"])
                                hbox:
                                    spacing 10
                                    add apex_ui("dot", APEX_C["gold"] if sel else APEX_C["dim"]) yalign 0.5
                                    vbox:
                                        text apex_mm_safe(t["name"]) size 13 bold True color APEX_C["text"]
                                        text apex_mm_safe(t["description"]) size 11 color APEX_C["muted"]
                        if not tpl:
                            text "No templates found (mods/_templates is missing - reinstall the pack)." size 12 color APEX_WARN
                        use apex_btn("Create mod", Function(apex_create_mod, apex_mm_ui.get("template")), "plus", "primary")
                frame:
                    xsize 788 padding (18, 14)
                    background apex_ui("panel", APEX_C["panel"])
                    vbox:
                        spacing 10
                        hbox:
                            spacing 8
                            add apex_ui("ic_search", APEX_INFO) zoom 0.85 yalign 0.5
                            text "Check my mods" size 15 bold True color APEX_C["text"] yalign 0.5
                        text "Looks for missing files, wrongly sized pictures, version mismatches, clashes between mods and errors." size 12 color APEX_C["muted"]
                        use apex_btn("Run check", Function(apex_check_mods), "search")
                        if apex_mm_ui.get("check"):
                            for name, found in apex_mm_ui["check"]:
                                text apex_mm_safe(name) size 13 bold True color APEX_C["text"]
                                for col, msg in found:
                                    hbox:
                                        spacing 8
                                        add apex_ui("dot", col) yalign 0.0 yoffset 4
                                        text apex_mm_safe(msg) size 12 color APEX_C["text"] xsize 700
                frame:
                    xsize 788 padding (18, 14)
                    background apex_ui("panel", APEX_C["panel"])
                    vbox:
                        spacing 10
                        hbox:
                            spacing 8
                            add apex_ui("ic_folder", APEX_C["gold"]) zoom 0.85 yalign 0.5
                            text "Export game pictures" size 15 bold True color APEX_C["text"] yalign 0.5
                        text "Copies every game picture whose name contains the text below to  mods/_exported  - edit a copy, then put it in your mod (same folders, same name, same size) to replace the original." size 12 color APEX_C["muted"]
                        hbox:
                            spacing 10
                            button:
                                xsize 360 padding (10, 6)
                                background apex_ui("panel", "#0f0c14")
                                hover_background apex_ui("panel", "#1c1626")
                                action apex_in_export.Toggle()
                                input value apex_in_export length 60 size 13 color APEX_C["text"] allow "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                            use apex_btn("Celica's tops", SetDict(apex_mm_ui, "export", "celica_top_normal"))
                            use apex_btn("Export", Function(apex_mm_export), "folder", "primary")
                frame:
                    xsize 788 padding (18, 14)
                    background apex_ui("panel", APEX_C["panel"])
                    vbox:
                        spacing 10
                        hbox:
                            spacing 8
                            add apex_ui("ic_book", APEX_C["purple"]) zoom 0.85 yalign 0.5
                            text "Help" size 15 bold True color APEX_C["text"] yalign 0.5
                        hbox:
                            spacing 10
                            use apex_btn("Modding guide", Function(apex_open, _apex_os.path.join(apex_mods_root(), "_guide", "Modding Guide.html")), "book")
                            use apex_btn("Open mods folder", Function(apex_open, apex_mods_root()), "folder")
                            use apex_btn("Loader log", Function(apex_open, _apex_os.path.join(apex_mods_root(), "_manager", "loader_log.txt")), "doc")


# ---------------------------------------------------------------- page: about & support
screen apex_mm_p_about():
    $ b = APEX_BUILD or {}
    $ vi = apex_mm_version()
    $ lvl_col = {"match": APEX_OK, "minor": APEX_WARN}.get(vi["level"], APEX_BAD)
    vbox:
        spacing 14
        at apex_rise
        use apex_page_head("About & Support", "Versions, compatibility, and how to support the project.")
        hbox:
            spacing 12
            frame:
                xsize 394 ysize 236 padding (18, 14)
                background apex_ui("panel", APEX_C["panel"])
                vbox:
                    spacing 5
                    text "MODPACK" size 10 bold True color APEX_C["muted"] kerning 1.5
                    text ("Version " + b.get("version", "?")) size 20 bold True color (APEX_INFO if vi["newer"] else APEX_C["text"])
                    text ("Last updated " + apex_mm_date(b.get("date"))) size 12 color APEX_C["muted"]
                    null height 4
                    text "GAME" size 10 bold True color APEX_C["muted"] kerning 1.5
                    text ("Your game  " + vi["game"] + ("  (simulated)" if vi["simulated"] else "")) size 14 color APEX_C["text"]
                    text ("Made for  " + vi["made_for"]) size 14 bold True color lvl_col
                    if vi["level"] == "match":
                        text "Compatible" size 12 color lvl_col
                    elif vi["level"] == "minor":
                        text "Version mismatch: bugs will likely occur. Wait for a modpack update or run the risk of bugs." size 11 color lvl_col
                    else:
                        text "Strongly advised not to play: it will likely break and won't be a good experience. Please update." size 11 color lvl_col
            frame:
                xsize 394 ysize 236 padding (18, 14)
                background apex_ui("panel", APEX_C["panel"])
                vbox:
                    spacing 6
                    text "SUPPORT" size 10 bold True color APEX_C["muted"] kerning 1.5
                    text "If you'd like to support the modpack's creation and future development, please support the game's developer first, then consider tipping me!" size 12 color APEX_C["text"]
                    imagebutton:
                        idle "apex_modpack/bmc_button.png"
                        hover "apex_modpack/bmc_button_hover.png"
                        action OpenURL(b.get("tip_url", "https://buymeacoffee.com/apex_modding"))
                        xalign 0.5
                    use apex_btn("Project page on GitHub", OpenURL(b.get("repo_url", "https://github.com/Apex-AIO/Apex-Town-of-Magic-Modpack")), "star")
        frame:
            xsize 800 padding (18, 14)
            background apex_ui("panel", APEX_C["panel"])
            vbox:
                spacing 6
                text "REVISIONS" size 10 bold True color APEX_C["muted"] kerning 1.5
                for m in apex_mm_modules():
                    hbox:
                        xsize 764
                        text apex_mm_safe(m["title"]) size 12 color APEX_C["text"]
                        text ("r" + m["rev"]) size 12 color APEX_C["gold"] xalign 1.0
                hbox:
                    xsize 764
                    text "Mod Manager" size 12 color APEX_C["text"]
                    text ("r" + b.get("core_rev", "?")) size 12 color APEX_C["gold"] xalign 1.0


# ---------------------------------------------------------------- settings (the gear) - Apex's mods and yours
screen apex_mm_settings(mid, user=False):
    modal True
    zorder 200
    style_prefix "apex_mm"
    if user:
        $ m = apex_um_get_info(mid) or {}
        $ title = m.get("name") or mid
        $ specs = [s for s in m.get("settings", []) if s["type"] != "text"]
    else:
        $ m = apex_mm_module(mid)
        $ title = m.get("title", mid)
        $ specs = m.get("settings") or []
    add Solid("#000000b8")
    frame:
        xalign 0.5 yalign 0.5 xsize 780 padding (26, 22)
        background apex_ui("panel", APEX_C["panel2"])
        at apex_rise
        vbox:
            spacing 10
            hbox:
                xfill True
                vbox:
                    text (apex_mm_safe(title)) size 20 bold True color APEX_C["gold"]
                    text "Settings - changes apply after a restart." size 12 color APEX_C["muted"]
                button:
                    xalign 1.0 padding (6, 6)
                    background apex_ui("panel", "#2a2236")
                    hover_background apex_ui("panel", APEX_BAD, 0.6)
                    action Hide("apex_mm_settings")
                    add apex_ui("ic_close", "#ffffff") zoom 0.7
            viewport:
                xsize 728 ysize min(400, 70 * max(1, len(specs)))
                mousewheel True draggable True scrollbars "vertical" spacing 4
                vbox:
                    spacing 6
                    for s in specs:
                        if user:
                            $ v = apex_um_get(mid, s["key"])
                            $ boolish = s["type"] in ("on/off", "onoff", "bool", "yes/no")
                            $ label = s.get("label") or s["key"]
                            $ helpt = ""
                            $ changed = False
                        else:
                            $ v = apex_mm_get(mid, s["key"])
                            $ boolish = s.get("type") == "bool"
                            $ label = s.get("label", s["key"])
                            $ helpt = s.get("help", "")
                            $ changed = (v != apex_mm_boot_value(mid, s["key"]))
                        frame:
                            xsize 716 padding (14, 9)
                            background apex_ui("panel", APEX_C["panel"])
                            hbox:
                                vbox:
                                    xsize 430 yalign 0.5
                                    text apex_mm_safe(label) size 13 bold True color APEX_C["text"]
                                    if helpt:
                                        text apex_mm_safe(helpt) size 11 color APEX_C["muted"]
                                hbox:
                                    yalign 0.5 spacing 6
                                    if boolish:
                                        null width 46
                                        use apex_switch(bool(v), Function(apex_um_step if user else apex_mm_step, mid, s["key"], 1))
                                    else:
                                        button:
                                            xsize 30 ysize 28 padding (0, 0)
                                            background apex_ui("panel", "#2a2236")
                                            hover_background apex_ui("panel", APEX_C["purple"], 0.6)
                                            action Function(apex_um_step if user else apex_mm_step, mid, s["key"], -1)
                                            text "-" size 16 bold True color "#ffffff" xalign 0.5 yalign 0.5
                                        frame:
                                            xsize 104 yalign 0.5 padding (0, 0) background None
                                            text apex_mm_fmt(s, v) size 14 bold True color (APEX_C["gold"] if changed else APEX_C["text"]) xalign 0.5
                                        button:
                                            xsize 30 ysize 28 padding (0, 0)
                                            background apex_ui("panel", "#2a2236")
                                            hover_background apex_ui("panel", APEX_C["purple"], 0.6)
                                            action Function(apex_um_step if user else apex_mm_step, mid, s["key"], 1)
                                            text "+" size 16 bold True color "#ffffff" xalign 0.5 yalign 0.5
                                    if not user and v != s.get("default"):
                                        text ("default " + apex_mm_fmt(s, s.get("default"))) size 10 color APEX_C["dim"] yalign 0.5
            hbox:
                xfill True
                use apex_btn("Reset to defaults", Function(apex_um_reset if user else apex_mm_reset, mid), "restart")
                frame:
                    xalign 1.0 padding (0, 0) background None
                    use apex_btn("Done", Hide("apex_mm_settings"), "check", "primary")
    key "game_menu" action Hide("apex_mm_settings")


# ---------------------------------------------------------------- outdated warning (main menu, once per launch)
screen apex_mm_outdated_warning():
    modal True
    style_prefix "apex_mm"
    $ vi = apex_mm_version()
    add Solid("#000000b0")
    frame:
        xalign 0.5 yalign 0.5 xsize 560 padding (26, 22)
        background apex_ui("panel", APEX_C["panel2"])
        at apex_rise
        vbox:
            spacing 12 xfill True
            add apex_ui("ic_warn", APEX_INFO) zoom 1.6 xalign 0.5
            text "Outdated modpack" size 22 bold True color APEX_INFO xalign 0.5
            text ("Your game is version %s, but this modpack was made for %s." % (vi["game"], vi["made_for"])) size 13 color APEX_C["text"] xalign 0.5 text_align 0.5
            text "You are running an outdated modpack, so all of Apex's mods have been disabled. If you wish to test the modpack on this new version, go to Apex's Modpack Manager." size 13 color APEX_C["text"] xalign 0.5 text_align 0.5
            hbox:
                xalign 0.5 spacing 12
                use apex_btn("Open Modpack Manager", [SetDict(apex_mm_seen_warning, 0, True), ShowMenu("apex_modpack_manager")], "star", "primary")
                use apex_btn("OK", SetDict(apex_mm_seen_warning, 0, True))


# ---------------------------------------------------------------- "Restart now to apply changes?"
# quitting=True: shown while the game is closing; returns True = restart
screen apex_mm_restart_prompt(quitting=False):
    modal True
    zorder 300
    style_prefix "apex_mm"
    add Solid("#000000b0")
    frame:
        xalign 0.5 yalign 0.5 xsize 480 padding (26, 22)
        background apex_ui("panel", APEX_C["panel2"])
        at apex_rise
        vbox:
            spacing 14 xfill True
            add apex_ui("ic_restart", APEX_C["gold"]) zoom 1.5 xalign 0.5
            text "Restart now to apply changes?" size 20 bold True color APEX_C["gold"] xalign 0.5
            text "You changed mods or their settings. They take effect when the game starts, so a restart is needed." size 13 color APEX_C["text"] text_align 0.5 xalign 0.5
            hbox:
                xalign 0.5 spacing 12
                use apex_btn("Restart now", (Return(True) if quitting else Function(apex_mm_restart)), "restart", "primary")
                use apex_btn(("Just quit" if quitting else "Later"), (Return(False) if quitting else [Hide("apex_mm_restart_prompt"), Return()]))
