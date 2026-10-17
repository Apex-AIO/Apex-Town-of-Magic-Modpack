# equip_scroll.rpy  -  Appearance/Accessories Scroll Mod (+ sub-mod "Movable Equip Clothing/Accessories Mod")
#
# In Equip, the Accessories and Appearance grids scroll with the mouse wheel instead of paging with arrows, grow a
# row whenever they are nearly full, and - with the sub-mod on - pieces can be dragged onto another square to swap
# places.  Only squares of the same grid accept a drop: nothing can be dragged onto the worn/equipped slots.
#
# How: the game draws its own grid only when there is equipment to show (equipment_are_empty).  While Equip shows
# Accessories or Appearance this mod answers "empty" for that one question, so the game draws its empty grid, and
# draws the same squares (same pictures, outlines, tooltips and click actions as the game's) in a scrolling grid on
# top.  Item safety: see apex_grid.rpy.

init 6 python:
    if tom_mod_ok('equip_scroll',
                  hooks=['equipment_are_empty'],
                  needs=['is_setup_frame_active', 'is_menu_enabled', 'is_equiped', 'equip_procedure',
                         'specialclothes_enable_suit_by_item', 'refresh_gui_screen', 'change_clothes_btn_enabled',
                         'is_item_menu_enabled', 'is_item_menu_enabled_alpha', 'get_item_shadowimage', 'item_get_image',
                         'item_get_name', 'item_get_type', 'item_get_desc', 'outfitset_action_get', 'trl',
                         'dark_color', 'spellnum_to_keysym', 'get_button_keysymlist']):
        import builtins as _es_bt

        ES_MOVABLE = tom_setting('equip_scroll', 'movable', True)
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
            return ES_MOVABLE and is_menu_enabled()

        if "apex_equip_grid" not in config.overlay_screens:
            config.overlay_screens.append("apex_equip_grid")


screen apex_equip_grid():
    zorder -17
    $ _v = apex_equip_view()
    if _v is not None:
        $ _slots = apex_grid_slots(_v["grid"], _v["keys"])
        $ _blocked = apex_ui_blocked(allow=("setup_frame",))
        use apex_grid_view(_v["grid"], ES_POS[0], ES_POS[1], _slots, _v["entries"], _v["icon_color"], apex_equip_can_move(), _blocked, apex_equip_on_move, keys=True)
