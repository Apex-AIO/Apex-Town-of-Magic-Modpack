# tom_mod_guard.rpy  -  shared safety check for the Town of Magic mods (ships with every mod; all copies are identical)
#
# Every mod asks this guard before changing anything in the game.  The guard compares the game functions the mod
# hooks into with fingerprints taken on the game version the mod was made for.
#   * same game version, or every hooked function unchanged  -> the mod runs
#   * a hooked function changed or disappeared               -> the mod stays OFF (the game runs as vanilla)
# Every start writes  game/tom_mod_report.txt : game version, and per mod what changed (function, file, line).
# Send that file to get the mods updated for a new game version.
#
# Switches (create the file in the game folder, contents don't matter):
#   tom_mods_off.txt         every mod off, no matter what
#   tom_mods_force_on.txt    every mod on even after a game update (at your own risk)
#   tom_fake_version.txt     TESTING: pretend the game is the version written in the file (e.g. 0.78.001)
# Single modules are switched on/off in Apex's Modpack Manager (main menu); that choice is kept in persistent.apex_mm_off
# and takes effect at the next start.  Module settings (the gear) are kept in persistent.apex_mm_settings.
#
# Game version check (game version vs TOM_TESTED_GAME):
#   same                      -> "match"
#   same first two numbers    -> "minor" difference (e.g. 0.77.002 -> 0.77.004)
#   otherwise                 -> "major" difference (e.g. 0.77.002 -> 0.78.001)
#   game NEWER than the pack  -> the pack is outdated: every module stays OFF until the player turns on
#                                "Test modpack" in the manager (persistent.apex_mm_test_version = that game version)

init 0 python:
    import os as _tg_os, io as _tg_io, time as _tg_time, hashlib as _tg_hashlib
    import builtins as _tg_b       # in Ren'Py scripts dict/list are Ren'Py's own types: check against the real ones

    TOM_GUARD_VERSION = 3
    TOM_TESTED_GAME = "0.77.002"

    # function name -> fingerprint on 0.77.002 (filled in from a recorded run)
    TOM_FINGERPRINTS = {
        "update_inventory_frame_items": "fe49107e27cb",    # procedures.rpy:1885
        "equipment_are_empty": "d869cfd4a960",    # procedures.rpy:2071
        "image_add_composite_path": "1f6d4a36b344",    # animations.rpy:421
        "list_files_match": "e80339dd6427",    # procedures.rpy:2865
        "list_files_regex": "69d593230ea8",    # procedures.rpy:2845
        "list_files_containing": "08436d46974c",    # procedures.rpy:2869
        "enemimage": "3851ac5cb260",    # screen_controller.rpy:1276
        "clothes_dict_set": "57840873f497",    # clothes.rpy:27
        "clothes_equip": "591c72d60bdb",    # clothes.rpy:497
        "clothes_redress_item": "fb16f80c8827",    # clothes.rpy:249
        "fix_clothes_button": "e685057397fd",    # clothes.rpy:1168
        "fix_clothes_button_enabled": "c67cf4279900",    # clothes.rpy:1157
        "equip_procedure": "6bec6055c892",    # equip_inventory.rpy:189
        "refresh_attire_dict": "18de4def2e79",    # clothes.rpy:429
        "clothes_redress_all": "ee74b495e522",    # clothes.rpy:301
        "Item": "916e549c3199",    #
        "Equip_Inventory": "1f9ac58003b6",    #
        "enemy_decides": "5a426adba885",    # enemy.rpy:358
        "enemy_mod_hp": "d3d7b648db6c",    # enemy.rpy:1671
        "body_influencelvl_mod": "322056f69bed",    # body_influence.rpy:463
        "attribute_mod": "e28e2afa5682",    # attribute.rpy:364
        "print_reward_message": "60b8444d1e7e",    # procedures.rpy:1498
    }

    tom_mod_status = {}            # mod -> "on" / "off: <reason>"
    _tg_lines = []

    def _tg_path(name):
        return _tg_os.path.join(config.basedir, "game", name)

    # Apex's Modpack Manager choices, read ONCE at start-up so every module sees the same thing
    # (a bad value in persistent - wrong type, unknown module - is ignored, never an error)
    def _tg_read_persistent():
        off = getattr(persistent, "apex_mm_off", None)
        off = frozenset(x for x in off if isinstance(x, str)) if isinstance(off, (_tg_b.list, _tg_b.tuple, _tg_b.set, _tg_b.frozenset)) else frozenset()
        sets = getattr(persistent, "apex_mm_settings", None)
        clean = {}
        if isinstance(sets, _tg_b.dict):
            for m, d in sets.items():
                if isinstance(m, str) and isinstance(d, _tg_b.dict):
                    clean[m] = dict((k, v) for k, v in d.items() if isinstance(k, str) and isinstance(v, (bool, int, float)))
        test = getattr(persistent, "apex_mm_test_version", None)
        return off, clean, (test if isinstance(test, str) else None)

    TOM_BOOT_OFF, TOM_BOOT_SETTINGS, TOM_BOOT_TEST = _tg_read_persistent()
    TOM_SETTING_DEFAULTS = {}      # (mod, key) -> default in the mod's code (the manager checks it against its list)

    def tom_setting_spec(mod, key):
        for m in ((globals().get("APEX_BUILD") or {}).get("modules") or []):
            if m.get("id") == mod:
                for s in (m.get("settings") or []) + (m.get("subs") or []):
                    if s.get("key") == key:
                        return s
        return None

    def tom_setting(mod, key, default):
        # a module setting chosen in Apex's Modpack Manager (the gear), kept inside its allowed range;
        # the mod's own default whenever nothing valid was chosen
        TOM_SETTING_DEFAULTS[(mod, key)] = default
        v = TOM_BOOT_SETTINGS.get(mod, {}).get(key, default)
        if isinstance(default, bool):
            return v if isinstance(v, bool) else default
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")):
            return default
        spec = tom_setting_spec(mod, key)
        if spec is not None:
            v = min(max(v, spec.get("min", v)), spec.get("max", v))
        return int(round(v)) if isinstance(default, int) else float(v)

    def _tg_vtuple(s):
        import re
        return tuple(int(x) for x in re.findall(r"\d+", s or ""))

    _tg_vinfo = {}

    def tom_version_info():
        # game version vs the version the mods were made for (worked out once, after the game has set config.version)
        if not _tg_vinfo:
            game = config.version
            try:
                if _tg_os.path.exists(_tg_path("tom_fake_version.txt")):
                    with _tg_io.open(_tg_path("tom_fake_version.txt"), encoding="utf8") as f:
                        fake = f.read().strip()
                    if _tg_vtuple(fake):
                        game = fake
            except Exception:
                pass
            g, m = _tg_vtuple(game), _tg_vtuple(TOM_TESTED_GAME)
            level = "match" if g == m else ("minor" if g[:2] == m[:2] else "major")
            newer = g > m
            approved = newer and TOM_BOOT_TEST == game
            forced = _tg_os.path.exists(_tg_path("tom_mods_force_on.txt"))
            _tg_vinfo.update(game=game, made_for=TOM_TESTED_GAME, level=level, newer=newer,
                             simulated=(game != config.version), approved=approved,
                             locked=newer and not approved and not forced)
        return _tg_vinfo

    def _tg_fingerprint(obj):
        """md5 of a function's compiled code (or of a class's methods); None if it isn't code"""
        h = _tg_hashlib.md5()

        def walk(co):
            h.update(co.co_code)
            h.update(repr(co.co_names).encode())
            for c in co.co_consts:
                if hasattr(c, "co_code"):
                    walk(c)
                elif isinstance(c, frozenset):
                    h.update(repr(sorted(repr(x) for x in c)).encode())
                else:
                    h.update(repr(c).encode())
        if isinstance(obj, type):
            found = False
            for k in sorted(vars(obj)):
                v = vars(obj)[k]
                if hasattr(v, "__code__"):
                    h.update(k.encode())
                    walk(v.__code__)
                    found = True
            return h.hexdigest()[:12] if found else None
        if hasattr(obj, "__code__"):
            walk(obj.__code__)
            return h.hexdigest()[:12]
        return None

    def _tg_where(obj):
        if isinstance(obj, type):                               # a class: where its first method is
            for v in vars(obj).values():
                if hasattr(v, "__code__"):
                    obj = v
                    break
        co = getattr(obj, "__code__", None)
        if co is None:
            return ""
        return "%s:%d" % (co.co_filename.replace("\\", "/").split("/")[-1], co.co_firstlineno)

    def tom_mod_ok(mod, hooks=(), needs=()):
        """True if the mod may change the game.  hooks = game functions it wraps/replaces (fingerprinted),
        needs = other game names it uses (must exist)."""
        problems, recorded = [], []
        if _tg_os.path.exists(_tg_path("tom_mods_off.txt")):
            tom_mod_status[mod] = "off: tom_mods_off.txt"
            _tg_lines.append("[%s] OFF (tom_mods_off.txt)" % mod)
            return False
        if tom_version_info()["locked"]:
            tom_mod_status[mod] = "off: outdated modpack"
            _tg_lines.append("[%s] OFF (the game is newer than the modpack and 'Test modpack' is off)" % mod)
            return False
        if mod in TOM_BOOT_OFF:
            tom_mod_status[mod] = "off: switched off"
            _tg_lines.append("[%s] OFF (switched off in Apex's Modpack Manager)" % mod)
            return False
        g = vars(store)
        for n in needs:
            if n not in g:
                problems.append("missing: %s (used by the mod)" % n)
        for n in hooks:
            if n not in g:
                problems.append("missing: %s (hooked by the mod)" % n)
                continue
            fp = _tg_fingerprint(g[n])
            want = TOM_FINGERPRINTS.get(n)
            if want is None:
                recorded.append("    \"%s\": \"%s\",    # %s" % (n, fp, _tg_where(g[n])))
            elif fp != want:
                problems.append("changed: %s  (%s)  fingerprint %s, made for %s" % (n, _tg_where(g[n]), fp, want))
        same_game = tom_version_info()["level"] == "match"
        force = _tg_os.path.exists(_tg_path("tom_mods_force_on.txt"))
        if problems and not force:
            tom_mod_status[mod] = "off: game changed"
            _tg_lines.append("[%s] OFF - the game changed where this mod hooks in:" % mod)
            _tg_lines.extend("    " + p for p in problems)
            return False
        tom_mod_status[mod] = "on" + (" (forced)" if problems else "")
        _tg_lines.append("[%s] ON%s%s" % (mod, "" if same_game else " (different game version, but nothing this mod uses changed)",
                                         " - FORCED despite: " + "; ".join(problems) if problems else ""))
        if recorded:
            _tg_lines.append("    fingerprints not recorded yet:")
            _tg_lines.extend(recorded)
        return True

    def _tg_write_report():
        try:
            with _tg_io.open(_tg_path("tom_mod_report.txt"), "w", encoding="utf8") as f:
                f.write(u"Town of Magic mods - compatibility report  (%s)\n" % _tg_time.strftime("%Y-%m-%d %H:%M"))
                vi = tom_version_info()
                state = ""
                if vi["newer"]:
                    state = ", game is newer: " + ("testing allowed" if vi["approved"] else "LOCKED" if vi["locked"] else "forced on")
                f.write(u"game version %s%s, mods made for %s (%s%s), Ren'Py %s, guard v%d\n\n"
                        % (vi["game"], " (SIMULATED by tom_fake_version.txt)" if vi["simulated"] else "", TOM_TESTED_GAME,
                           vi["level"], state, renpy.version_only, TOM_GUARD_VERSION))
                bad = []
                for (m, k), d in sorted(TOM_SETTING_DEFAULTS.items()):
                    s = tom_setting_spec(m, k)
                    if s is not None and s.get("default") != d:
                        bad.append(u"    %s.%s: the mod's default is %r, the manager's list says %r" % (m, k, d, s.get("default")))
                    elif s is None and globals().get("APEX_BUILD"):
                        bad.append(u"    %s.%s: not in the manager's list" % (m, k))
                if bad:
                    f.write(u"SETTINGS LIST PROBLEMS (fix Mods/modpack.json):\n" + u"\n".join(bad) + u"\n\n")
                f.write(u"\n".join(_tg_lines) + u"\n")
        except Exception:
            pass

    def _tg_notify_off():
        if tom_version_info()["locked"]:
            return                     # the main menu explains it (Apex's Modpack Manager)
        off = [m for m, s in tom_mod_status.items() if s.startswith("off: game")]
        if off:
            renpy.notify("Town of Magic mods switched off after a game update: %s. See tom_mod_report.txt" % ", ".join(sorted(off)))

# written after every mod has checked in (mods check at init 1..999; same priority runs in file-name order, and
# tom_mod_guard sorts after every module file)
init 999 python:
    _tg_write_report()
    if _tg_notify_off not in config.start_callbacks:
        config.start_callbacks.append(_tg_notify_off)
