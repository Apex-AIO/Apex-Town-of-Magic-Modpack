# clothing_remover.rpy  -  two mods in one file, each with its own switch in Apex's Modpack Manager:
#   Clothing Remover (clothing_remover)  the three red-X pieces below
#   Combat Helpers   (combat_helpers)    the three Combat Helper accessories below
#
#   Shoes            visually removes her shoes (shoes are cosmetic, no effect in combat)
#   Top/Bra          removes top + bra and puts her top in the 'exposed' state
#   Pants/Underwear  removes pants + panties and puts her bottom in the 'exposed' state
#                    (both: Allure/Lewdness +25, Willpower/Cooldown/Arcane/Speed -25)
#   Combat Helper Green / Orange / Red   10% / 50% / 100% of "Speedster's Blessing"
#                    (Arcane/Speed/Luck/Cooldown +50, Willpower +100, HP + MP regen 10% per turn at 100%)
#                    They share their own slot (one at a time) and are not drawn on her.
#
# How it works
#   The game keeps Celica's clothes in clothes_dict:  "area|level" -> [name, stripped, stripable, molestable]
#   (top|0 = bra, top|1 = top, bottom|0 = panties, bottom|1 = pants, feet|1 = shoes).
#   'Exposed' simply means every level of that area is stripped (clothes_get_equip_level(area) == -1),
#   exactly what happens when a monster tears the last layer.
#   Top/Bra and Pants/Underwear are built like the Jammie Top / Pink Briefs: one piece that takes level 0
#   and blocks level 1.  Their level-0 entry is kept permanently "stripped", so the game draws her bare and
#   the monsters treat that spot as already torn.  Anything that would redress her (end of battle, garment
#   guardian, "fix clothes") leaves these pieces stripped.
#   Equip any other top/bra/pants/panties/shoes to swap back, or click the red X again to take it off
#   (her default clothes for that spot come back).
#
# Uninstall: delete the clothing_remover folder.  Saves stay loadable (the pieces are plain game Items);
# if one was worn, just equip other clothes.
#
# Debug log (off by default): set XR_LOG = True -> game/xr_log.txt

init 999 python:
    import builtins as _bt     # dict/list in Ren'Py scripts are Ren'Py's own types; check against the real ones
    # only when the shared guard says the game still matches what this mod was made for (tom_mod_guard.rpy)
    _XR_NEEDS = ['is_equiped', 'inventory_add', 'attribute_get_max_value', 'attribute_mod_equip_value', 'Attribute', 'ColorHealth', 'ColorMagic', 'ColorOK']
    XR_REMOVER_ON = tom_mod_ok('clothing_remover',
                  hooks=['clothes_dict_set', 'clothes_equip', 'clothes_redress_item', 'fix_clothes_button', 'fix_clothes_button_enabled', 'equip_procedure', 'refresh_attire_dict', 'clothes_redress_all', 'Item', 'Equip_Inventory'],
                  needs=_XR_NEEDS + ['gemstone_is_garment_guardian', 'clothes_equiparealevel_disabled', 'refresh_gui_screen', 'clothes_get_equip_level', 'get_enemy_player'])
    XR_HELPERS_ON = tom_mod_ok('combat_helpers', hooks=['Item', 'Equip_Inventory'], needs=_XR_NEEDS)
    if XR_REMOVER_ON or XR_HELPERS_ON:
        import os, io, time
        import renpy.store as store

        XR_LOG = False
        XR_ICON = "clothing_remover/xr_icon.png"

        # Stats are written the way the game shows them (Attributes tab / tooltips: 0-100).
        # The game stores Arcane, Speed, Luck and Cooldown on a 0-200 scale; the conversion is done for you.
        # the red-X items' stats, times the "strength" setting (gear in Apex's Modpack Manager, default 100%)
        _xr_k = tom_setting('clothing_remover', 'remover_strength', 100) / 100.0
        XR_REMOVER_STATS = dict((a, int(round(v * _xr_k))) for a, v in
                                {"a_allure": 25, "a_lewdness": 25, "a_willpower": -25, "a_cooldown": -25, "a_arcane": -25, "a_speed": -25}.items())

        # Combat Helpers: "Speedster's Blessing" scaled.  Its stats: Arcane/Speed/Luck/Cooldown +50, Willpower +100,
        # HP and MP regen 10% of max per battle turn.
        XR_HELPER_BASE = {"a_arcane": 50, "a_speed": 50, "a_luck": 50, "a_cooldown": 50, "a_willpower": 100}
        XR_HELPER_REGEN = 10
        XR_HELPER_SCALE = tuple((c, tom_setting('combat_helpers', 'helper_' + c, d) / 100.0)
                                for c, d in (("green", 10), ("orange", 50), ("red", 100)))

        def _xr_items():
            # one dict per item: var, name, desc, image, order, properties, equip_extra, stats (shown values), regen (% per turn)
            rem_props = ["equipable", "haswideshadow", "unique", "toggleattire"]
            items = [] if not XR_REMOVER_ON else [
                dict(var="i_xr_shoes", name="Shoes", desc="Visually removes", image=XR_ICON, order=2390, props=rem_props,
                     extra={"name": "nude", "equip_area": ["feet|1"], "stripable": True, "molestable": True, "xr": "feet"}, stats={}, regen=0),
                dict(var="i_xr_top", name="Top/Bra", desc="Visually removes and sets player in 'exposed' state for top body part", image=XR_ICON, order=2391, props=rem_props,
                     extra={"name": "nude", "equip_area": ["top|0"], "block_area": ["top|1"], "stripable": True, "molestable": True, "xr": "top"}, stats=XR_REMOVER_STATS, regen=0),
                dict(var="i_xr_bottom", name="Pants/Underwear", desc="Visually removes and sets player in 'exposed' state for pants body part", image=XR_ICON, order=2392, props=rem_props,
                     extra={"name": "nude", "equip_area": ["bottom|0"], "block_area": ["bottom|1"], "stripable": True, "molestable": True, "xr": "bottom"}, stats=XR_REMOVER_STATS, regen=0),
            ]
            for i, (color, k) in enumerate(XR_HELPER_SCALE if XR_HELPERS_ON else ()):
                # own slot "helper|0": one helper at a time, no clothes_dict entry (no "name"), never drawn on her
                items.append(dict(var="i_xr_helper_" + color, name="Combat Helper " + color.title(), desc="Helpful Combat Stats",
                                  image="clothing_remover/helper_%s.png" % color, order=2393 + i, props=["equipable", "hasshadow", "unique", "toggleattire"],
                                  extra={"equip_area": ["helper|0"]}, stats={a: v * k for a, v in XR_HELPER_BASE.items()}, regen=XR_HELPER_REGEN * k))
            return items

        XR_VARS = [s["var"] for s in _xr_items()]

        def _xr_num(v):
            return int(v) if float(v).is_integer() else round(v, 2)

        def _xr_stat_dict(stats, regen):
            # shown values -> the game's equip_attribure_dict
            d = {}
            for name, shown in stats.items():
                attr = getattr(store, name, None)
                if attr is not None and shown:
                    d[attr] = _xr_num(shown * attribute_get_max_value(attr) / 100.0)
            if regen:
                r = _xr_num(regen)
                d["hp_regen%s" % r] = "{color=%s}HP{/color} {color=%s}Regen{/color} {color=%s}+%s%%/turn{/color}" % (ColorHealth, ColorOK, ColorOK, r)
                d["mp_regen%s" % r] = "{color=%s}MP{/color} {color=%s}Regen{/color} {color=%s}+%s%%/turn{/color}" % (ColorMagic, ColorOK, ColorOK, r)
            return d

        def _xr_set_stats(item, new):
            # changing the stats of a piece she is wearing: apply the difference, or unequipping would leave stats behind
            old = dict(getattr(item, "equip_attribure_dict", None) or {})
            if old == new:
                return
            if is_equiped(item):
                for k in set(old) | set(new):
                    if isinstance(k, Attribute):
                        delta = new.get(k, 0) - old.get(k, 0)
                        if delta:
                            attribute_mod_equip_value(k, delta)
                evl = main_vars.setdefault("equip_value_list", [])
                for k in old:
                    if not isinstance(k, Attribute) and k in evl:
                        evl.remove(k)
                for k in new:
                    if not isinstance(k, Attribute):
                        evl.append(k)
                _xr_log("stats changed while worn: %s" % item.name)
            item.equip_attribure_dict = new

        def _xr_log(msg):

            tom_mod_log_check('clothing_remover', msg)
            if not XR_LOG:
                return
            try:
                with io.open(os.path.join(config.basedir, "game", "xr_log.txt"), "a", encoding="utf8") as f:
                    f.write(u"%s  %s\n" % (time.strftime("%H:%M:%S"), msg))
            except Exception:
                pass

        def _xr_is_remover(item):
            try:
                return "xr" in item.equip_extra
            except Exception:
                return False

        def _xr_exposed_keys():
            # clothes_dict keys held by a worn Top/Bra or Pants/Underwear remover: always stripped
            keys = set()
            mv = getattr(store, "main_vars", None)
            if not isinstance(mv, _bt.dict):
                return keys
            for item in mv.get("attire_list", []):
                if _xr_is_remover(item) and item.equip_extra["xr"] in ("top", "bottom"):
                    keys.update(item.equip_extra["equip_area"])
            return keys

        def _xr_enforce():
            cd = getattr(store, "clothes_dict", None)
            if not isinstance(cd, _bt.dict):
                return
            for key in _xr_exposed_keys():
                if key in cd and cd[key][1] is not True:
                    cd[key][1] = True
                    _xr_log("enforce: %s stripped" % key)

        # ---- install the items into the player's inventory (new game, every load, and after inventory swaps)
        def _xr_install():
            if not all(hasattr(store, n) for n in ("inventory", "main_vars", "Item", "inventory_add")):
                return
            if not isinstance(store.main_vars, _bt.dict) or "attire_list" not in store.main_vars:
                return
            for spec in _xr_items():
                item = getattr(store, spec["var"], None)
                if item is None or not isinstance(item, store.Item):
                    item = store.Item(name=spec["name"], type="Equipment", image=spec["image"])
                    setattr(store, spec["var"], item)
                    _xr_log("created %s" % spec["var"])
                # refreshed every time so mod updates reach old saves
                item.name = spec["name"]
                item.image = spec["image"]
                item.refresh_imagetext()
                item.order = spec["order"]
                item.rarity = 1
                item.cost = 0
                item.properties = list(spec["props"])
                item.equip_extra = dict(spec["extra"])
                _xr_set_stats(item, _xr_stat_dict(spec["stats"], spec["regen"]))
                item.set_desc(spec["desc"])
                if store.inventory.count(item) <= 0:
                    store.inventory_add(store.inventory, item)
                    _xr_log("added %s to inventory" % spec["var"])
            _xr_enforce()

        _xr_tick_state = {"next": 0.0}

        def _xr_tick():
            now = time.time()
            if now < _xr_tick_state["next"]:
                return
            _xr_tick_state["next"] = now + 2.0
            try:
                for var in XR_VARS:
                    item = getattr(store, var, None)
                    if item is None or store.inventory.count(item) <= 0:
                        _xr_install()
                        break
            except Exception as e:
                _xr_log("tick error %r" % (e,))

        def _xr_after_load():
            try:
                _xr_install()
            except Exception as e:
                _xr_log("install error %r" % (e,))

        if XR_REMOVER_ON:
            # ---- keep the removers' areas stripped whatever the game does
            _xr_orig_clothes_dict_set = clothes_dict_set
            _xr_orig_clothes_equip = clothes_equip
            _xr_orig_clothes_redress_item = clothes_redress_item
            _xr_orig_fix_clothes_button = fix_clothes_button

            def clothes_dict_set(area=None, level=None, pos=None, value=None):
                if pos == 1 and value is False and area is not None and level is not None:
                    if str(area) + "|" + str(level) in _xr_exposed_keys():
                        return
                return _xr_orig_clothes_dict_set(area, level, pos, value)

            def clothes_equip(equip_extra=None):
                r = _xr_orig_clothes_equip(equip_extra)
                _xr_enforce()
                return r

            def clothes_redress_item(initem=None):
                r = _xr_orig_clothes_redress_item(initem)
                _xr_enforce()
                return r

            def fix_clothes_button():
                r = _xr_orig_fix_clothes_button()
                _xr_enforce()
                return r

            _xr_orig_equip_procedure = equip_procedure

            def equip_procedure(item=None, action=None):
                r = _xr_orig_equip_procedure(item, action)
                # clicking a worn red X takes it off: put her default clothes back on right away
                if item is not None and _xr_is_remover(item) and not is_equiped(item):
                    refresh_attire_dict()
                    refresh_gui_screen()
                return r

            def fix_clothes_button_enabled():
                # same as the game's, but a remover is not "torn clothes" to fix
                if gemstone_is_garment_guardian():
                    return False
                if get_enemy_player() != e_celica:
                    return False
                held = _xr_exposed_keys()
                for key, value in clothes_dict.items():
                    if value[1] == True and key not in held and not clothes_equiparealevel_disabled(key):
                        return True
                return False

            # ---- Equip > Appearance: click a worn piece in the EQUIPPED list (left) to take it off, click again to put it back.
            # The game's own icons there do nothing (NullAction), so transparent buttons are laid over them (overlay,
            # zorder -17).  "Off" = the same 'stripped' state a monster causes; the pieces over it (the top over a bra,
            # the pants over panties) are protection, so they come off with it.  Pieces of Violet's suits and hair are left alone.
            XR_EQ_POS = (267 + 10 + 15, 38 + 60 + 15)       # the game's list: event screen (267, 38) + inner frame (10, 60) + (15, 15)
            XR_EQ_BLOCKING = ("select_item_frame", "gotitem_frame", "confirm_frame", "shopmenu_frame", "fusemenu_frame", "book_frame", "map_frame")
            XR_EQ_OWN = ("action_frame", "apex_inv_hud", "apex_equip_grid", "apex_hd_toggle", "quick_menu", "setup_frame", "apex_xr_equipped")

            def _xr_eq_blocked():
                # a window or question is open over Equip: leave the game's own list alone
                for n in XR_EQ_BLOCKING:
                    if renpy.get_screen(n) is not None:
                        return True
                try:
                    for tag in renpy.get_showing_tags("screens"):
                        if tag in XR_EQ_OWN:
                            continue
                        sd = renpy.get_screen(tag)
                        if sd is not None and getattr(sd, "modal", False) is True:
                            return True
                except Exception:
                    pass
                return False

            def _xr_eq_item_ok(item):
                return not (item.has_property("special") or item.has_property("hair_attire"))

            def _xr_eq_stripped(item):
                keys = [k for k in item.get_equip_area_list() if k in clothes_dict]
                return bool(keys) and all(clothes_dict[k][1] == True for k in keys)

            def _xr_eq_click(item):
                try:
                    if _xr_is_remover(item):
                        equip_procedure(item, "unequip")          # the wrapper above puts her default clothes back
                    elif _xr_eq_stripped(item):
                        for key in item.get_equip_area_list():
                            area, level = key.split("|")
                            clothes_dict_set(area, level, 1, False)
                    else:
                        keys = set(item.get_equip_area_list()) | set(item.get_block_area_list())
                        for key in list(keys):
                            area, level = key.split("|")
                            for other in clothes_dict.keys():
                                oarea, olevel = other.split("|")
                                if oarea == area and int(olevel) > int(level):
                                    keys.add(other)
                        for key in keys:
                            area, level = key.split("|")
                            clothes_dict_set(area, level, 1, True)
                    _xr_enforce()
                    refresh_gui_screen()
                    renpy.restart_interaction()
                except Exception as e:
                    tom_mod_error('clothing_remover', 'click-to-remove', e)

            def apex_xr_equipped_view():
                """[(item, x, y, stripped, clickable, tooltip)] while Equip > Appearance shows Celica's worn clothes, else []"""
                try:
                    if not is_setup_frame_active() or store._menu or store.main_menu:
                        return []
                    sd = renpy.get_screen("setup_frame")
                    if sd is None or tuple(getattr(sd, "screen_name", ("setup_frame",)))[0] != "setup_frame":
                        return []                       # the shop and the fuse screen use the same tag: not Equip
                    if getattr(store, "setup_frame_select", None) != "Appearance" or get_enemy_player() != e_celica:
                        return []
                    if clothes_are_empty() or _xr_eq_blocked():
                        return []
                    can = bool(is_menu_enabled() and change_clothes_btn_enabled())
                    rv = []
                    for i, item in enumerate(print_sorted_attire_list()):
                        x = XR_EQ_POS[0] + 35 * (i % 2) + 1
                        y = XR_EQ_POS[1] + 39 * (i // 2) + 1
                        ok = can and is_item_menu_enabled(item) and _xr_eq_item_ok(item)
                        st = _xr_eq_stripped(item) and not _xr_is_remover(item)
                        tip = trl(item_get_name(item)) + trl(item_get_type(item)) + "\n" + item_get_desc(item)
                        if ok:
                            tip += "\n{color=#ffd34d}" + ("Click to put it back on" if st else ("Click to take it off" if not _xr_is_remover(item) else "Click to take it off (her clothes come back)")) + "{/color}"
                        rv.append((item, x, y, st, ok, tip))
                    return rv
                except Exception as e:
                    tom_mod_error('clothing_remover', 'equipped view', e)
                    return []

            if "apex_xr_equipped" not in config.overlay_screens:
                config.overlay_screens.append("apex_xr_equipped")

        if _xr_after_load not in config.after_load_callbacks:
            config.after_load_callbacks.append(_xr_after_load)
        if _xr_tick.__name__ not in [getattr(f, "__name__", "") for f in config.periodic_callbacks]:
            config.periodic_callbacks.append(_xr_tick)


# the click-to-remove buttons over Equip > Appearance's EQUIPPED list (see apex_xr_equipped_view above)
screen apex_xr_equipped():
    zorder -17
    # a save can bring this overlay back while the mod is switched off: then draw nothing
    if hasattr(store, "apex_xr_equipped_view"):
        for _it, _x, _y, _st, _ok, _tip in apex_xr_equipped_view():
            fixed area (_x, _y, 33, 37):
                if _st:
                    add Solid("#000000a0") size (33, 37)
                    add Solid("#ff3030") size (33, 2) ypos 17
                if _ok:
                    imagebutton idle Solid("#00000000") hover Solid("#ffffff30") xysize (33, 37) action Function(_xr_eq_click, _it) tooltip _tip
