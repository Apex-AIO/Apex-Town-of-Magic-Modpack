# stutter_fix.rpy  -  removes the ~0.3-0.4 second freezes in battle when Celica changes pose
#
# Cause (found with a frame-time recorder): when her pose changes in battle, the game prepares the next pictures
# by searching its whole file list (~33,000 names) about 20 times with a slow pattern match
# (list_files_match / list_files_regex in procedures.rpy, called from renpy_battle.rpy).
# The file list never changes while the game runs, so this mod:
#   1. remembers the answer to every search (the same searches repeat every turn), and
#   2. only runs the slow pattern match on names that contain the pattern's fixed text.
# The results are exactly the same as the game's own.
#
# Uninstall: delete stutter_fix.rpy / stutter_fix.rpyc.

init 5 python:
    # only when the shared guard says the game still matches what this mod was made for (tom_mod_guard.rpy)
    if tom_mod_ok('stutter_fix',
                  hooks=['list_files_match', 'list_files_regex', 'list_files_containing'],
                  needs=[]):
        import re as _sf_re, fnmatch as _sf_fnmatch

        _sf_cache = {}
        _sf_files = {}

        def _sf_list(common):
            # the game's file list (and a lower-case copy), read once
            if common not in _sf_files:
                fl = list(renpy.list_files(common=common))
                _sf_files[common] = (fl, [f.lower() for f in fl])
            return _sf_files[common]

        def _sf_literal(pattern, stop):
            # the fixed text at the start of a pattern (up to the first wildcard)
            out = []
            for ch in pattern:
                if ch in stop:
                    break
                out.append(ch)
            return "".join(out)

        def list_files_regex(pattern, common=False, flags=0):
            key = ("re", pattern, common, flags)
            if key not in _sf_cache:
                regex = _sf_re.compile(pattern, flags)
                fl, low = _sf_list(common)
                lit = _sf_literal(pattern, ".^$*+?{}[]\\|()")
                if lit:
                    if flags & _sf_re.IGNORECASE:
                        l = lit.lower()
                        cand = [f for f, lf in zip(fl, low) if l in lf]
                    else:
                        cand = [f for f in fl if lit in f]
                else:
                    cand = fl
                _sf_cache[key] = [f for f in cand if regex.search(f)]
            return list(_sf_cache[key])

        def list_files_match(pattern, common=False):
            key = ("fn", pattern, common)
            if key not in _sf_cache:
                fl, low = _sf_list(common)
                lit = _sf_literal(pattern, "*?[").lower()            # fnmatch on Windows ignores upper/lower case
                cand = [f for f, lf in zip(fl, low) if lit in lf] if lit else fl
                _sf_cache[key] = [f for f in cand if _sf_fnmatch.fnmatch(f, pattern)]
            return list(_sf_cache[key])

        def list_files_containing(text, common=False):
            key = ("in", text, common)
            if key not in _sf_cache:
                fl, low = _sf_list(common)
                _sf_cache[key] = [f for f in fl if text in f]
            return list(_sf_cache[key])

        # ---- 2: the game empties ALL picture memory after battles and at wake-up (renpy.free_memory, 8 places):
        # every texture is thrown away and reloaded on the next frame, plus a full Python memory sweep, so the screen
        # freezes for 0.25 s (0.55 s with HD pictures).  Ren'Py's picture memory already limits itself (oldest
        # pictures go first), so while it is less than 80% full the wipe is skipped.  When it is fuller, the game's
        # own call runs as before.
        import renpy.display.im as _sf_im
        _sf_orig_free_memory = renpy.free_memory

        def _sf_free_memory():
            try:
                c = _sf_im.cache
                if c.cache_limit and c.cache_size < 0.8 * c.cache_limit:
                    return
            except Exception as e:
                tom_mod_error("stutter_fix", "checking picture memory", e)
            return _sf_orig_free_memory()

        renpy.free_memory = _sf_free_memory

        # ---- 3: Python's full garbage sweep.  The game keeps ~575,000 objects alive (items, enemies, settings...), so
        # every full sweep, which Ren'Py starts now and then at idle moments, freezes the game for ~120 ms - the
        # 250-300 ms hitches in battles.  gc.freeze() moves everything that exists right now out of the sweep (the
        # sweep then only looks at new objects: ~0 ms).  Each start and load first sweeps the old objects once
        # (unfreeze + collect), then freezes the new state, so nothing leaks from one save to the next.
        import gc as _sf_gc

        def _sf_refreeze():
            try:
                _sf_gc.unfreeze()
                _sf_gc.collect(2)
                _sf_gc.freeze()
            except Exception as e:
                tom_mod_error("stutter_fix", "freezing long-lived objects", e)

        _SF_FROZEN = [False]

        def _sf_first_freeze():
            # once, a moment after the game has started (init is finished): the main menu is showing
            if not _SF_FROZEN[0] and renpy.get_screen("main_menu") is not None:
                _SF_FROZEN[0] = True
                _sf_refreeze()

        if _sf_refreeze not in config.after_load_callbacks:
            config.after_load_callbacks.append(_sf_refreeze)
        if _sf_refreeze not in config.start_callbacks:
            config.start_callbacks.append(_sf_refreeze)
        if _sf_first_freeze not in config.periodic_callbacks:
            config.periodic_callbacks.append(_sf_first_freeze)
