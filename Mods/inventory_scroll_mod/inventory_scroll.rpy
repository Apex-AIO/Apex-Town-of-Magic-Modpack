# inventory_scroll.rpy  -  Inventory Scroll Mod (+ sub-mod "Movable Inventory Items")
#
# The ITEMS and SPELLS grid on the right of the screen scrolls with the mouse wheel instead of paging with arrows,
# grows a row whenever it is nearly full (7 of 9 squares, 10 of 12, ...), and - with Movable Inventory Items on -
# items can be dragged onto another square to swap places.
#
# How: the game builds the grid 9 items at a time (update_inventory_frame_items).  This mod lets the game build
# every page, keeps the game's own square for each item (picture, numbers, tooltip, what a click does), then draws
# them in a scrolling grid of its own on top of the game's (whose squares are left empty).
#
# Item safety: see apex_grid.rpy - the mod only remembers where each item is DRAWN.  On top of that it keeps an
# inventory backup each time Celica arrives somewhere new (the last 5 places); "Inventory backups" (the small button
# under the scroll bar) can put the items and gold back to one of them.

init 6 python:
    if tom_mod_ok('inventory_scroll',
                  hooks=['update_inventory_frame_items'],
                  needs=['itemlist_dict_gui_var_printlist', 'itemlist_dict_gui_var_refresh', 'enemy_print_sorted_moves',
                         'get_playable_enemy', 'get_move_field', 'is_menu_enabled', 'get_gui_vars',
                         'spellnum_to_keysym', 'get_button_keysymlist', 'get_location', 'is_battle_in_session',
                         'item_get_image', 'item_get_name', 'is_equiped',
                         'print_battle_event_move_list', 'get_day_num']):
        import builtins as _is_bt

        IS_MOVABLE = tom_setting('inventory_scroll', 'movable', True)
        IS_BACKUPS = tom_setting('inventory_scroll', 'backups', 5)

        APEX_INV_VIEW = _is_bt.dict(tab=None, grid=None, keys=[], entries={}, icon_color="#808080", objs=[])
        _IS_PAGE = _is_bt.dict(item=0, ability=0)        # the game's page numbers we last saw (to follow the game)

        _is_orig_update = update_inventory_frame_items

        def _is_vanilla(tab):
            """True when this mod leaves the grid to the game (another tab, a battle event list...)"""
            if tab not in ("ITEMS", "SPELLS"):
                return True
            if tab == "SPELLS" and flag_list.has("enable_playable_battleevents") and len(print_battle_event_move_list()):
                return True
            return False

        def update_inventory_frame_items():
            tab = store.inventory_tab_selected_name
            if _is_vanilla(tab):
                APEX_INV_VIEW["tab"] = None
                return _is_orig_update()
            want_item, want_ability = store.item_page, store.ability_page
            rows = []
            try:
                store.item_page = 0
                store.ability_page = 0
                _is_orig_update()
                total = store.inventory_frame_item_dict.get("count_total", 0)
                rows.extend(store.inventory_frame_item_list)
                for p in range(1, (total + 8) // 9):
                    if tab == "ITEMS":
                        store.item_page = p
                    else:
                        store.ability_page = p
                    _is_orig_update()
                    rows.extend(store.inventory_frame_item_list)
            finally:
                store.item_page, store.ability_page = want_item, want_ability
            # the game's own list of what those squares are, in the same order
            if not rows:
                objs, names = [], []
            elif tab == "ITEMS":
                objs = itemlist_dict_gui_var_printlist()
                names = [getattr(o, "name", o) for o in objs]
            else:
                pe = get_playable_enemy()
                objs = list(enemy_print_sorted_moves(pe))
                names = [get_move_field(m, "id", pe) or get_move_field(m, "name", pe) for m in objs]
            if len(objs) != len(rows):
                # something unexpected: show the game's own grid, untouched
                apex_grid_log("inventory: %d squares but %d items - game grid used" % (len(rows), len(objs)))
                APEX_INV_VIEW["tab"] = None
                return _is_orig_update()
            keys = apex_grid_keys(names)
            grid = "items" if tab == "ITEMS" else "spells:%s" % getattr(get_playable_enemy(), "name", "?")
            APEX_INV_VIEW.update(tab=tab, grid=grid, keys=keys, entries=_is_bt.dict(zip(keys, rows)), objs=objs,
                                 icon_color=store.inventory_frame_item_dict.get("icon_color", "#808080"))
            # the game asked for a page (a tutorial pointing at a spell): scroll there
            page = want_item if tab == "ITEMS" else want_ability
            last = "item" if tab == "ITEMS" else "ability"
            if page != _IS_PAGE[last]:
                _IS_PAGE[last] = page
                if 0 < page * 9 < len(keys):
                    APEX_INV_VIEW["show"] = keys[page * 9]
            # the game's squares stay empty; ours are drawn on top
            store.inventory_frame_item_list = []
            store.inventory_frame_item_dict["count_total"] = 0
            store.inventory_frame_item_dict["count_page"] = 0
            return

        def apex_inv_hud_visible():
            v = APEX_INV_VIEW
            return (v["tab"] is not None and v["tab"] == store.inventory_tab_selected_name and not store._menu
                    and not store.main_menu and renpy.get_screen("action_frame") is not None
                    and get_gui_vars("frame_inventory") and not flag_list.has("enable_event_viewer"))

        def apex_inv_slots():
            v = APEX_INV_VIEW
            slots = apex_grid_slots(v["grid"], v["keys"])
            if v.get("show"):
                apex_grid_show_key(v["grid"], slots, v.pop("show"))
            return slots

        def apex_inv_on_move(a, b):
            v = APEX_INV_VIEW
            apex_grid_move(v["grid"], v["keys"], a, b)

        def apex_inv_can_move():
            return IS_MOVABLE and is_menu_enabled()

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
            update_inventory_frame_items()
            renpy.notify("Inventory put back to %s (day %s, %s)." % (s["place"], s["day"], s["time"]))
            renpy.restart_interaction()
            return True

        def _is_after_load():
            APEX_INV_VIEW["tab"] = None
            try:
                update_inventory_frame_items()
            except Exception as e:
                apex_grid_log("after load: %r" % (e,))

        if _is_after_load not in config.after_load_callbacks:
            config.after_load_callbacks.append(_is_after_load)

        if "apex_inv_hud" not in config.overlay_screens:
            config.overlay_screens.append("apex_inv_hud")


screen apex_inv_hud():
    zorder -17
    if apex_inv_hud_visible():
        $ _v = APEX_INV_VIEW
        $ _slots = apex_inv_slots()
        $ _blocked = apex_ui_blocked()
        use apex_grid_view(_v["grid"], 830, 148, _slots, _v["entries"], _v["icon_color"], apex_inv_can_move(), _blocked, apex_inv_on_move, keys=True)
        if IS_BACKUPS > 0 and not _blocked and is_menu_enabled():
            # Inventory backups: small button under the scroll bar
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
