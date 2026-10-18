# inventory_scroll.rpy  -  Inventory Scroll Mod
#
# Every item grid scrolls with the mouse wheel instead of paging with arrows, and grows a row whenever it is nearly
# full (7 of 9 squares, 10 of 12, ...): ITEMS and SPELLS on the right of the screen, and Appearance and Accessories
# in Equip.  Dragging items to rearrange them is its own mod (Movable Inventory Items, inventory_move.rpy).
#
# How (ITEMS/SPELLS): the game builds the grid 9 items at a time (update_inventory_frame_items).  This mod lets the
# game build every page, keeps the game's own square for each item (picture, numbers, tooltip, what a click does),
# then draws them in a scrolling grid of its own on top of the game's (whose squares are left empty).
# How (Equip): the game draws its own grid only when there is equipment to show (equipment_are_empty).  While Equip
# shows Accessories or Appearance this mod answers "empty" for that one question, so the game draws its empty grid,
# and draws the same squares (pictures, outlines, tooltips, click actions) in a scrolling grid on top.
# Item safety: see apex_grid.rpy - only WHERE each item is drawn is remembered.

init 6 python:
    if tom_mod_ok('inventory_scroll',
                  hooks=['update_inventory_frame_items', 'equipment_are_empty'],
                  needs=['itemlist_dict_gui_var_printlist', 'itemlist_dict_gui_var_refresh', 'enemy_print_sorted_moves',
                         'get_playable_enemy', 'get_move_field', 'is_menu_enabled', 'get_gui_vars',
                         'spellnum_to_keysym', 'get_button_keysymlist', 'get_location', 'is_battle_in_session',
                         'item_get_image', 'item_get_name', 'is_equiped',
                         'print_battle_event_move_list', 'is_setup_frame_active', 'equip_procedure',
                         'specialclothes_enable_suit_by_item', 'refresh_gui_screen', 'change_clothes_btn_enabled',
                         'is_item_menu_enabled', 'is_item_menu_enabled_alpha', 'get_item_shadowimage', 'item_get_type',
                         'item_get_desc', 'outfitset_action_get', 'trl', 'dark_color']):
        import builtins as _is_bt

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
            return APEX_GRID_MOVABLE and is_menu_enabled()

        def _is_after_load():
            APEX_INV_VIEW["tab"] = None
            try:
                update_inventory_frame_items()
            except Exception as e:
                apex_grid_log("after load: %r" % (e,))

        if _is_after_load not in config.after_load_callbacks:
            config.after_load_callbacks.append(_is_after_load)

        # ---------- Equip: Appearance and Accessories ----------
        import builtins as _es_bt

        _es_orig_empty = equipment_are_empty
        APEX_EQUIP_VIEW = _es_bt.dict(kind=None, grid=None, keys=[], entries={}, icon_color="#808080")

        # Equip's grid, from the game's setup_frame: event screen (267, 38) + inner frame (10, 60) + (532 - 240, 15)
        ES_POS = (267 + 10 + 532 - 240, 38 + 60 + 15)

        def _es_kind():
            """'acc' / 'app' while Equip shows a grid this mod handles, else None"""
            if not is_setup_frame_active() or store._menu or store.main_menu:
                return None
            sel = getattr(store, "setup_frame_select", None)
            if sel in ("EQUIPMENT", "Accessories"):
                return "acc"
            if sel == "Appearance":
                if outfitset_action_get("selected_action") is not None:
                    return None                    # the outfit save/load list is shown there instead
                return "app"
            return None

        def equipment_are_empty():
            real = _es_orig_empty()
            if not real and _es_kind() is not None:
                return True                        # the game's grid stays empty; ours is drawn on top
            return real

        def _es_entry(item, kind):
            e = _es_bt.dict(img=item_get_image(item), shadow_img=get_item_shadowimage(item), alpha=is_item_menu_enabled_alpha(item),
                            grayscale=False, bar=False, bar_color="", bar_perc=0.0, cooldown_perc=0.0,
                            count_total=inventory.count(item))
            if kind == "acc":
                e.update(sensitive=is_menu_enabled(), action=[Function(equip_procedure, item, "equip"), Function(renpy.restart_interaction)],
                         tooltiptext=trl(item_get_name(item)) + "\n" + item_get_desc(item), outline=False, outline_color="")
            else:
                if item.has_property("special"):
                    act = [Function(specialclothes_enable_suit_by_item, item), Function(refresh_gui_screen), Function(renpy.restart_interaction)]
                else:
                    act = [Function(equip_procedure, item, "equip"), Function(refresh_gui_screen), Function(renpy.restart_interaction)]
                if getattr(store, "current_event_scene", None) == "test_images":
                    sens = True
                else:
                    sens = is_menu_enabled() and is_item_menu_enabled(item) and change_clothes_btn_enabled()
                e.update(sensitive=sens, action=act, outline=is_equiped(item), outline_color=ColorClick,
                         tooltiptext=trl(item_get_name(item)) + trl(item_get_type(item)) + "\n" + item_get_desc(item))
            return e

        def apex_equip_view():
            """build the squares for the grid Equip is showing (None when this mod draws nothing)"""
            kind = _es_kind()
            if kind is None:
                return None
            if _es_orig_empty():
                items = []
            elif kind == "acc":
                items = inventory.print_sorted_unique_accessory_only_list()
            else:
                items = inventory.print_sorted_unique_appearance_only_list()
            keys = apex_grid_keys([getattr(i, "name", i) for i in items])
            color = dark_color(ColorMain1) if kind == "acc" else dark_color(ColorMain2b)
            APEX_EQUIP_VIEW.update(kind=kind, grid="equip:" + kind, keys=keys, icon_color=color,
                                   entries=_es_bt.dict((k, _es_entry(i, kind)) for k, i in zip(keys, items)))
            return APEX_EQUIP_VIEW

        def apex_equip_on_move(a, b):
            v = APEX_EQUIP_VIEW
            apex_grid_move(v["grid"], v["keys"], a, b)

        def apex_equip_can_move():
            return APEX_GRID_MOVABLE and is_menu_enabled()

        if "apex_equip_grid" not in config.overlay_screens:
            config.overlay_screens.append("apex_equip_grid")

        if "apex_inv_hud" not in config.overlay_screens:
            config.overlay_screens.append("apex_inv_hud")


screen apex_inv_hud():
    zorder -17
    if apex_inv_hud_visible():
        $ _v = APEX_INV_VIEW
        $ _slots = apex_inv_slots()
        $ _blocked = apex_ui_blocked()
        use apex_grid_view(_v["grid"], 830, 148, _slots, _v["entries"], _v["icon_color"], apex_inv_can_move(), _blocked, apex_inv_on_move, keys=True)


screen apex_equip_grid():
    zorder -17
    $ _v = apex_equip_view()
    if _v is not None:
        $ _slots = apex_grid_slots(_v["grid"], _v["keys"])
        $ _blocked = apex_ui_blocked(allow=("setup_frame",))
        use apex_grid_view(_v["grid"], ES_POS[0], ES_POS[1], _slots, _v["entries"], _v["icon_color"], apex_equip_can_move(), _blocked, apex_equip_on_move, keys=True)
