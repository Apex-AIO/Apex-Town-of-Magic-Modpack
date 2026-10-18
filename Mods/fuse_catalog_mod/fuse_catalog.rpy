# fuse_catalog.rpy  -  Morden's Lab Craftable Catalog
#
# In Morden's Lab fuse screen, a CATALOG button sits between the two glass capsules.  It lists only the upgrades the
# player can make RIGHT NOW (both ingredients owned and usable); clicking one puts its two items in Item 1 and Item 2,
# then FUSE crafts it as usual.  Nothing else changes: the game's own FUSE does the fusing.
#
# Always exact, also after game updates: the recipes come from the game's own list (print_fusion_recipe_list) and
# "usable" from the game's own rule (print_inventory_and_equip_unique_list_for_fusion: items in the inventory, worn
# accessories, the wallet, clothes - but not items whose skill isn't mastered yet), read every time it opens.

init 6 python:
    if tom_mod_ok('fuse_catalog',
                  needs=['print_fusion_recipe_list', 'print_inventory_and_equip_unique_list_for_fusion',
                         'fusion_clear_button_items', 'is_fuse_menu_active', 'is_menu_enabled', 'item_get_image',
                         'item_get_name', 'item_get_desc', 'trl', 'is_equiped']):
        import builtins as _fc_bt

        def apex_fuse_craftable():
            """[(item 1, item 2, result)] the player can fuse now, in the game's own recipe order"""
            out = []
            try:
                usable = list(print_inventory_and_equip_unique_list_for_fusion())
                for r in print_fusion_recipe_list():
                    a, b, res = r[0], r[1], r[2]
                    if a is not None and b is not None and a is not b and a in usable and b in usable:
                        out.append((a, b, res))
            except Exception as e:
                tom_mod_error("fuse_catalog", "listing recipes", e)
            return out

        def apex_fuse_pick(a, b):
            try:
                gui_vars["fuse_item_1"] = a
                gui_vars["fuse_item_2"] = b
                gui_vars["fuse_result"] = None
            except Exception as e:
                tom_mod_error("fuse_catalog", "putting the items in", e)
            renpy.hide_screen("apex_fuse_catalog_list")
            renpy.restart_interaction()

        def apex_fuse_btn_visible():
            return (is_fuse_menu_active() and is_menu_enabled() and not store._menu and not store.main_menu
                    and renpy.get_screen("select_item_frame") is None and renpy.get_screen("confirm_frame") is None)

        def apex_fuse_where(i):
            """where the player finds an ingredient (accessories and clothes aren't in the ITEMS grid)"""
            try:
                if is_equiped(i):
                    return " (worn)"
                if i.has_property("equipable"):
                    return " (Equip > Appearance)" if i.has_equip_area() else " (Equip > Accessories)"
            except Exception as e:
                tom_mod_error("fuse_catalog", "finding where an item is", e)
            return ""

        def apex_fuse_name(i):
            return str(trl(item_get_name(i))).replace("[", "[[").replace("{", "{{")

        if "apex_fuse_catalog" not in config.overlay_screens:
            config.overlay_screens.append("apex_fuse_catalog")


# the CATALOG button: centred between the two glass capsules (game event screen at 267, 38; capsules at x 161-227
# and 305-371, so the gap is centred on x 266)
screen apex_fuse_catalog():
    zorder -17
    # a save can bring this overlay back while the mod is switched off: then draw nothing
    if hasattr(store, "apex_fuse_btn_visible") and apex_fuse_btn_visible() and renpy.get_screen("apex_fuse_catalog_list") is None:
        $ _n = len(apex_fuse_craftable())
        frame area (267 + 228, 38 + 214, 76, 20) padding 0,0 background None:
            imagebutton idle CustomBox(color=ColorMain1, xsize=76, ysize=20) hover CustomBox(color=light_color(ColorMain1), xsize=76, ysize=20) action Show("apex_fuse_catalog_list") tooltip ("Catalog: %d upgrade%s you can make now" % (_n, "" if _n == 1 else "s"))
            add CustomBox(color=ColorClick, xsize=75, ysize=20, shapestyle=1)
            text ("CATALOG" + (" (%d)" % _n if _n else "")) color ("#FFF" if _n else "#FFFFFF90") outlines [(absolute(0), "#000", absolute(1), absolute(1))] xalign 0.5 yalign 0.5 size 11 layout "nobreak"


screen apex_fuse_catalog_list():
    modal True
    zorder 100
    $ _rows = apex_fuse_craftable()
    add Solid("#00000090")
    frame area (267 + 26, 38 + 22, 480, 330) padding (12, 10) background Frame(CustomBox(color=ColorMain1, xsize=40, ysize=40), 8, 8):
        vbox spacing 6:
            hbox xfill True:
                text "CATALOG" size 18 bold True color ColorClick outlines [(absolute(0), "#000", absolute(1), absolute(1))]
                text "Upgrades you can make now - click one to put its items in" size 11 color "#FFFFFFB0" xalign 1.0 yalign 0.6
            if not _rows:
                null height 40
                text "Nothing you can fuse right now.\nYou need both ingredients of a recipe (and a mastered skill for items that teach one)." size 13 color "#FFFFFFC0" xalign 0.5 text_align 0.5
            else:
                viewport:
                    xsize 456 ysize 248
                    mousewheel True draggable True scrollbars "vertical"
                    vbox spacing 4:
                        for _a, _b, _r in _rows:
                            button:
                                xsize 440 ysize 46 padding (6, 2)
                                background Solid("#00000050")
                                hover_background Solid(ColorClick + "40")
                                action Function(apex_fuse_pick, _a, _b)
                                tooltip apex_fuse_name(_r) + "\n" + item_get_desc(_r)
                                hbox spacing 6 yalign 0.5:
                                    add item_get_image(_a) zoom 0.55 yalign 0.5
                                    text "+" size 18 color "#FFFFFF" yalign 0.5
                                    add item_get_image(_b) zoom 0.55 yalign 0.5
                                    text "→" size 18 color ColorClick yalign 0.5
                                    add item_get_image(_r) zoom 0.55 yalign 0.5
                                    vbox yalign 0.5 xsize 250:
                                        text apex_fuse_name(_r) size 13 bold True color "#FFFFFF"
                                        text apex_fuse_name(_a) + apex_fuse_where(_a) + " + " + apex_fuse_name(_b) + apex_fuse_where(_b) size 10 color "#FFFFFFA0"
            textbutton "Close" text_size 13 text_color "#FFFFFF" text_hover_color ColorClick xalign 1.0 action Hide("apex_fuse_catalog_list")
    key "game_menu" action Hide("apex_fuse_catalog_list")
