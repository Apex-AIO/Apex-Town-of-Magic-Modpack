# apex_modkit.rpy  -  the Apex Mod Kit: simple, safe building blocks for YOUR mods (the "mods" folder).
#
# Use these in your mod's .rpy files (examples: mods/_templates and the modding guide).  Every function checks what
# you give it and, instead of crashing the game, writes a clear message to the Mod Manager (Your Mods -> your mod).
#
#   apex_setting("chance", 9)                          a setting from your mod_info.txt (the player's choice, or the default)
#   apex_log("text")                                   a line in mods/<your mod>/log.txt
#   apex_notify("text")                                a small message on screen
#   apex_add_accessory("ring", "Lucky Ring", icon="ring.png", description="...", stats={"luck": 10}, regen=0)
#   apex_add_clothing("reddress", "Red Dress", area="top", picture="reddress", icon="icon.png", stats={"allure": 5})
#   apex_add_clothing("vest", "Vest", equip_area=["top|0", "sleeves|1"], block_area=["top|1"], picture="vest", order=2500)
#                                                      exact game areas (top/bottom/feet/head/sleeves, each |0 or |1)
#   apex_give("ring")                                 give one of YOUR items to the player (again)
#   apex_on_new_game(func)  apex_on_load(func)  apex_on_wakeup(func)  apex_on_label("label name", func)
#   apex_every(seconds, func)                          run func every few seconds while playing
#   apex_wakeup_scene("my label", chance=0.2)          play your own scene (a label) on some quiet mornings
#   apex_give_gold(500)                                give Celica gold
#   apex_export("celica_top_normal")                   copy matching game pictures to mods/_exported (to edit them)
#   apex_game_version()                                the game's version, e.g. "0.77.002"
# Your mod's name is found automatically (from its folder), you never need to type it.

init -999 python:
    import renpy as _apex_renpy
    if getattr(_apex_renpy, "apex_exception_handler", None) and config.exception_handler is None:
        config.exception_handler = _apex_renpy.apex_exception_handler        # mod errors: explained, not fatal

init -900 python:
    import os as _ak_os, io as _ak_io, re as _ak_re, time as _ak_time, json as _ak_json, sys as _ak_sys
    import builtins as _ak_b
    import renpy as _ak_renpy

    APEX_MODS = getattr(_ak_renpy, "apex_mods", None) or {"mods": [], "files": {}, "errors": [], "conflicts": [],
                                                          "settings": {"enabled": {}, "values": {}, "auto_off": {}},
                                                          "log": [], "crash_recovered": [], "root": ""}
    apex_mod_warnings = {}                 # mod id -> [plain-words problems found while it loaded]
    _ak_items = {}                         # "mod/id" -> spec
    _ak_hooks = {"new_game": [], "load": [], "wakeup": [], "label": [], "every": [], "scenes": []}

    def apex_this_mod():
        """the mod (folder name) whose script is calling - found from the call stack"""
        f = _ak_sys._getframe(1)
        while f is not None:
            m = _ak_re.search(r"mods[/\\]([^/\\]+)[/\\]", f.f_code.co_filename or "")
            if m and not m.group(1).startswith("_"):
                return m.group(1)
            f = f.f_back
        return None

    def _ak_mod(mod):
        return mod or apex_this_mod() or "?"

    def apex_mod_problem(text, mod=None):
        """a problem that doesn't stop the mod (shown in the Mod Manager)"""
        mod = _ak_mod(mod)
        lst = apex_mod_warnings.setdefault(mod, [])
        if text not in lst:
            lst.append(text)
        apex_log("PROBLEM: " + text, mod)

    def apex_mod_info(mod=None):
        mod = _ak_mod(mod)
        for m in APEX_MODS["mods"]:
            if m["id"] == mod:
                return m
        return None

    def apex_game_version():
        return config.version

    def apex_log(text, mod=None):
        mod = _ak_mod(mod)
        try:
            p = _ak_os.path.join(APEX_MODS["root"], mod, "log.txt")
            if _ak_os.path.isdir(_ak_os.path.dirname(p)):
                with _ak_io.open(p, "a", encoding="utf8") as f:
                    f.write(u"%s  %s\n" % (_ak_time.strftime("%Y-%m-%d %H:%M:%S"), text))
        except Exception:
            pass

    def apex_notify(text):
        try:
            renpy.notify(text)
        except Exception:
            pass

    # ---------------- settings declared in mod_info.txt:  setting = key | type | default | min | max | label
    def _ak_conv(s, v):
        t = s["type"]
        try:
            if t in ("on/off", "onoff", "bool", "yes/no"):
                if isinstance(v, bool):
                    return v
                return str(v).strip().lower() in ("on", "yes", "true", "1")
            if t in ("text",):
                return str(v)
            x = float(v)
            lo = float(s["min"]) if s.get("min") not in ("", None) else None
            hi = float(s["max"]) if s.get("max") not in ("", None) else None
            if lo is not None:
                x = max(lo, x)
            if hi is not None:
                x = min(hi, x)
            return int(round(x)) if t in ("number", "whole", "1 in n", "percent", "seconds") else x
        except Exception:
            return None

    def apex_setting(key, default=None, mod=None):
        mod = _ak_mod(mod)
        info = apex_mod_info(mod)
        spec = None
        for s in (info or {}).get("settings", []):
            if s["key"] == key:
                spec = s
        if spec is None:
            if info is not None:
                apex_mod_problem("apex_setting('%s'): there is no 'setting = %s | ...' line in mod_info.txt" % (key, key), mod)
            return default
        chosen = APEX_MODS["settings"].get("values", {}).get(mod, {}).get(key)
        v = _ak_conv(spec, chosen if chosen is not None else spec["default"])
        if v is None:
            v = _ak_conv(spec, spec["default"])
        return default if v is None else v

    # ---------------- items: accessories and clothing that live in the player's inventory
    _AK_STATS = {"allure": "a_allure", "lewdness": "a_lewdness", "willpower": "a_willpower", "cooldown": "a_cooldown",
                 "arcane": "a_arcane", "speed": "a_speed", "luck": "a_luck"}
    _AK_AREAS = {"top": "top|1", "bra": "top|0", "bottom": "bottom|1", "panties": "bottom|0", "shoes": "feet|1"}

    def _ak_var(mod, iid):
        return "i_mod_" + _ak_re.sub(r"[^a-z0-9]+", "_", ("%s_%s" % (mod, iid)).lower()).strip("_")

    def _ak_icon(mod, icon):
        if not icon:
            return "ICON/attire_tanktop.png"
        for cand in ("mods/%s/%s" % (mod, icon), "mods/%s/images/%s" % (mod, icon), icon):     # own folder first
            if renpy.loadable(cand):
                return cand
        apex_mod_problem("icon '%s' not found - put the picture in your mod folder (e.g. mods/%s/%s)" % (icon, mod, icon), mod)
        return "ICON/attire_tanktop.png"

    def _ak_check_stats(mod, stats):
        good = {}
        for k, v in (stats or {}).items():
            a = _AK_STATS.get(str(k).lower())
            if a is None:
                apex_mod_problem("unknown stat '%s' - use: %s" % (k, ", ".join(sorted(_AK_STATS))), mod)
            elif not isinstance(v, (int, float)) or isinstance(v, bool):
                apex_mod_problem("stat '%s' needs a number, got %r" % (k, v), mod)
            else:
                good[a] = v
        return good

    def apex_add_accessory(item_id, name, icon=None, description="", stats=None, regen=0, give=True, mod=None):
        """an accessory with stats (no picture on Celica).  stats: {"luck": 10, "speed": 5} on the 0-100 scale shown
        in game.  regen: HP and MP back per battle turn, in % of the maximum."""
        mod = _ak_mod(mod)
        _ak_items["%s/%s" % (mod, item_id)] = dict(mod=mod, id=item_id, name=name, icon=_ak_icon(mod, icon),
            desc=description, stats=_ak_check_stats(mod, stats), regen=regen, give=give,
            props=["equipable", "hasshadow", "unique", "toggleattire"], extra={"equip_area": ["acc_%s|0" % _ak_var(mod, item_id)]})

    _AK_SLOTS = ("top", "bottom", "feet", "head", "sleeves", "hair")      # the game's area names; each has |0 and |1 (hair: |0)

    def _ak_area_list(mod, fname, value):
        """a list of game areas like ["top|0", "sleeves|1"] - checked, so a typo is explained instead of breaking the game"""
        if isinstance(value, str):
            value = [value]
        good = []
        for v in (value or []):
            s = str(v).strip().lower()
            slot, _, level = s.partition("|")
            if slot in _AK_SLOTS and level in ("0", "1"):
                good.append(s)
            else:
                apex_mod_problem("%s: '%s' is not a game area - use e.g. top|0, top|1, bottom|0, bottom|1, feet|1, head|1, sleeves|1 "
                                 "(slots: %s; level 0 = underwear/inner layer, 1 = outer layer)" % (fname, v, ", ".join(_AK_SLOTS)), mod)
        return good

    def apex_add_clothing(item_id, name, area=None, picture="", icon=None, description="", stats=None, give=True,
                          tucked_in=True, equip_area=None, block_area=None, order=None, properties=None,
                          stripable=True, molestable=True, extra=None, mod=None):
        """wearable clothing.  Simple: area = top, bra, bottom, panties or shoes.  Exact (same as the game's own clothes):
        equip_area = ["top|0", "sleeves|1"] (areas it is worn on; the first one is the main area and shows its inventory
        picture) and block_area = ["top|1"] (areas it covers, so nothing else can be worn there); each of top, bottom, feet,
        head, sleeves has a |0 and |1 layer.  order = sort position in the inventory, properties = the game's item
        properties (default: equipable, haswideshadow, unique, toggleattire), stripable / molestable = whether she can be
        stripped / groped out of it, extra = more game clothing keys (e.g. extra_cost).  picture: the name in the picture
        files - Celica wearing it in a pose is  images/CHAR/celica/<pose>_<area word>_<picture>-<size>.png  (see the guide).
        Poses without a picture show her without that piece."""
        mod = _ak_mod(mod)
        if equip_area is None and area is None:
            apex_mod_problem("apex_add_clothing('%s'): give area=... or equip_area=[...]" % item_id, mod)
            return
        if equip_area is None:
            a = _AK_AREAS.get(str(area).lower())
            if a is None:
                apex_mod_problem("apex_add_clothing('%s'): area must be one of %s, not '%s'" % (item_id, ", ".join(_AK_AREAS), area), mod)
                return
            areas = [a]
            if block_area is None and a in ("top|0", "bottom|0"):
                block_area = [a.split("|")[0] + "|1"]
        else:
            areas = _ak_area_list(mod, "equip_area", equip_area)
            if not areas:
                apex_mod_problem("apex_add_clothing('%s'): equip_area has no valid area" % item_id, mod)
                return
        blocks = _ak_area_list(mod, "block_area", block_area)
        word = areas[0].split("|")[0]
        if word in ("top", "bottom", "feet") and not renpy.loadable("images/CHAR/celica/celica_%s_%s-530-530-1.png" % (word, picture)):
            apex_mod_problem("no picture of Celica standing in '%s': add images/CHAR/celica/celica_%s_%s-530-530-1.png "
                             "to your mod (other poses are optional)" % (name, word, picture), mod)
        if properties is None:
            props = ["equipable", "haswideshadow", "unique", "toggleattire"] + (["belowpants"] if (word == "top" and tucked_in) else [])
        else:
            props = list(properties)
            if "equipable" not in props:
                props.insert(0, "equipable")
        ex = {"name": picture, "equip_area": areas, "stripable": bool(stripable), "molestable": bool(molestable)}
        if blocks:
            ex["block_area"] = blocks
        if isinstance(extra, dict):
            for k, v in extra.items():
                if k not in ("name", "equip_area", "block_area"):
                    ex[k] = v
        item_order = order if (isinstance(order, int) and not isinstance(order, bool)) else None
        if order is not None and item_order is None:
            apex_mod_problem("apex_add_clothing('%s'): order must be a whole number, got %r" % (item_id, order), mod)
        _ak_items["%s/%s" % (mod, item_id)] = dict(mod=mod, id=item_id, name=name, icon=_ak_icon(mod, icon),
            desc=description, stats=_ak_check_stats(mod, stats), regen=0, give=give, props=props, extra=ex, order=item_order)

    def _ak_stat_dict(stats, regen):
        d = {}
        for name, shown in stats.items():
            attr = getattr(store, name, None)
            if attr is not None and shown:
                v = shown * attribute_get_max_value(attr) / 100.0
                d[attr] = int(v) if float(v).is_integer() else round(v, 2)
        if regen:
            r = int(regen) if float(regen).is_integer() else round(regen, 2)
            d["hp_regen%s" % r] = "{color=%s}HP{/color} {color=%s}Regen{/color} {color=%s}+%s%%/turn{/color}" % (ColorHealth, ColorOK, ColorOK, r)
            d["mp_regen%s" % r] = "{color=%s}MP{/color} {color=%s}Regen{/color} {color=%s}+%s%%/turn{/color}" % (ColorMagic, ColorOK, ColorOK, r)
        return d

    def _ak_install(force_give=None):
        if not _ak_items or not all(hasattr(store, n) for n in ("inventory", "main_vars", "Item", "inventory_add")):
            return
        mv = store.main_vars
        if not isinstance(mv, _ak_b.dict) or "attire_list" not in mv:
            return
        given = mv.setdefault("apex_mod_given", [])
        for key, s in _ak_items.items():
            try:
                var = _ak_var(s["mod"], s["id"])
                item = getattr(store, var, None)
                if item is None or not isinstance(item, store.Item):
                    item = store.Item(name=s["name"], type="Equipment", image=s["icon"])
                    setattr(store, var, item)
                    try:
                        if not all_items.in_list(item):
                            all_items.add(item)
                    except Exception:
                        pass
                item.name, item.image = s["name"], s["icon"]
                item.refresh_imagetext()
                item.order, item.rarity, item.cost = s.get("order") or 9000, 1, 0
                item.properties = list(s["props"])
                item.equip_extra = dict(s["extra"])
                new = _ak_stat_dict(s["stats"], s["regen"])
                if getattr(item, "equip_attribure_dict", None) != new and not is_equiped(item):
                    item.equip_attribure_dict = new
                item.set_desc(s["desc"] or s["name"])
                if (s["give"] and key not in given) or key == force_give:
                    if store.inventory.count(item) <= 0:
                        store.inventory_add(store.inventory, item)
                    if key not in given:
                        given.append(key)
            except Exception as e:
                apex_mod_problem("could not add '%s': %s" % (s["name"], e), s["mod"])

    def apex_give(item_id, mod=None):
        mod = _ak_mod(mod)
        key = "%s/%s" % (mod, item_id)
        if key not in _ak_items:
            apex_mod_problem("apex_give('%s'): no item with that id in this mod" % item_id, mod)
            return
        _ak_install(force_give=key)

    # ---------------- events
    def _ak_run(kind, func, mod, *args):
        try:
            func(*args)
        except Exception as e:
            import traceback
            full = traceback.format_exc()
            h = getattr(_ak_renpy, "apex_exception_handler", None)
            if h:
                h("%s: %s" % (type(e).__name__, e), full.replace('File "', 'File "mods/%s/' % mod, 0) if "mods/" not in full else full)
            else:
                apex_mod_problem("%s hook failed: %s" % (kind, e), mod)

    def apex_on_new_game(func, mod=None):
        _ak_hooks["new_game"].append((func, _ak_mod(mod)))

    def apex_on_load(func, mod=None):
        _ak_hooks["load"].append((func, _ak_mod(mod)))

    def apex_on_wakeup(func, mod=None):
        _ak_hooks["wakeup"].append((func, _ak_mod(mod)))

    def apex_on_label(label, func, mod=None):
        _ak_hooks["label"].append((label, func, _ak_mod(mod)))

    def apex_every(seconds, func, mod=None):
        _ak_hooks["every"].append([max(0.5, float(seconds)), func, _ak_mod(mod), 0.0])

    def apex_wakeup_scene(label, chance=0.2, mod=None):
        """on a quiet morning (the game planned nothing), play your label with this chance (0.2 = 1 in 5)"""
        mod = _ak_mod(mod)
        if not renpy.has_label(label):
            apex_mod_problem("apex_wakeup_scene: there is no label '%s' in your mod" % label, mod)
            return
        _ak_hooks["scenes"].append((label, float(chance), mod))

    def apex_give_gold(amount, mod=None):
        try:
            inventory_add(store.inventory, store.i_coin, int(amount))
        except Exception as e:
            apex_mod_problem("apex_give_gold: %s" % e, _ak_mod(mod))

    def apex_export(name_part):
        """copy every game picture whose name contains name_part to mods/_exported/ (keeps the game's folders)"""
        import renpy.loader as L
        n = 0
        root = _ak_os.path.join(APEX_MODS["root"], "_exported")
        for fn, index in L.archives:
            for k in index:
                if name_part and name_part.lower() in k.lower() and k.lower().endswith(".png") and n < 3000:
                    dst = _ak_os.path.join(root, k)
                    _ak_os.makedirs(_ak_os.path.dirname(dst), exist_ok=True)
                    with open(dst, "wb") as f:
                        f.write(L.load_from_archive(k).read())
                    n += 1
        return n

    def _ak_label_cb(name, abnormal):
        if name == "wake_up.normal_wakeup":
            for func, mod in list(_ak_hooks["wakeup"]):
                _ak_run("apex_on_wakeup", func, mod)
            try:
                if _ak_hooks["scenes"] and getattr(store, "wakeup_event_pick", "x") == "":
                    import random
                    for label, chance, mod in random.sample(_ak_hooks["scenes"], len(_ak_hooks["scenes"])):
                        if random.random() < chance:
                            store.apex_kit_scene_label = label
                            store.wakeup_event_pick = "afterwakeup_apex_kit_scene"     # the game calls events_apex_kit_scene
                            break
            except Exception as e:
                apex_mod_problem("wake-up scene: %s" % e, "?")
        for lab, func, mod in list(_ak_hooks["label"]):
            if lab == name:
                _ak_run("apex_on_label", func, mod)

    _ak_state = {"started": False, "next_install": 0.0}

    def _ak_tick():
        now = _ak_time.time()
        if now >= _ak_state["next_install"]:
            _ak_state["next_install"] = now + 2.0
            _ak_install()
            mv = getattr(store, "main_vars", None)
            if isinstance(mv, _ak_b.dict) and "attire_list" in mv and not mv.get("apex_mod_newgame_done"):
                mv["apex_mod_newgame_done"] = True
                for func, mod in list(_ak_hooks["new_game"]):
                    _ak_run("apex_on_new_game", func, mod)
        for h in _ak_hooks["every"]:
            if now >= h[3]:
                h[3] = now + h[0]
                if getattr(store, "main_vars", None) is not None and not main_menu:
                    _ak_run("apex_every", h[1], h[2])

    def _ak_after_load():
        _ak_install()
        for func, mod in list(_ak_hooks["load"]):
            _ak_run("apex_on_load", func, mod)

    def _ak_started():
        # the game got through its start-up: tell the loader this start did not crash
        try:
            p = _ak_os.path.join(APEX_MODS["root"], "_manager", "boot.json")
            if APEX_MODS["root"] and _ak_os.path.isdir(_ak_os.path.dirname(p)):
                with _ak_io.open(p, "w", encoding="utf8") as f:
                    _ak_json.dump({"starting": False, "time": _ak_time.time()}, f)
        except Exception:
            pass

    config.label_callbacks.append(_ak_label_cb)
    config.periodic_callbacks.append(_ak_tick)
    config.after_load_callbacks.append(_ak_after_load)
    config.start_callbacks.append(_ak_started)


# the game plays a picked morning scene by calling "events_<name>"; this one plays the mod's own label
label events_apex_kit_scene:
    if renpy.has_label(apex_kit_scene_label):
        call expression apex_kit_scene_label
    return

default apex_kit_scene_label = ""
