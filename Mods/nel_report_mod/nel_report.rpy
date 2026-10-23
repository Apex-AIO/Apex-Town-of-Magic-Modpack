# nel_report.rpy  -  Nel's Battle Report
#
# While Nel possesses Celica and auto-battles, everything she does is recorded: monsters she defeated, items and gold
# she collected, battle XP and skill XP (SP), how many times she invited the monsters (Nel's Auto Battler taunts),
# her climaxes, how many battles and how long it all took.  When Nel leaves Celica's body ("Bye…!") and control comes
# back to the player, a report sheet shows it all; items are ordered rarest first, with a border per rarity.
#
# Hooks (the game's own functions, wrapped; nothing is changed in what they do):
#   add_to_reward_dict(enemy)      the game calls it once for every defeated monster -> the kill
#   battle_ally_get_win_reward()   pays the rewards at the end of a won battle -> the same amounts, recorded
#   label remove_possession        Nel leaves -> the report opens when that scene hands control back
# The record lives in the save (main_vars["apex_nel_report"]), so it survives saving and loading mid-possession.

init 8 python:
    if tom_mod_ok('nel_report',
                  hooks=['add_to_reward_dict', 'battle_ally_get_win_reward', 'inventory_add'],
                  needs=['enemy_has_status', 'get_enemy_player', 'dampen_reward_xp', 'dampen_reward_sp',
                         'battle_get_average_enemy_lvl', 'xpmulti_get', 'spmulti_get', 'item_get_image', 'item_get_name',
                         'get_day_num', 'trl']):
        import builtins as _nr_bt, time as _nr_time

        def _nr_active():
            try:
                if enemy_has_status(e_celica, s_possessionnel):
                    return True
                f = getattr(store, "apex_auto_active", None)      # Celica's Smart Auto Battle
                return bool(f is not None and f())
            except Exception:
                return False

        def _nr_rec(start=True):
            mv = getattr(store, "main_vars", None)
            if mv is None:
                return None
            r = mv.get("apex_nel_report")
            if r is None and start:
                r = mv["apex_nel_report"] = {"kills": [], "items": {}, "xp": 0, "xp_bonus": 0, "sp": 0, "sp_bonus": 0,
                                             "coins": 0, "taunts": 0, "climaxes": 0, "battles": 0,
                                             "start_game": _nr_minutes(), "start_real": _nr_time.time(), "real": 0.0}
            return r

        def _nr_minutes():
            try:
                return int(get_day_num()) * 1440 + int(store.day_hour) * 60 + int(store.day_min)
            except Exception:
                return 0

        def _nr_enemy_pic(e):
            """a picture of the monster for the report: its first frame (the files are <name>-W-H-FRAMES.png)"""
            try:
                return apex_nr_enemy_pic(e)
            except Exception as ex:
                tom_mod_error("nel_report", "finding a monster's picture", ex)
                return None

        # ---- kills
        _nr_orig_add_to_reward_dict = add_to_reward_dict

        def add_to_reward_dict(enemytarget=None):
            if enemytarget is not None and _nr_active():
                try:
                    r = _nr_rec()
                    if r is not None:
                        name = str(getattr(enemytarget, "name", "?"))
                        for k in r["kills"]:
                            if k["name"] == name:
                                k["n"] += 1
                                break
                        else:
                            r["kills"].append({"name": name, "n": 1, "pic": _nr_enemy_pic(enemytarget)})
                except Exception as ex:
                    tom_mod_error("nel_report", "recording a defeated monster", ex)
            return _nr_orig_add_to_reward_dict(enemytarget)

        # ---- rewards (the same sums the game pays to Celica)
        _nr_orig_win_reward = battle_ally_get_win_reward

        def battle_ally_get_win_reward(in_dictionary, in_bonus_dictionary):
            if _nr_active():
                try:
                    r = _nr_rec()
                    lvl = battle_get_average_enemy_lvl()
                    r["battles"] += 1
                    for key, value in list(in_dictionary.items()):
                        if key is i_xp:
                            v = int(round(dampen_reward_xp(lvl, e_celica, value)))
                            b = int(v * (0.1 * xpmulti_get())) if key in in_bonus_dictionary else 0
                            r["xp"] += v
                            r["xp_bonus"] += b
                        elif key is i_sp:
                            v = int(round(dampen_reward_sp(lvl, e_celica, value)))
                            b = int(v * (0.1 * spmulti_get())) if key in in_bonus_dictionary else 0
                            r["sp"] += v
                            r["sp_bonus"] += b
                except Exception as ex:
                    tom_mod_error("nel_report", "recording battle rewards", ex)
            return _nr_orig_win_reward(in_dictionary, in_bonus_dictionary)

        # ---- items and gold: everything the game gives goes through inventory_add (battle drops, chests, finds,
        # rewards); moving a piece back from Equip (equip_inventory.rpy) is not loot
        _nr_orig_inventory_add = inventory_add

        def inventory_add(in_inventory=None, in_item=None, in_total=1):
            if in_item is not None and in_inventory is not None and _nr_active() and not getattr(store, "APEX_NR_IGNORE", False):
                try:
                    import sys as _nr_sys
                    caller = _nr_sys._getframe(1).f_code.co_filename.replace("\\", "/")
                    if in_inventory is store.inventory and "equip_inventory" not in caller:
                        r = _nr_rec()
                        n = abs(int(in_total or 0))
                        name = in_item.get_name() if hasattr(in_item, "get_name") else ""
                        if name == store.money:
                            r["coins"] += n
                        elif name in (store.xp_name, store.sp_name, store.attribute_points_name) or in_item.get_type() == "Wallet":
                            pass
                        elif n > 0:
                            r["items"][in_item] = r["items"].get(in_item, 0) + n
                except Exception as ex:
                    tom_mod_error("nel_report", "recording an item", ex)
            return _nr_orig_inventory_add(in_inventory, in_item, in_total)

        # ---- taunts and climaxes: Nel's Auto Battler calls this (nel_taunt.rpy _nt_report)
        def apex_nr_event(event):
            try:
                if _nr_active():
                    r = _nr_rec()
                    if event == "taunt":
                        r["taunts"] += 1
                    elif event == "climax":
                        r["climaxes"] += 1
            except Exception as ex:
                tom_mod_error("nel_report", "counting a " + str(event), ex)

        # ---- start / end of a possession
        _NR = {"pending": False}

        def _nr_tick():
            try:
                mv = getattr(store, "main_vars", None)
                if mv is None:
                    return
                if _nr_active():
                    _nr_rec()                       # starts the record when Nel takes over
                elif not _NR["pending"] and mv.get("apex_nel_report") is not None and renpy.get_screen("apex_nel_report") is None:
                    if not mv["apex_nel_report"].get("closing"):
                        mv["apex_nel_report"] = None    # she left some other way (an event): nothing to report
            except Exception as ex:
                tom_mod_error("nel_report", "watching the possession", ex)

        if _nr_tick not in config.interact_callbacks:
            config.interact_callbacks.append(_nr_tick)

        def _nr_label(name, abnormal):
            try:
                if name == "remove_possession":
                    r = _nr_rec(start=False)
                    if r is not None:
                        r["closing"] = True
                        r["end_game"] = _nr_minutes()
                        r["real"] = _nr_time.time() - r.get("start_real", _nr_time.time())
                        _NR["pending"] = True
                elif name == "enable_menu" and _NR["pending"]:
                    # the possession scene hands control back: show the sheet
                    _NR["pending"] = False
                    renpy.show_screen("apex_nel_report")
            except Exception as ex:
                tom_mod_error("nel_report", "opening the report", ex)

        if _nr_label not in config.label_callbacks:
            config.label_callbacks.append(_nr_label)

        def _nr_after_load():
            _NR["pending"] = False

        if _nr_after_load not in config.after_load_callbacks:
            config.after_load_callbacks.append(_nr_after_load)

        def apex_nr_finish_auto(min_seconds=20):
            """Celica's Smart Auto Battle ended: open the report when there is something to report
            (and the mode ran for at least min_seconds of real time: a short run shows nothing)"""
            r = _nr_rec(start=False)
            if r is None:
                return
            short = _nr_time.time() - r.get("start_real", _nr_time.time()) < min_seconds
            if short or not (r.get("battles") or r.get("kills") or r.get("items") or r.get("coins")):
                store.main_vars["apex_nel_report"] = None
                return
            r["closing"] = True
            r["src"] = "auto"
            r["end_game"] = _nr_minutes()
            r["real"] = _nr_time.time() - r.get("start_real", _nr_time.time())
            renpy.show_screen("apex_nel_report")

        # ---- what the sheet shows
        APEX_RARITY = [(9, "LEGENDARY", "#ffcc33"), (7, "EPIC", "#c46bff"), (5, "RARE", "#4da3ff"), (3, "UNCOMMON", "#46d36b"),
                       (0, "COMMON", "#b8b0c8")]

        def apex_rarity(item):
            try:
                r = int(item.get_rarity() or 0)
            except Exception:
                r = 0
            for lo, name, col in APEX_RARITY:
                if r >= lo:
                    return r, name, col
            return 0, "COMMON", "#b8b0c8"

        def apex_nr_view():
            r = _nr_rec(start=False) or {}
            items = sorted(r.get("items", {}).items(), key=lambda kv: (-apex_rarity(kv[0])[0], str(getattr(kv[0], "name", ""))))
            mins = max(0, r.get("end_game", _nr_minutes()) - r.get("start_game", _nr_minutes()))
            secs = int(r.get("real", 0))
            return dict(kills=r.get("kills", []), items=items, xp=r.get("xp", 0) + r.get("xp_bonus", 0),
                        xp_base=r.get("xp", 0), xp_bonus=r.get("xp_bonus", 0), sp=r.get("sp", 0) + r.get("sp_bonus", 0),
                        coins=r.get("coins", 0), taunts=r.get("taunts", 0), climaxes=r.get("climaxes", 0),
                        battles=r.get("battles", 0), auto=(r.get("src") == "auto"), game="%dh %02dm" % (mins // 60, mins % 60),
                        real="%dm %02ds" % (secs // 60, secs % 60), killed=sum(k["n"] for k in r.get("kills", [])))

        def apex_nr_close():
            mv = getattr(store, "main_vars", None)
            if mv is not None:
                mv["apex_nel_report"] = None
            renpy.hide_screen("apex_nel_report")
            renpy.restart_interaction()

        def apex_nr_safe(s):
            return str(s).replace("[", "[[").replace("{", "{{")


init 9 python:
    import os as _nr_os
    _NR_FILES = {}

    def apex_nr_enemy_pic(e):
        """the monster's first animation frame: images/CHAR/<image>/<image>-W-H-N.png (its idle sheet)"""
        img = str(getattr(e, "image", "") or "")
        if not img:
            return None
        if not _NR_FILES:
            for f in renpy.list_files():
                if f.startswith("images/CHAR/") and f.endswith(".png") and "@" not in f:
                    _NR_FILES.setdefault(f.split("/")[2], []).append(f)
        import re as _re
        cands = []
        for f in _NR_FILES.get(img, []):
            m = _re.match(r"images/CHAR/[^/]+/(.+)-(\d+)-(\d+)-(\d+)\.png$", f)
            if m:
                cands.append((m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), f))
        # the plain sheet first (a monster's own body), else its idle pose, else any sheet of it
        for test in (lambda c: c[0] == img, lambda c: c[0].startswith(img + "_idle"), lambda c: True):
            for c in sorted(cands, key=lambda c: len(c[0])):
                if test(c):
                    return _nr_trim(c[4], c[1], c[2])
        return None

    def _nr_trim(f, w, h):
        """(file, x, y, w, h): the first frame cut down to the visible monster (frames are mostly empty space)"""
        x, y, bw, bh = 0, 0, w, h
        try:
            s = renpy.display.im.load_surface(f).subsurface((0, 0, w, h))
            r = s.get_bounding_rect(min_alpha=8)
            if r.width > 4 and r.height > 4:
                pad = 6
                x, y = max(0, r.x - pad), max(0, r.y - pad)
                bw, bh = min(w - x, r.width + 2 * pad), min(h - y, r.height + 2 * pad)
        except Exception as ex:
            tom_mod_error("nel_report", "cropping a monster picture", ex)
        return (f, x, y, bw, bh)


screen apex_nr_item_tile(item, qty):
    $ _r, _rn, _rc = apex_rarity(item)
    fixed:
        xsize 74 ysize 92
        # rarity frame: coloured border + glow; epic and legendary pulse
        if _r >= 7:
            add Solid(_rc) xsize 72 ysize 82 xpos 1 at apex_nr_pulse
        add Solid(_rc) xsize 70 ysize 80 xpos 2 ypos 1 alpha 0.85
        add Solid("#160d1c") xsize 66 ysize 76 xpos 4 ypos 3
        add Solid(_rc) xsize 66 ysize 76 xpos 4 ypos 3 alpha 0.12
        if _r >= 9:
            add Solid("#ffffff") xsize 10 ysize 76 xpos 4 ypos 3 at apex_nr_shine
        add item_get_image(item) xpos 4 ypos 3
        if qty > 1:
            text "x%d" % qty size 12 bold True color "#ffffff" outlines [(absolute(1), "#000", 0, 0)] xpos 66 ypos 64 xanchor 1.0
        text _rn size 8 bold True color _rc xalign 0.5 ypos 82 outlines [(absolute(1), "#000", 0, 0)]


transform apex_nr_pulse:
    alpha 0.25
    linear 0.9 alpha 0.75
    linear 0.9 alpha 0.25
    repeat

transform apex_nr_shine:
    alpha 0.0 xoffset 0
    pause 1.2
    alpha 0.35
    linear 0.5 xoffset 56 alpha 0.0
    repeat

transform apex_nr_in:
    alpha 0.0 yoffset 20
    easein 0.35 alpha 1.0 yoffset 0


screen apex_nel_report():
    modal True
    zorder 120
    # shown screens are saved: with the mod switched off, a loaded save must not crash here
    $ _v = apex_nr_view() if hasattr(store, "apex_nr_view") else None
    if _v is not None:
        add Solid("#000000B8")
        frame at apex_nr_in:
            xalign 0.5 yalign 0.5 xsize 760 padding (20, 16)
            background Frame(CustomBox(color=ColorMain1, xsize=40, ysize=40), 8, 8)
            vbox spacing 10:
                hbox xfill True:
                    vbox:
                        text ("AUTO BATTLE REPORT" if _v["auto"] else "NEL'S BATTLE REPORT") size 22 bold True color "#7ef0e0" outlines [(absolute(1), "#000", absolute(1), absolute(1))]
                        text ("While Celica's Smart Auto Battle was on" if _v["auto"] else "While Nel had Celica's body") size 11 color "#FFFFFFA0"
                    vbox xalign 1.0:
                        text "%s in game  ·  %s real time" % (_v["game"], _v["real"]) size 12 color "#FFFFFF" xalign 1.0
                        text "%d battle%s won" % (_v["battles"], "" if _v["battles"] == 1 else "s") size 11 color "#FFFFFFA0" xalign 1.0
                # monsters
                frame xfill True padding (10, 8) background Solid("#00000055"):
                    vbox spacing 6:
                        text "MONSTERS DEFEATED  (%d)" % _v["killed"] size 12 bold True color ColorClick
                        if not _v["kills"]:
                            text "None this time." size 12 color "#FFFFFFA0"
                        else:
                            viewport:
                              xfill True ymaximum 200 child_size (700, None) mousewheel True draggable True
                              hbox spacing 8 box_wrap True:
                                  for _k in _v["kills"]:
                                      frame padding (4, 4) background Solid("#ffffff10"):
                                          vbox spacing 2 xsize 76:
                                              if _k.get("pic"):
                                                  add Transform(Crop(tuple(_k["pic"][1:5]) if len(_k["pic"]) == 5 else (0, 0, _k["pic"][1], _k["pic"][2]), _k["pic"][0]), fit="contain", xysize=(76, 62)) xalign 0.5
                                              else:
                                                  null height 62
                                              text apex_nr_safe(_k["name"]) size 10 color "#FFFFFF" xalign 0.5 text_align 0.5
                                              text "x%d" % _k["n"] size 11 bold True color ColorClick xalign 0.5
                # totals
                hbox spacing 10:
                    frame xsize 360 padding (10, 8) background Solid("#00000055"):
                        vbox spacing 3:
                            text "EXPERIENCE" size 12 bold True color ColorClick
                            text "Battle XP  %d" % _v["xp_base"] + ("  +%d bonus" % _v["xp_bonus"] if _v["xp_bonus"] else "") size 13 color "#FFFFFF"
                            text "Skill XP (SP)  %d" % _v["sp"] size 13 color "#ff8fd0"
                            text "= %d XP" % (_v["xp"] + _v["sp"]) size 16 bold True color "#FFFFFF"
                    frame xsize 350 padding (10, 8) background Solid("#00000055"):
                        vbox spacing 3:
                            text "GOLD & MORE" size 12 bold True color ColorClick
                            hbox spacing 6:
                                add "GUI/coin.png" yalign 0.5
                                text "%d gold" % _v["coins"] size 15 bold True color "#ffd24a" yalign 0.5
                            if not _v["auto"]:
                                text "Invited the monsters  %d time%s" % (_v["taunts"], "" if _v["taunts"] == 1 else "s") size 13 color "#ff8fd0"
                                text "Climaxes  %d" % _v["climaxes"] size 13 color "#ff8fd0"
                # items: rarest first, left to right
                frame xfill True padding (10, 8) background Solid("#00000055"):
                    vbox spacing 6:
                        text "ITEMS COLLECTED" size 12 bold True color ColorClick
                        if not _v["items"]:
                            text "No items this time." size 12 color "#FFFFFFA0"
                        else:
                            viewport:
                                xfill True ysize 96
                                mousewheel "horizontal" draggable True
                                hbox spacing 6:
                                    for _it, _q in _v["items"]:
                                        button:
                                            padding (0, 0) background None action NullAction()
                                            tooltip apex_nr_safe(trl(item_get_name(_it)))
                                            use apex_nr_item_tile(_it, _q)
                textbutton "OK" xalign 1.0 text_size 16 text_bold True text_color "#FFFFFF" text_hover_color ColorClick padding (24, 6) background CustomBox(color=dark_color(ColorClick), xsize=90, ysize=32) action Function(apex_nr_close)
        key "game_menu" action Function(apex_nr_close)
        key "K_RETURN" action Function(apex_nr_close)
