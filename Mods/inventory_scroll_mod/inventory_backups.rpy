# inventory_backups.rpy  -  Inventory Backups
#
# Each time Celica arrives somewhere new, a backup of everything she owns (items, worn accessories, gold) is kept -
# the last few places.  The small ↺ button under the inventory opens the list; "Put back" restores one, after showing
# exactly what comes back and what is removed.  Clothes and accessories she is wearing are never taken off.
# Only when the player is free to act (not in a battle or a scene).  Works with or without the Inventory Scroll Mod.

init 6 python:
    if tom_mod_ok('inventory_backups',
                  needs=['get_location', 'is_menu_enabled', 'is_battle_in_session', 'item_get_name', 'is_equiped',
                         'itemlist_dict_gui_var_refresh', 'update_inventory_frame_items', 'get_day_num', 'get_gui_vars']):
        import builtins as _is_bt

        IS_BACKUPS = tom_setting('inventory_backups', 'backups', 5)

        # ---------- inventory backups (one per new place, the last IS_BACKUPS) ----------

        def _is_snaps():
            mv = getattr(store, "main_vars", None)
            if mv is None:
                return None
            if "apex_inv_backups" not in mv:
                mv["apex_inv_backups"] = []
            return mv["apex_inv_backups"]

        def _is_place():
            loc = get_location()
            return getattr(loc, "name", None) if loc is not None else None

        def _is_worn_acc():
            # accessories she wears are kept by the game in pequip_inv, NOT in the item list
            return [i for i in pequip_inv.get_list() if i is not None]

        def _is_owned(items, worn):
            return list(items) + list(worn)

        def _is_backup_tick():
            try:
                snaps = _is_snaps()
                if snaps is None or IS_BACKUPS <= 0:
                    return
                place = _is_place()
                if place is None or main_vars.get("apex_inv_last_place") == place:
                    return
                main_vars["apex_inv_last_place"] = place
                snaps.append({"place": place, "day": int(get_day_num()), "time": "%d:%02d" % (store.day_hour, store.day_min),
                              "items": list(inventory.list), "worn": _is_worn_acc(), "coins": main_vars.get("coins", 0)})
                del snaps[:-IS_BACKUPS]
            except Exception as e:
                apex_grid_log("backup failed: %r" % (e,))

        if _is_backup_tick not in config.interact_callbacks:
            config.interact_callbacks.append(_is_backup_tick)

        def apex_inv_backup_summary(s):
            """what would change: (items back, items taken away, gold before -> after)"""
            now = _is_owned(inventory.list, _is_worn_acc())
            then = _is_owned(s["items"], s.get("worn", []))
            back, gone = [], []
            for it in _is_bt.set(then) | _is_bt.set(now):
                diff = then.count(it) - now.count(it)
                if diff > 0:
                    back.append("%s x%d" % (item_get_name(it), diff))
                elif diff < 0:
                    gone.append("%s x%d" % (item_get_name(it), -diff))
            return sorted(back), sorted(gone), main_vars.get("coins", 0), s["coins"]

        def apex_inv_safe(s):
            return str(s).replace("[", "[[").replace("{", "{{")

        def apex_inv_can_restore():
            return is_menu_enabled() and not is_battle_in_session()

        def apex_inv_restore(i):
            snaps = _is_snaps()
            if not snaps or not (0 <= i < len(snaps)) or not apex_inv_can_restore():
                return False
            s = snaps[i]
            # everything she owned then (item list + worn accessories) ...
            target = _is_owned(s["items"], s.get("worn", []))
            # ... minus the accessories she wears now: they stay worn (never unequipped, never doubled)
            for it in _is_worn_acc():
                if it in target:
                    target.remove(it)
            # clothes she is wearing right now stay with her
            for it in list(inventory.list):
                if it not in target and is_equiped(it) and getattr(it, "has_equip_area", lambda: False)():
                    target.append(it)
            inventory.list[:] = target
            main_vars["coins"] = s["coins"]
            apex_grid_log("inventory backup restored: %s, day %s %s" % (s["place"], s["day"], s["time"]))
            itemlist_dict_gui_var_refresh()
            store.update_inventory_frame_items()
            renpy.notify("Inventory put back to %s (day %s, %s)." % (s["place"], s["day"], s["time"]))
            renpy.restart_interaction()
            return True

        def apex_inv_backup_btn_visible():
            return (IS_BACKUPS > 0 and not store._menu and not store.main_menu and renpy.get_screen("action_frame") is not None
                    and get_gui_vars("frame_inventory") and not flag_list.has("enable_event_viewer")
                    and is_menu_enabled() and not apex_ui_blocked())

        if "apex_inv_backup_btn" not in config.overlay_screens:
            config.overlay_screens.append("apex_inv_backup_btn")


screen apex_inv_backup_btn():
    zorder -16
    if apex_inv_backup_btn_visible():
        # small button under the inventory
        frame area (1036, 360, 14, 14) padding 0,0 background None:
            imagebutton idle CustomBox(color=ColorMain1, xsize=14, ysize=14) hover CustomBox(color=light_color(ColorMain1), xsize=14, ysize=14) action Show("apex_inv_backups") tooltip "Inventory backups\nPut your items back to how they were at one of the last places you visited."
            text "↺" size 12 xalign 0.5 yalign 0.45 color ColorClick outlines [(absolute(0), "#000", absolute(1), absolute(1))]


screen apex_inv_backups():
    modal True
    zorder 150
    add Solid("#000000B0")
    $ _snaps = list(reversed(main_vars.get("apex_inv_backups", []))) if "main_vars" in globals() else []
    $ _n = len(_snaps)
    frame xalign 0.5 yalign 0.45 xsize 560 padding (16, 14) background Frame(CustomBox(color=ColorMain1, xsize=40, ysize=40), 8, 8):
        vbox spacing 8:
            text "Inventory backups" size 20 bold True color ColorClick outlines [(absolute(0), "#000", absolute(1), absolute(1))]
            text "A backup is made each time you arrive somewhere new (the last " + str(IS_BACKUPS) + " places). Putting one back gives you exactly the items and gold you had when you arrived there: anything you got since is removed, anything you used or sold comes back. Clothes you are wearing stay." size 12 color "#FFFFFF"
            if not apex_inv_can_restore():
                text "Only possible when you are free to act (not in a battle or a scene)." size 12 color ColorWarning
            if _n == 0:
                text "No backups yet. Go somewhere and one is made when you arrive." size 13 color "#FFFFFFB0"
            for _i, _s in enumerate(_snaps):
                $ _idx = _n - 1 - _i
                $ _back, _gone, _c0, _c1 = apex_inv_backup_summary(_s)
                frame xfill True padding (8, 6) background Solid("#00000060"):
                    hbox spacing 10:
                        vbox xsize 400 spacing 2:
                            text apex_inv_safe("%s - day %s, %s" % (_s["place"], _s["day"], _s["time"])) size 14 color "#FFFFFF"
                            if not _back and not _gone and _c0 == _c1:
                                text "Same as now." size 11 color "#FFFFFFA0"
                            else:
                                if _back:
                                    text "Comes back: " + apex_inv_safe(", ".join(_back[:8])) + (" ..." if len(_back) > 8 else "") size 11 color ColorOK
                                if _gone:
                                    text "Removed: " + apex_inv_safe(", ".join(_gone[:8])) + (" ..." if len(_gone) > 8 else "") size 11 color ColorWarning
                                if _c0 != _c1:
                                    text "Gold: %s -> %s" % (_c0, _c1) size 11 color "#FFD24A"
                        textbutton "Put back" text_size 13 text_color "#FFFFFF" text_hover_color ColorClick text_insensitive_color "#FFFFFF50" yalign 0.5 sensitive apex_inv_can_restore() action Show("apex_inv_backup_confirm", i=_idx)
            textbutton "Close" text_size 14 text_color "#FFFFFF" text_hover_color ColorClick xalign 1.0 action Hide("apex_inv_backups")
    key "game_menu" action Hide("apex_inv_backups")


screen apex_inv_backup_confirm(i):
    modal True
    zorder 160
    add Solid("#00000080")
    frame xalign 0.5 yalign 0.5 xsize 420 padding (16, 14) background Frame(CustomBox(color=ColorMain1, xsize=40, ysize=40), 8, 8):
        vbox spacing 10:
            text "Put this backup back?" size 18 bold True color ColorClick
            text "Your items and gold change to what they were then. This can't be undone (but a save made before keeps working)." size 12 color "#FFFFFF"
            hbox spacing 20 xalign 0.5:
                textbutton "Yes, put it back" text_size 14 text_color "#FFFFFF" text_hover_color ColorClick action [Function(apex_inv_restore, i), Hide("apex_inv_backup_confirm"), Hide("apex_inv_backups")]
                textbutton "No" text_size 14 text_color "#FFFFFF" text_hover_color ColorClick action Hide("apex_inv_backup_confirm")
