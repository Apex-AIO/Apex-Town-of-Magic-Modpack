# appearance_unlock.rpy  -  the Equip > Appearance tab is open from the start
#
# Normally the Appearance tab (changing clothes / outfits) opens after the tailor, Walter Turner, unlocks it - or
# the first time Celica picks up a piece of clothing.  This mod opens it right away: on a new game and on every
# save you load.  It uses the game's own unlock (the same one the tailor uses), nothing else changes.

init 999 python:
    import builtins as _bt     # dict/list in Ren'Py scripts are Ren'Py's own types; check against the real ones
    # only when the shared guard says the game still matches what this mod was made for (tom_mod_guard.rpy)
    if tom_mod_ok('appearance_unlock',
                  hooks=[],
                  needs=['enable_clothes_menu', 'is_clothes_enabled']):
        import time as _au_time

        def _au_unlock():
            try:
                mv = getattr(store, "main_vars", None)
                tl = getattr(store, "setup_frame_list", None)
                # wait until a new game has built its menu list (it is made after main_vars)
                if not (isinstance(mv, _bt.dict) and "attire_list" in mv and getattr(store, "e_celica", None) is not None
                        and tl is not None and tl.has("Quests")):
                    return
                if not is_clothes_enabled():
                    enable_clothes_menu()
                elif not tl.has("Appearance"):
                    # unlocked, but the tab is missing from the menu list: put it back the way the tailor does
                    tl.add("EQUIPMENT", "root")
                    tl.add("Appearance", "EQUIPMENT")
                    tl.add("Accessories", "EQUIPMENT")
            except Exception:
                pass

        _au_next = [0.0]

        def _au_tick():
            # a new game sets up its variables a moment after it starts: check now and then until it's open
            now = _au_time.time()
            if now >= _au_next[0]:
                _au_next[0] = now + 3.0
                _au_unlock()

        if _au_unlock not in config.after_load_callbacks:
            config.after_load_callbacks.append(_au_unlock)
        if _au_tick.__name__ not in [getattr(f, "__name__", "") for f in config.periodic_callbacks]:
            config.periodic_callbacks.append(_au_tick)
