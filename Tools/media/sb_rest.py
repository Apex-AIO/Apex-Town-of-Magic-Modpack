# storyboards for the rest (in-memory changes only - reload the save afterwards, never save)
def close_equip():
    renpy.hide_screen("setup_frame")
    store.setup_frame_select = None
    renpy.show_screen("action_frame")

def hd(on):
    def f():
        if apex_hd_is_on() != on:
            apex_hd_toggle()
    return f

def open_equip(tab):
    def f():
        renpy.run([SetVariable('setup_frame_select', tab), Function(update_gui_vars, 'equip_showclothes', 'set', True),
                   Function(update_gui_vars, 'equip_zoom', 'set', 0.55), Function(update_gui_vars, 'equip_ypos', 'set', 0),
                   SetVariable('equip_page', 0), Function(renpy.show_screen, 'action_frame'), SetVariable('equip_inv_page', 0),
                   Show('setup_frame', in_color=ColorMain1), Function(update_gui_vars, 'frame_currentequip', 'set', 1),
                   Function(outfitset_initialize)])
    return f

def wear(var, on=True):
    def f():
        it = getattr(store, var)
        if is_equiped(it) != on:
            equip_procedure(it, "equip" if on else "unequip")
        refresh_gui_screen()
    return f

def backups():
    # show what a put-back looks like: two items used up since the last backup (memory only)
    some = [i for i in inventory.list if not is_equiped(i) and inventory.count(i) > 1][:2]
    for i in some:
        inventory_rem(inventory, i)
    main_vars["coins"] -= 40
    renpy.show_screen("apex_inv_backups")

def mm(page):
    def f():
        apex_mm_ui["page"] = page
        renpy.show_screen("apex_modpack_manager")
    return f

def mm_close():
    renpy.hide_screen("apex_modpack_manager")

store._SB = [
    ("hd", [(close_equip, 1.0), (hd(True), 1.5), (hd(False), 1.5), (hd(True), 1.5)]),
    ("remover", [(open_equip("Appearance"), 1.2), (wear("i_xr_top", False), 0.8), (wear("i_xr_bottom", False), 0.8),
                 (wear("i_xr_top"), 1.0), (wear("i_xr_bottom"), 1.0), (wear("i_xr_shoes"), 1.0)]),
    ("helpers", [(open_equip("Accessories"), 1.2), (wear("i_xr_helper_red"), 1.0)]),
    ("backups", [(close_equip, 1.0), (backups, 1.0)]),
    ("manager", [(lambda: renpy.hide_screen("apex_inv_backups"), 0.5)] +
                [(mm(p), 1.0) for p in ("overview", "apex", "yours", "hd", "tools", "about")] + [(mm_close, 0.5)]),
]

def _sb_next():
    if story_done() and store._SB:
        name, steps = store._SB.pop(0)
        story(name, steps)
    return not store._SB and story_done()
store._sb_next = _sb_next
_sb_next()
RESULT = "started"
