# hd_sprites.rpy  -  lets the game use high-resolution sprite files
#
# How it works
#   Ren'Py already supports HD files: next to "name.png" you can put "name@2.png" (2x size) and/or "name@4.png"
#   (4x size).  When the window is bigger than the game's 1066x600 canvas, Ren'Py draws the HD file instead,
#   still treating it as the original size, so nothing in the game's layout changes.
#     window up to 2x the canvas (e.g. 1920x1080)  -> @2 is used
#     window over 2x (e.g. 2560x1440, 4K)         -> @4 if it exists, otherwise @2
#   The game stacks a character's layers (body, clothes, face, hair...) with im.Composite, which blends them on
#   the CPU and never looks for HD files.  This mod builds those stacks with Ren'Py's GPU Composite instead, but
#   only when one of the layers has an HD file - everything else is left exactly as the game does it.
#
# The HD pictures themselves go in  game/images/CHAR/<character>/  next to where the originals live in the archive,
# named like the original plus @2 / @4.
#
# Debug log (off by default): set HD_LOG = True -> game/hd_log.txt

init 5 python:
    # only when the shared guard says the game still matches what this mod was made for (tom_mod_guard.rpy)
    if tom_mod_ok('hd_sprites',
                  hooks=['image_add_composite_path'],
                  needs=['animationimage_fileexists']):
        import os, io, time
        import renpy.display.im as _hd_im

        HD_ENABLED = True
        HD_LOG = False
        HD_IMAGE_CACHE_MB = tom_setting('hd_sprites', 'cache_mb', 1024)   # HD pictures are bigger: let Ren'Py keep more of them loaded (Ren'Py default 400)

        if (config.image_cache_size_mb or 0) < HD_IMAGE_CACHE_MB:
            config.image_cache_size_mb = HD_IMAGE_CACHE_MB

        def _hd_log(msg):

            tom_mod_log_check('hd_sprites', msg)
            if not HD_LOG:
                return
            try:
                with io.open(os.path.join(config.basedir, "game", "hd_log.txt"), "a", encoding="utf8") as f:
                    f.write(u"%s  %s\n" % (time.strftime("%H:%M:%S"), msg))
            except Exception:
                pass

        _hd_has = {}

        def _hd_has_hd(d):
            # True if d is a file image with an @2/@4 version
            if isinstance(d, str):
                key = d
            elif isinstance(d, _hd_im.Image):
                key = d.filename
            else:
                return False
            if key not in _hd_has:
                base, _, ext = key.rpartition(".")
                _hd_has[key] = any(renpy.loader.loadable("%s@%d.%s" % (base, n, ext), directory="images") for n in (2, 4))
                if _hd_has[key]:
                    _hd_log("HD found for %s" % key)
            return _hd_has[key]

        def _hd_composite(size, *args, **properties):
            if HD_ENABLED and any(_hd_has_hd(a) for a in args[1::2]):
                # GPU composite: every layer is drawn as its own image, so HD layers keep their resolution
                return Composite(size, *[a if i % 2 == 0 else (Image(a) if isinstance(a, str) else a) for i, a in enumerate(args)])
            try:
                return _hd_im.Composite(size, *args, **properties)
            except Exception as e:
                if "Expected an image" not in str(e):
                    raise
                return Composite(size, *args)       # a layer below is already a GPU composite

        # Ren'Py itself is NOT changed (saves store its classes by name, so replacing im.Composite broke loading).
        # Only the game's own shortcut "im" is pointed at a copy of the module whose Composite is ours.
        import types as _hd_types
        _hd_improxy = _hd_types.ModuleType("renpy.display.im")
        _hd_improxy.__dict__.update(_hd_im.__dict__)
        _hd_improxy.Composite = _hd_composite
        im = _hd_improxy

        # ---- HD on/off: F8 or the "HD Toggle" button under Health/Magic (remembered between sessions) ----
        # Ren'Py picks the @2/@4 file each time a picture is drawn, so switching automatic_oversampling changes every
        # picture that is drawn again: characters, backgrounds, items, icons, interface.  Pictures that did not change
        # (backgrounds, icons, frames) are not drawn again by themselves: Ren'Py keeps their last drawing (render cache)
        # and would show the old quality until something moved.  Emptying that cache (not the pictures in memory, so
        # there is no hitch) makes everything redraw at once.
        import renpy.display.render as _hd_render
        if persistent.apex_hd_off:
            config.automatic_oversampling = None

        def apex_hd_is_on():
            return not persistent.apex_hd_off

        def apex_hd_toggle():
            persistent.apex_hd_off = not persistent.apex_hd_off
            config.automatic_oversampling = None if persistent.apex_hd_off else 4
            try:
                _hd_render.free_memory()
                renpy.force_full_redraw()
            except Exception as e:
                tom_mod_error('hd_sprites', 'toggle redraw', e)
            renpy.notify("HD pictures %s" % ("OFF (original pictures)" if persistent.apex_hd_off else "ON"))
            renpy.restart_interaction()

        config.underlay.append(renpy.Keymap(K_F8=apex_hd_toggle))
        if "apex_hd_toggle" not in config.overlay_screens:
            config.overlay_screens.append("apex_hd_toggle")


# the "HD Toggle" button: right end of the strip under Health and Magic, drawn like the game's Equip button
screen apex_hd_toggle():
    zorder -17
    if hasattr(store, "apex_hd_toggle") and not _menu and not main_menu and renpy.get_screen("action_frame") is not None and not flag_list.has("enable_event_viewer") and not (hasattr(store, "apex_ui_blocked") and apex_ui_blocked()):
        frame area (156, 74, 75, 25) padding 0,0 background Solid("#000"):
            imagebutton idle CustomBox(color=ColorMain1, xsize=75, ysize=25) hover CustomBox(color=light_color(ColorMain1), xsize=75, ysize=25) action Function(apex_hd_toggle) tooltip ("HD pictures: " + ("ON" if apex_hd_is_on() else "OFF (original pictures)") + "\nClick or press F8 to switch.")
            add CustomBox(color=ColorClick, xsize=74, ysize=24, shapestyle=1, line_size=1)
            text ("HD Toggle" if apex_hd_is_on() else "{alpha=0.6}HD Toggle{/alpha}") outlines [(absolute(0), "#000", absolute(1), absolute(1))] xalign 0.5 yalign 0.5 size 14
