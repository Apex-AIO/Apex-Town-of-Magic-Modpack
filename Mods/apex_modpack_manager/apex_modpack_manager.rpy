# apex_modpack_manager.rpy  -  Apex's Modpack Manager: the main-menu hub for every module of the modpack
#
# * "Apex's Modpack Manager" button on the main menu, above Start, in line with the other options
# * a scrolling list of modules with on/off switches, sub-modules (a tree under their module) and a gear for each
#   module's settings.  Choices are kept in persistent (apex_mm_off / apex_mm_settings / apex_mm_test_version);
#   tom_mod_guard.rpy reads them once at start-up, so every change takes effect after a restart
# * leaving the screen or quitting the game with unapplied changes asks "Restart now to apply changes?"
# * game version check: the version the pack was made for is green (same), orange (same 0.xx line) or red;
#   if the game is NEWER than the pack, every module is off until "Test modpack" is switched on, and the main
#   menu says so once per launch
# * bottom: every module's revision, the versions, the last update date and the tip button
#
# The module list, settings, revisions and dates come from APEX_BUILD, written by Tools/build_modpack.py.

init -10 python:
    if "APEX_BUILD" not in globals():
        APEX_BUILD = None

init 1 python:
    import builtins as _apex_b      # dict/list here are Ren'Py's own types: check against the real ones

    def apex_mm_modules():
        return (APEX_BUILD or {}).get("modules", [])

    def apex_mm_off_now():
        off = persistent.apex_mm_off
        return set(x for x in off if isinstance(x, str)) if isinstance(off, (_apex_b.list, _apex_b.tuple, _apex_b.set, _apex_b.frozenset)) else set()

    # what was switched off when the game started (the guard's list = what is actually running)
    APEX_MM_BOOT_OFF = TOM_BOOT_OFF

init 999 python:
    import renpy.exports as _apex_exports

    # the HD module isn't running -> Ren'Py must not pick up the @2/@4 files on its own either
    if not tom_mod_status.get("hd_sprites", "").startswith("on"):
        config.automatic_oversampling = None

    # ---------------- settings (the gear) and sub-modules ----------------
    def apex_mm_spec(mid, key):
        return tom_setting_spec(mid, key)

    def _apex_clean(mid, key, v):
        """a value made valid for its setting, or None"""
        s = apex_mm_spec(mid, key)
        if s is None:
            return None
        d = s.get("default")
        if isinstance(d, bool):
            return v if isinstance(v, bool) else None
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")):
            return None
        v = min(max(v, s.get("min", v)), s.get("max", v))
        return int(round(v)) if isinstance(d, int) else round(float(v), 4)

    def _apex_norm(settings):
        """{mod: {key: value}} without invalid values and without values equal to the default"""
        out = {}
        if not isinstance(settings, _apex_b.dict):
            return out
        for mid, d in settings.items():
            if not isinstance(d, _apex_b.dict):
                continue
            for k, v in d.items():
                c = _apex_clean(mid, k, v)
                if c is not None and c != apex_mm_spec(mid, k).get("default"):
                    out.setdefault(mid, {})[k] = c
        return out

    APEX_MM_BOOT_SETTINGS = _apex_norm(TOM_BOOT_SETTINGS)

    def apex_mm_get(mid, key):
        v = _apex_norm(persistent.apex_mm_settings).get(mid, {}).get(key)
        if v is None:
            v = (apex_mm_spec(mid, key) or {}).get("default")
        return v

    def apex_mm_boot_value(mid, key):
        v = APEX_MM_BOOT_SETTINGS.get(mid, {}).get(key)
        return (apex_mm_spec(mid, key) or {}).get("default") if v is None else v

    def apex_mm_set(mid, key, v):
        sets = _apex_norm(persistent.apex_mm_settings)
        c = _apex_clean(mid, key, v)
        if c is None:
            return
        if c == apex_mm_spec(mid, key).get("default"):
            sets.get(mid, {}).pop(key, None)
        else:
            sets.setdefault(mid, {})[key] = c
        persistent.apex_mm_settings = dict((m, d) for m, d in sets.items() if d)
        renpy.save_persistent()
        renpy.restart_interaction()

    def apex_mm_step(mid, key, direction):
        s = apex_mm_spec(mid, key)
        if s is None:
            return
        v = apex_mm_get(mid, key)
        if isinstance(s.get("default"), bool):
            apex_mm_set(mid, key, not v)
        else:
            apex_mm_set(mid, key, v + direction * s.get("step", 1))

    def apex_mm_module(mid):
        for m in apex_mm_modules():
            if m["id"] == mid:
                return m
        return {}

    def apex_mm_reset(mid):
        sets = _apex_norm(persistent.apex_mm_settings)
        mine = sets.get(mid, {})
        for s in (apex_mm_module(mid).get("settings") or []):
            mine.pop(s["key"], None)                 # sub-module switches are left as they are
        persistent.apex_mm_settings = dict((k, d) for k, d in sets.items() if d)
        renpy.save_persistent()
        renpy.restart_interaction()

    def apex_mm_is_default(mid):
        return all(apex_mm_get(mid, s["key"]) == s.get("default") for s in (apex_mm_module(mid).get("settings") or []))

    def apex_mm_fmt(s, v):
        t = s.get("type")
        if t == "bool" or isinstance(v, bool):
            return "On" if v else "Off"
        if t == "one_in":
            return "1 in %d" % v
        if t == "percent":
            return "%d%%" % v
        if t == "number":
            return ("%.2f" % v).rstrip("0").rstrip(".")
        return "%d%s" % (v, s.get("unit", ""))

    def apex_mm_safe(text):
        # module texts are plain text: no Ren'Py text tags or [variables]
        return (text or "").replace("{", "{{").replace("[", "[[")

    def apex_mm_text(mid, text):
        """a description with {key} replaced by that setting's chosen value"""
        import re

        def sub(mo):
            s = apex_mm_spec(mid, mo.group(1))
            return apex_mm_fmt(s, apex_mm_get(mid, mo.group(1))) if s else mo.group(0)
        return apex_mm_safe(re.sub(r"\{(\w+)\}", sub, text or ""))

    # ---------------- version check and "Test modpack" ----------------
    def apex_mm_version():
        return tom_version_info()

    def apex_mm_test_wanted():
        vi = apex_mm_version()
        return vi["newer"] and persistent.apex_mm_test_version == vi["game"]

    def apex_mm_set_test(on):
        persistent.apex_mm_test_version = apex_mm_version()["game"] if on else None
        renpy.save_persistent()
        renpy.restart_interaction()

    apex_mm_seen_warning = [False]          # the "outdated modpack" message is shown once per launch

    # ---------------- on / off ----------------
    def apex_mm_pending():
        if apex_mm_off_now() != set(APEX_MM_BOOT_OFF):
            return True
        if _apex_norm(persistent.apex_mm_settings) != APEX_MM_BOOT_SETTINGS:
            return True
        vi = apex_mm_version()
        return vi["newer"] and apex_mm_test_wanted() != vi["approved"]

    def apex_mm_is_on(mid):
        return mid not in apex_mm_off_now()

    def apex_mm_toggle(mid):
        off = apex_mm_off_now()
        if mid in off:
            off.discard(mid)
        else:
            off.add(mid)
        persistent.apex_mm_off = sorted(off)
        renpy.save_persistent()
        renpy.restart_interaction()

    def apex_mm_status(m):
        """(text, colour) for a module's status"""
        mid = m["id"]
        st = tom_mod_status.get(mid, "")
        want_on = apex_mm_is_on(mid)
        if st.startswith("off: outdated"):
            if want_on and apex_mm_test_wanted():
                return ("Turns ON after a restart (testing)", "#ffd24d")
            return ("Off: outdated modpack", "#4de1ff")
        if st.startswith("off: game"):
            return ("Paused: a game update changed what it uses", "#ff6b6b")
        if st.startswith("off: tom_mods_off"):
            return ("Off: tom_mods_off.txt is in the game folder", "#ff6b6b")
        if not st:
            return ("Not loaded", "#ff6b6b")
        running = st.startswith("on")
        if want_on and not running:
            return ("Turns ON after a restart", "#ffd24d")
        if running and not want_on:
            return ("Turns OFF after a restart", "#ffd24d")
        if running and any(apex_mm_get(mid, s["key"]) != apex_mm_boot_value(mid, s["key"])
                           for s in (m.get("settings") or [])):
            return ("New settings after a restart", "#ffd24d")
        if running:
            return ("Running", "#7ee08a")
        return ("Off", "#8a8a8a")

    def apex_mm_sub_status(m, s):
        mid, key = m["id"], s["key"]
        if not apex_mm_is_on(mid):
            return ("Off with its module", "#8a8a8a")
        if apex_mm_get(mid, key) != apex_mm_boot_value(mid, key):
            return ("Changes after a restart", "#ffd24d")
        if not tom_mod_status.get(mid, "").startswith("on"):
            return ("", "#8a8a8a")
        return ("Running", "#7ee08a") if apex_mm_get(mid, key) else ("Off", "#8a8a8a")

    def apex_mm_count_on():
        return sum(1 for m in apex_mm_modules() if apex_mm_is_on(m["id"]))

    def apex_mm_date(d):
        try:
            import datetime
            return datetime.date(*[int(x) for x in d.split("-")]).strftime("%d %b %Y").lstrip("0")
        except Exception:
            return d or "?"

    def apex_mm_restart():
        renpy.quit(relaunch=True)

    # quitting with changes that aren't applied yet -> offer to restart instead
    _apex_orig_quit = _apex_exports.quit
    _apex_asking = [False]

    def _apex_quit(relaunch=False, status=0, save=False):
        if not relaunch and not _apex_asking[0]:
            try:
                if apex_mm_pending():
                    _apex_asking[0] = True
                    try:
                        relaunch = bool(renpy.invoke_in_new_context(renpy.call_screen, "apex_mm_restart_prompt",
                                                                    quitting=True))
                    finally:
                        _apex_asking[0] = False
            except Exception:
                pass
        return _apex_orig_quit(relaunch=relaunch, status=status, save=save)

    if APEX_BUILD is not None and getattr(_apex_exports.quit, "__name__", "") != "_apex_quit":
        _apex_exports.quit = _apex_quit

    if APEX_BUILD is not None and "apex_mm_menu_button" not in config.always_shown_screens:
        config.always_shown_screens.append("apex_mm_menu_button")


# ---------------- styles ----------------
style apex_mm_text is default:
    font gui.text_font
    size 13
    color "#dddddd"
    outlines []

style apex_mm_vscrollbar:
    xsize 6
    base_bar Solid("#ffffff14")
    thumb Solid("#9933ff")
    hover_thumb Solid("#c184ff")
    unscrollable "hide"

style apex_mm_button is default
style apex_mm_button_text is apex_mm_text
style apex_mm_frame is default
style apex_mm_viewport is default


# ---------------- main menu button: above "Start", same left edge as the other options ----------------
screen apex_mm_menu_button():
    zorder 50
    if main_menu and renpy.get_screen("main_menu") and not renpy.get_screen("apex_modpack_manager"):
        $ vi = apex_mm_version()
        vbox:
            xpos gui.navigation_xpos
            ypos 104
            spacing 2
            button:
                padding (4, 2)
                background None
                hover_background Solid("#9933ff33")
                action ShowMenu("apex_modpack_manager")
                vbox:
                    text "Apex's Modpack" size 20 color "#ffd24d" hover_color "#ffffff"
                    text "Manager" size 20 color "#ffd24d" hover_color "#ffffff"
            if vi["locked"] and not apex_mm_test_wanted():
                text "Outdated: all modules off" size 11 color "#4de1ff" xpos 4
            else:
                text ("%d of %d modules on" % (apex_mm_count_on(), len(apex_mm_modules()))) size 11 color "#9a9a9a" xpos 4
            if apex_mm_pending():
                text "Restart to apply changes" size 11 color "#ffd24d" xpos 4
            add Solid("#9933ff") xsize 170 ysize 1 ypos 12 xpos 4

        # once per launch: the game is newer than the modpack
        if vi["locked"] and not apex_mm_seen_warning[0]:
            use apex_mm_outdated_warning


screen apex_mm_outdated_warning():
    modal True
    style_prefix "apex_mm"
    $ vi = apex_mm_version()
    add Solid("#000000b0")
    frame:
        xalign 0.5 yalign 0.5 xsize 560 padding (26, 22)
        background Solid("#101c26")
        vbox:
            spacing 12 xfill True
            text "Outdated modpack" size 22 bold True color "#4de1ff" xalign 0.5
            text ("Your game is version %s, but this modpack was made for %s." % (vi["game"], vi["made_for"])) size 13 color "#dddddd" xalign 0.5 text_align 0.5
            text "You are running an outdated modpack, so all mods and modules have been disabled. If you wish to test the modpack on this new version, go to Apex's Modpack Manager." size 13 color "#dddddd" xalign 0.5 text_align 0.5
            hbox:
                xalign 0.5 spacing 16
                textbutton "Open Modpack Manager":
                    padding (16, 7)
                    background Solid("#4de1ff") hover_background Solid("#9df0ff")
                    text_color "#000000" text_size 15 text_bold True
                    action [SetDict(apex_mm_seen_warning, 0, True), ShowMenu("apex_modpack_manager")]
                textbutton "OK":
                    padding (16, 7)
                    background Solid("#ffffff18") hover_background Solid("#9933ff88")
                    text_color "#ffffff" text_size 15
                    action SetDict(apex_mm_seen_warning, 0, True)


# ---------------- the manager ----------------
screen apex_modpack_manager():
    tag menu
    modal True
    style_prefix "apex_mm"

    $ vi = apex_mm_version()
    $ mods = apex_mm_modules()
    $ b = APEX_BUILD or {}
    $ testing = apex_mm_test_wanted()

    add gui.main_menu_background
    add Solid("#07040cf0")

    # header
    text "Apex's Modpack Manager" xpos 28 ypos 14 size 30 color "#ffd24d" bold True
    if vi["newer"] and not testing:
        text "The game is newer than this modpack, so every module is off. Switch on \"Test modpack\" (bottom) to try it anyway." xpos 30 ypos 52 size 13 color "#4de1ff"
    else:
        text "Switch modules on or off; the gear changes a module's settings. Changes apply after a restart." xpos 30 ypos 52 size 13 color "#a8a8a8"

    hbox:
        xalign 1.0 xoffset -24 ypos 20 spacing 12
        if apex_mm_pending():
            textbutton "Restart now":
                padding (14, 6)
                background Solid("#ffd24d") hover_background Solid("#ffe680")
                text_color "#000000" text_size 15 text_bold True
                action Function(apex_mm_restart)
        textbutton "Back":
            padding (14, 6)
            background Solid("#ffffff18") hover_background Solid("#9933ff88")
            text_color "#ffffff" text_size 15
            action If(apex_mm_pending(), Show("apex_mm_restart_prompt", quitting=False), Return())

    # modules (scrolls when the list gets long)
    viewport:
        xpos 28 ypos 78 xsize 1016 ysize 318
        mousewheel True
        draggable True
        scrollbars "vertical"
        spacing 4
        vbox:
            spacing 5
            for m in mods:
                $ on = apex_mm_is_on(m["id"])
                $ st, stc = apex_mm_status(m)
                frame:
                    xsize 1000 padding (8, 6)
                    background Solid("#ffffff0d")
                    hbox:
                        spacing 10
                        button:
                            xsize 726 padding (2, 2)
                            background None hover_background Solid("#9933ff30")
                            action Function(apex_mm_toggle, m["id"])
                            hbox:
                                spacing 14
                                frame:
                                    xsize 58 ysize 24 yalign 0.5 padding (0, 0)
                                    background Solid("#2fa84f" if on else "#55505c")
                                    text ("ON" if on else "OFF") size 13 bold True color "#ffffff" xalign 0.5 yalign 0.5
                                vbox:
                                    xsize 640 yalign 0.5
                                    hbox:
                                        spacing 8
                                        text apex_mm_safe(m["title"]) size 15 bold True color ("#ffffff" if on else "#9a9a9a")
                                        text ("r" + m["rev"]) size 12 color "#b38cff" yalign 1.0
                                        if m.get("wip"):
                                            text apex_mm_safe(m["wip"]) size 11 bold True color "#ff9a3c" yalign 1.0
                                    text apex_mm_text(m["id"], m["desc"]) size 11 color "#a0a0a0"
                        frame:
                            xsize 210 yalign 0.5 padding (0, 0) background None
                            text st size 12 color stc xalign 1.0 text_align 1.0
                        if m.get("settings"):
                            imagebutton:
                                idle "apex_modpack/gear.png"
                                hover "apex_modpack/gear_hover.png"
                                yalign 0.5
                                action Show("apex_mm_settings", mid=m["id"])
                        else:
                            null width 22
                # sub-modules: a tree under their module
                $ subs = m.get("subs") or []
                for i, s in enumerate(subs):
                    $ son = bool(apex_mm_get(m["id"], s["key"]))
                    $ sst, sstc = apex_mm_sub_status(m, s)
                    frame:
                        xsize 1000 padding (8, 3)
                        background Solid("#ffffff07")
                        hbox:
                            spacing 8
                            null width 18
                            text ("└─" if i == len(subs) - 1 else "├─") size 18 color "#6d5a8a" yalign 0.5
                            button:
                                xsize 668 padding (2, 2)
                                background None hover_background Solid("#9933ff30")
                                action Function(apex_mm_step, m["id"], s["key"], 1)
                                hbox:
                                    spacing 12
                                    frame:
                                        xsize 46 ysize 20 yalign 0.5 padding (0, 0)
                                        background Solid(("#2fa84f" if son else "#55505c") if on else "#3a3640")
                                        text ("ON" if son else "OFF") size 11 bold True color "#ffffff" xalign 0.5 yalign 0.5
                                    vbox:
                                        xsize 610 yalign 0.5
                                        text apex_mm_safe(s["title"]) size 13 bold True color ("#ffffff" if (on and son) else "#9a9a9a")
                                        text apex_mm_text(m["id"], s.get("desc", "")) size 11 color "#a0a0a0"
                            frame:
                                xsize 210 yalign 0.5 padding (0, 0) background None
                                text sst size 12 color sstc xalign 1.0 text_align 1.0

    # bottom info: modules | game | modpack | support
    $ lvl_col = {"match": "#7ee08a", "minor": "#ff9a3c"}.get(vi["level"], "#ff6b6b")
    hbox:
        xpos 28 ypos 404 spacing 10
        frame:
            xsize 290 ysize 182 padding (10, 8) background Solid("#ffffff0d")
            vbox:
                spacing 2
                text "MODULES" size 12 bold True color "#b38cff"
                viewport:
                    xsize 270 ysize 148
                    mousewheel True
                    scrollbars "vertical"
                    spacing 2
                    vbox:
                        spacing 1
                        for m in mods:
                            hbox:
                                xsize 256
                                text apex_mm_safe(m["title"]) size 11 color "#cccccc" xsize 216
                                text ("r" + m["rev"]) size 11 color "#ffd24d" xalign 1.0
                        hbox:
                            xsize 256
                            text "Modpack Manager" size 11 color "#cccccc"
                            text ("r" + b.get("core_rev", "?")) size 11 color "#ffd24d" xalign 1.0
        frame:
            xsize 220 ysize 182 padding (10, 8) background Solid("#ffffff0d")
            vbox:
                spacing 2
                text "GAME" size 12 bold True color "#b38cff"
                text "Your game version" size 11 color "#a0a0a0"
                hbox:
                    spacing 6
                    text vi["game"] size 15 bold True color "#ffffff"
                    if vi["simulated"]:
                        text "(simulated)" size 10 color "#ff9a3c" yalign 1.0
                text "Modpack made for" size 11 color "#a0a0a0"
                text vi["made_for"] size 15 bold True color lvl_col
                if vi["level"] == "match":
                    text "Compatible" size 11 color lvl_col
                elif vi["level"] == "minor":
                    text "Version mismatch: bugs will likely occur. Wait for a modpack update or run the risk of bugs." size 10 color lvl_col
                else:
                    text "Highly suggested not to run: it will likely break and won't be a good experience. Please update." size 10 color lvl_col
        frame:
            xsize 220 ysize 182 padding (10, 8) background Solid("#ffffff0d")
            vbox:
                spacing 2
                text "MODPACK" size 12 bold True color "#b38cff"
                text "Version" size 11 color "#a0a0a0"
                text b.get("version", "?") size 15 bold True color ("#4de1ff" if vi["newer"] else "#ffffff")
                if vi["newer"]:
                    text "Outdated modpack, untested" size 11 color "#4de1ff"
                    hbox:
                        spacing 6
                        text "Test modpack?" size 11 color "#dddddd" yalign 0.5
                        textbutton "Yes":
                            padding (8, 2)
                            background Solid("#2fa84f" if testing else "#ffffff14")
                            hover_background Solid("#3fc865")
                            text_size 11 text_color "#ffffff" text_bold testing
                            action Function(apex_mm_set_test, True)
                        textbutton "No":
                            padding (8, 2)
                            background Solid("#55505c" if not testing else "#ffffff14")
                            hover_background Solid("#77707f")
                            text_size 11 text_color "#ffffff" text_bold (not testing)
                            action Function(apex_mm_set_test, False)
                    text "Master switch for the whole modpack on this game version." size 10 color "#a0a0a0"
                else:
                    text "Last updated" size 11 color "#a0a0a0"
                    text apex_mm_date(b.get("date")) size 15 bold True color "#ffffff"
                    text ("%d of %d modules on" % (apex_mm_count_on(), len(mods))) size 11 color "#a0a0a0"
        frame:
            xsize 256 ysize 182 padding (12, 8) background Solid("#ffffff0d")
            vbox:
                spacing 7
                text "SUPPORT" size 12 bold True color "#b38cff"
                text "If you'd like to support the modpack's creation and future development, please support the game's developers first before considering tipping me!" size 11 color "#dddddd"
                imagebutton:
                    idle "apex_modpack/bmc_button.png"
                    hover "apex_modpack/bmc_button_hover.png"
                    action OpenURL(b.get("tip_url", "https://buymeacoffee.com/apex_modding"))
                    xalign 0.5

    key "game_menu" action If(apex_mm_pending(), Show("apex_mm_restart_prompt", quitting=False), Return())


# ---------------- a module's settings (the gear) ----------------
screen apex_mm_settings(mid):
    modal True
    zorder 200
    style_prefix "apex_mm"
    $ m = apex_mm_module(mid)
    add Solid("#000000b0")
    frame:
        xalign 0.5 yalign 0.5 xsize 780 padding (22, 16)
        background Solid("#1b1226")
        vbox:
            spacing 8
            text (apex_mm_safe(m.get("title", "")) + " - settings") size 20 bold True color "#ffd24d"
            text "Changes apply after a restart." size 12 color "#a8a8a8"
            viewport:
                xsize 736 ysize min(420, 66 * len(m.get("settings") or []))
                mousewheel True
                draggable True
                scrollbars "vertical"
                spacing 4
                vbox:
                    spacing 4
                    for s in (m.get("settings") or []):
                        $ v = apex_mm_get(mid, s["key"])
                        $ changed = (v != apex_mm_boot_value(mid, s["key"]))
                        frame:
                            xsize 722 padding (10, 6)
                            background Solid("#ffffff0d")
                            hbox:
                                vbox:
                                    xsize 420 yalign 0.5
                                    text apex_mm_safe(s.get("label", s["key"])) size 13 bold True color "#ffffff"
                                    if s.get("help"):
                                        text apex_mm_safe(s["help"]) size 11 color "#a0a0a0"
                                hbox:
                                    yalign 0.5 spacing 6
                                    if s.get("type") == "bool":
                                        null width 34
                                        textbutton ("On" if v else "Off"):
                                            xsize 96 padding (0, 3)
                                            background Solid("#2fa84f" if v else "#55505c")
                                            hover_background Solid("#3fc865" if v else "#77707f")
                                            text_size 13 text_bold True text_color "#ffffff" text_xalign 0.5
                                            action Function(apex_mm_step, mid, s["key"], 1)
                                        null width 34
                                    else:
                                        textbutton "-":
                                            xsize 30 padding (0, 2)
                                            background Solid("#ffffff18") hover_background Solid("#9933ff88")
                                            insensitive_background Solid("#ffffff08")
                                            text_size 15 text_bold True text_color "#ffffff" text_insensitive_color "#555555" text_xalign 0.5
                                            sensitive v > s.get("min", v)
                                            action Function(apex_mm_step, mid, s["key"], -1)
                                        frame:
                                            xsize 100 yalign 0.5 padding (0, 0) background None
                                            text apex_mm_fmt(s, v) size 14 bold True color ("#ffd24d" if changed else "#ffffff") xalign 0.5
                                        textbutton "+":
                                            xsize 30 padding (0, 2)
                                            background Solid("#ffffff18") hover_background Solid("#9933ff88")
                                            insensitive_background Solid("#ffffff08")
                                            text_size 15 text_bold True text_color "#ffffff" text_insensitive_color "#555555" text_xalign 0.5
                                            sensitive v < s.get("max", v)
                                            action Function(apex_mm_step, mid, s["key"], 1)
                                    if v != s.get("default"):
                                        text ("default " + apex_mm_fmt(s, s.get("default"))) size 10 color "#8a8a8a" yalign 0.5
            hbox:
                xfill True
                textbutton "Reset to defaults":
                    padding (14, 6)
                    background Solid("#ffffff18") hover_background Solid("#9933ff88")
                    insensitive_background Solid("#ffffff08")
                    text_color "#ffffff" text_insensitive_color "#555555" text_size 14
                    sensitive not apex_mm_is_default(mid)
                    action Function(apex_mm_reset, mid)
                textbutton "Done":
                    xalign 1.0
                    padding (18, 6)
                    background Solid("#ffd24d") hover_background Solid("#ffe680")
                    text_color "#000000" text_size 14 text_bold True
                    action Hide("apex_mm_settings")
    key "game_menu" action Hide("apex_mm_settings")


# "Restart now to apply changes?"  (quitting=True: shown while the game is closing; returns True = restart)
screen apex_mm_restart_prompt(quitting=False):
    modal True
    zorder 300
    style_prefix "apex_mm"
    add Solid("#000000aa")
    frame:
        xalign 0.5 yalign 0.5 xsize 460 padding (24, 20)
        background Solid("#1b1226")
        vbox:
            spacing 14 xfill True
            text "Restart now to apply changes?" size 20 bold True color "#ffd24d" xalign 0.5
            text "You changed modules or their settings. They take effect when the game starts, so a restart is needed." size 13 color "#dddddd" text_align 0.5 xalign 0.5
            hbox:
                xalign 0.5 spacing 16
                textbutton "Restart now":
                    padding (16, 7)
                    background Solid("#ffd24d") hover_background Solid("#ffe680")
                    text_color "#000000" text_size 15 text_bold True
                    action (Return(True) if quitting else Function(apex_mm_restart))
                textbutton ("Just quit" if quitting else "Later"):
                    padding (16, 7)
                    background Solid("#ffffff18") hover_background Solid("#9933ff88")
                    text_color "#ffffff" text_size 15
                    action (Return(False) if quitting else [Hide("apex_mm_restart_prompt"), Return()])
