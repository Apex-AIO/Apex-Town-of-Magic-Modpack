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
