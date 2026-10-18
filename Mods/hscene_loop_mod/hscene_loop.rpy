# hscene_loop.rpy  -  keeps the monsters' grapple "molest" animations looping on Celica
#
# What it does
#   After a monster plays a molest animation (rub, fondle, fuck ...), the game normally goes back to a still
#   image while it is your turn.  This mod keeps a molest animation looping instead.
#   With several monsters on her, every monster that has molested her adds its animation to a "pool":
#     - each time she goes idle, one animation is picked at random from the pool
#     - while she stays idle it switches to another one from the pool every few seconds
#   An animation leaves the pool when:  its monster is shaken off / stops grabbing that spot, it strips her
#   (stripping is not looped), the monster is defeated, or she climaxes.
#   Any other animation (attack, struggle, ...) plays normally, then the loop resumes.
#
# Every different molest animation a monster has played stays in the pool (a monster with two animations adds both).
# The loop also plays the animation sound quietly (HL_SOUND_VOLUME of normal), ONE sound at a time: it plays, and when it has ended it plays again while she is still idle; it is cut as soon as she is not idle.
#
# Settings (below):  HL_LOOP_ENABLED = False turns it off;  HL_SWAP_SECONDS = (0, 0) disables switching while idle;
#                    HL_LOOP_SOUND = False turns the idle sounds off;  HL_SOUND_VOLUME = 0.30 is their volume.
# Debug log (off by default): set HL_LOG = True -> game/hl_log.txt

init 998 python:
    import builtins as _bt     # dict/list in Ren'Py scripts are Ren'Py's own types; check against the real ones
    # only when the shared guard says the game still matches what this mod was made for (tom_mod_guard.rpy)
    if tom_mod_ok('hscene_loop',
                  hooks=['enemimage'],
                  needs=['get_all_grabbed_areas', 'grab_dict_list', 'grab_dict_get', 'enemy_get_defeated', 'enemy_get_hp_perc', 'where_grab_who', 'is_battle_in_session', 'enemy_has_status', 'get_enemy_player', 'find_screen_controller', 'char_pos', 'struggle', 'enemy_get_dimensions', 'get_character_dimensions_from_file']):
        import os, io, inspect, time, random
        import renpy.store as store

        HL_LOOP_ENABLED = True
        HL_LOOP_SOUND = tom_setting('hscene_loop', 'sound', True)          # also replay the frame-synced sounds during the idle loop
        HL_SOUND_VOLUME = tom_setting('hscene_loop', 'volume', 30) / 100.0  # ... at this fraction of the normal volume (restored as soon as it is a monster's turn)
        HL_SLOW_LOG = 0.25             # log any step that takes longer than this many seconds (finds the cause of hitches)
        HL_ADAPTIVE = False            # True = if switching animations freezes the game, stop switching for the rest of that fight (off: 2x sheets made it unnecessary)
        # while idle, switch to another animation of the pool after this many seconds (min, max); (0, 0) = never
        _hl_lo, _hl_hi = tom_setting('hscene_loop', 'swap_min', 4), tom_setting('hscene_loop', 'swap_max', 8)
        HL_SWAP_SECONDS = (float(min(_hl_lo, _hl_hi)), float(max(_hl_lo, _hl_hi))) if tom_setting('hscene_loop', 'swap', True) else (0, 0)
        HL_LOG = False                 # True = write game/hl_log.txt (for troubleshooting)

        hl_pool = []                   # one entry per monster that has molested her
        hl_state = {"active": False, "current": None, "next": 0.0}
        _hl_log_count = [0]

        def _hl_log(msg):

            tom_mod_log_check('hscene_loop', msg)
            if not HL_LOG or _hl_log_count[0] > 1500:
                return
            try:
                _hl_log_count[0] += 1
                d = os.path.join(config.basedir, "game")
                if not os.path.isdir(d):
                    os.makedirs(d)
                with io.open(os.path.join(d, "hl_log.txt"), "a", encoding="utf8") as f:
                    f.write(u"%s  %s\n" % (time.strftime("%H:%M:%S"), msg))
            except Exception:
                pass

        _hl_vol = {"orig": None, "on": False}

        def _hl_vol_lower():
            if not HL_LOOP_SOUND or _hl_vol["on"]:
                return
            try:
                o = 1.0
                try:
                    o = float(getattr(renpy.audio.audio.get_channel("audio"), "secondary_volume", 1.0))
                except Exception:
                    o = 1.0
                _hl_vol["orig"] = o
                renpy.music.set_volume(o * HL_SOUND_VOLUME, channel="audio")
                _hl_vol["on"] = True
            except Exception as e:
                _hl_log("VOLUME lower failed %r" % (e,))

        def _hl_vol_restore():
            if not _hl_vol["on"]:
                return
            _hl_vol["on"] = False
            try:
                renpy.music.set_volume(_hl_vol["orig"] if _hl_vol["orig"] is not None else 1.0, channel="audio")
            except Exception as e:
                _hl_log("VOLUME restore failed %r" % (e,))


        # ---- idle sound: ONE sound at a time, on the game's "audio" channel, driven by the periodic tick (not by the game's timer screen)
        hl_snd = {"mem": None, "on": False, "events": [], "cycle": 1.0, "base": 0.0, "idx": 0, "next": 0.0, "last": 0.0, "name": None}

        def _hl_snd_events(mem, delay):
            # -> ([(offset_seconds, [sound names]), ...], cycle_seconds)   (same timing the game's own sound screen uses)
            dl = list(mem.get("delay_list") or [])
            def dur(i):
                return (delay * dl[i] if i < len(dl) else delay) * 0.001
            ev = []
            cycle = 0.0
            for ent in (mem.get("sounds") or []):
                try:
                    st, tot, names = int(ent[0]), int(ent[1]), ent[2]
                    if not isinstance(names, (_bt.list, _bt.tuple)):
                        names = [names]
                    names = [n for n in names if n]
                    if not names or tot < 1:
                        continue
                    ev.append((sum(dur(i) for i in range(min(st, tot))), list(names)))
                    cycle = max(cycle, sum(dur(i) for i in range(tot)))
                except Exception:
                    continue
            ev.sort(key=lambda e: e[0])
            return ev, max(cycle, 0.3)

        def _hl_snd_stop():
            if not hl_snd["on"]:
                return
            hl_snd["on"] = False
            hl_snd["mem"] = None
            if hl_snd.get("logged", 0):
                _hl_log("SOUND stop (idle loop ended or interrupted)")
            try:
                pl = renpy.music.get_playing(channel="audio")
                if pl and hl_snd["name"] and hl_snd["name"] in str(pl):
                    renpy.music.stop(channel="audio", fadeout=0.05)
            except Exception as e:
                _hl_log("SOUND stop failed %r" % (e,))

        def _hl_snd_start(mem, delay):
            _hl_snd_stop()
            if not HL_LOOP_SOUND or not mem.get("sounds"):
                return
            ev, cycle = _hl_snd_events(mem, delay)
            if not ev:
                return
            now = time.time()
            hl_snd.update({"mem": mem, "on": True, "events": ev, "cycle": cycle, "base": now, "idx": 0, "next": now + ev[0][0], "name": None, "busy": 0.0, "logged": 0})

        _hl_dur_cache = {}

        def _hl_mp3_len(path):
            # length of an mp3 in seconds (reads the file header: Xing/Info frame count, else constant bitrate); None if unknown
            if path in _hl_dur_cache:
                return _hl_dur_cache[path]
            dur = None
            try:
                fh = renpy.loader.load(path)
                try:
                    data = fh.read()
                finally:
                    try:
                        fh.close()
                    except Exception:
                        pass
                pos = 0
                if data[:3] == b"ID3":
                    pos = 10 + ((data[6] & 127) << 21 | (data[7] & 127) << 14 | (data[8] & 127) << 7 | (data[9] & 127))
                i = pos
                end = min(len(data) - 4, pos + 20000)
                while i < end:
                    if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
                        ver = (data[i + 1] >> 3) & 3
                        layer = (data[i + 1] >> 1) & 3
                        bi = data[i + 2] >> 4
                        si = (data[i + 2] >> 2) & 3
                        if ver != 1 and layer in (1, 2) and 0 < bi < 15 and si < 3:
                            break
                    i += 1
                else:
                    i = -1
                if i >= 0:
                    mpeg1 = (ver == 3)
                    sr = ([44100, 48000, 32000] if mpeg1 else [22050, 24000, 16000] if ver == 2 else [11025, 12000, 8000])[si]
                    if layer == 1:       # layer III
                        br = ([0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320] if mpeg1 else [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160])[bi]
                        spf = 1152 if mpeg1 else 576
                    else:                # layer II
                        br = [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384][bi]
                        spf = 1152
                    frames = None
                    head = data[i:i + 200]
                    for tag in (b"Xing", b"Info"):
                        j = head.find(tag)
                        if j > 0 and (head[j + 7] & 1):
                            frames = int.from_bytes(head[j + 8:j + 12], "big")
                            break
                    if frames:
                        dur = frames * spf / float(sr)
                    elif br:
                        dur = (len(data) - i) * 8.0 / (br * 1000.0)
            except Exception as e:
                _hl_log("mp3 length failed for %s %r" % (path, e))
            _hl_dur_cache[path] = dur
            return dur

        def _hl_snd_tick():
            if not (HL_LOOP_SOUND and hl_snd["on"]):
                return
            now = time.time()
            # the game's own sound screen must not run next to ours
            try:
                if renpy.get_screen("enemimage_frame") is not None:
                    renpy.hide_screen("enemimage_frame")
                    _hl_log("SOUND: hid the game's own sound screen during the idle loop")
            except Exception:
                pass
            if now < hl_snd["next"] or now < hl_snd.get("busy", 0.0):
                return
            ev = hl_snd["events"]
            i = hl_snd["idx"]
            name = random.choice(ev[i][1])
            path = "/audio/sound/" + name + ".mp3"
            dur = _hl_mp3_len(path)
            _hl_vol_lower()
            renpy.music.play(path, channel="audio")
            hl_snd["name"] = name
            hl_snd["last"] = now
            # not again until it has ended (+ a third of a second)
            hl_snd["busy"] = now + (dur if dur else 1.5) + 0.33
            if hl_snd.get("logged", 0) < 12:
                hl_snd["logged"] = hl_snd.get("logged", 0) + 1
                _hl_log("SOUND play %s (%.2fs)" % (name, dur or -1.0))
            # next event; if we were late (the sound was still playing) shift the whole schedule
            late = max(0.0, now - hl_snd["next"])
            hl_snd["base"] += late
            i += 1
            if i >= len(ev):
                i = 0
                hl_snd["base"] += hl_snd["cycle"]
            hl_snd["idx"] = i
            hl_snd["next"] = hl_snd["base"] + ev[i][0]

        _hl_recent = []                # last few enemimage calls (for the freeze report)
        _hl_tickstate = {"last": 0.0, "n": 0}

        def _hl_event(txt):
            _hl_recent.append((time.time(), txt))
            del _hl_recent[:-8]

        def _hl_cache_info():
            try:
                c = renpy.display.im.cache
                parts = []
                for k, v in sorted(vars(c).items()):
                    if isinstance(v, bool):
                        continue
                    if isinstance(v, (int, float)):
                        parts.append("%s=%g" % (k, v))
                    elif isinstance(v, (_bt.dict, _bt.list, _bt.set)):
                        parts.append("%s=n%d" % (k, len(v)))
                return "cache[%s] cfgMB=%s vram=%s" % (", ".join(parts), getattr(config, "image_cache_size_mb", None), getattr(persistent, "vram_usage", None))
            except Exception as e:
                return "cache=? %r" % (e,)

        def _hl_watch():
            # the periodic callbacks stop while the game is busy: a long gap = a freeze.  Log it with what happened just before.
            now = time.time()
            gap = now - _hl_tickstate["last"] if _hl_tickstate["last"] else 0.0
            _hl_tickstate["last"] = now
            if gap > 0.7 and gap < 30 and is_battle_in_session():
                ev = " | ".join("%+.1fs %s" % (t - now, x) for t, x in _hl_recent[-6:])
                mine = HL_ADAPTIVE and hl_state.get("changed", 0.0) > now - gap - 0.6
                _hl_log("FREEZE %.2fs%s  %s  recent: %s" % (gap, " (right after the loop changed animation)" if mine else "", _hl_cache_info(), ev))
                if mine and not hl_state.get("swap_off"):
                    hl_state["swap_off"] = True
                    _hl_log("LOOP: no more animation changes for the rest of this fight (changing froze the game)")

        def _hl_call_orig(label, **p):
            t0 = time.time()
            r = _hl_orig_enemimage(**p)
            dt = time.time() - t0
            if dt > HL_SLOW_LOG:
                _hl_log("SLOW %.2fs in the game's enemimage (%s, %s)" % (dt, label, p.get("img_name")))
            return r

        def _hl_g(name, default=None):
            return getattr(store, name, default)

        def _hl_name(e):
            try:
                return e.get_name()
            except Exception:
                return str(e)

        def _hl_idle_names(enemy):
            base = enemy.get_image()
            names = set(["", base])
            try:
                for grab in get_all_grabbed_areas(enemy):
                    if grab in grab_dict_list():
                        d = grab_dict_get(grab, 5)
                        if "newimage" in d:
                            names.add(base + d["newimage"])
            except Exception:
                pass
            return names

        def _hl_entry_valid(mem, enemy):
            g = mem["grabber"]
            if g is None or mem["area"] is None:
                return False
            if enemy_get_defeated(g) or enemy_get_hp_perc(g) <= 0.0:
                return False
            if where_grab_who(enemy, g) != mem["area"]:
                return False
            return True

        def _hl_valid_pool(enemy):
            # drops entries that are no longer valid and returns the rest
            global hl_pool
            if not is_battle_in_session() or enemy_has_status(enemy, s_climax) or enemy_has_status(enemy, s_climaxcum):
                if hl_pool:
                    _hl_log("STOP loop (battle over / climax)")
                hl_pool = []
                if not is_battle_in_session():
                    hl_state["swap_off"] = False
                return []
            keep = []
            for m in hl_pool:
                if _hl_entry_valid(m, enemy):
                    keep.append(m)
                else:
                    _hl_log("DROP %s from pool (%s no longer grabbing)" % (m["img"], _hl_name(m["grabber"])))
            hl_pool = keep
            return keep

        def _hl_pick(pool, avoid=None):
            cands = [m for m in pool if m is not avoid] or pool
            return random.choice(cands)

        def _hl_schedule_swap():
            lo, hi = HL_SWAP_SECONDS
            hl_state["next"] = time.time() + (random.uniform(lo, hi) if hi > 0 else 1e12)

        _hl_orig_enemimage = enemimage
        _hl_sig = inspect.signature(_hl_orig_enemimage)

        def _hl_fallback_sounds(img, enemy):
            # moves without a frame-synced sound list play a single "sound|xxx" when they start: repeat that once per loop instead
            try:
                names = []
                seq = _hl_g("e_attack_animation") or []
                for a in seq:
                    if isinstance(a, str) and a.startswith("sound|"):
                        n = a.split("|", 1)[1]
                        names.extend(n.split("-") if "-" in n else [n])
                        break
                if not names:
                    _hl_log("no sound in the move's animation list for %s: %r" % (img, list(seq)[:8]))
                    return []
                total = 0
                try:
                    dims = get_character_dimensions_from_file(img_name=img, enemy=enemy, update_if_not_found=True)
                    total = int(dims[2]) if dims and len(dims) > 2 and dims[2] else 0
                except Exception as e:
                    _hl_log("frame count lookup failed for %s %r" % (img, e))
                if total < 1:
                    total = 8
                    _hl_log("frame count unknown for %s: assuming %d" % (img, total))
                return [(0, total, names)]
            except Exception as e:
                _hl_log("fallback sound failed %r" % (e,))
                return []

        def _hl_apply(p, mem, enemy, ctrl):
            delay = int(mem["base_delay"] * (_hl_g("arousal_speed", 1.0) if mem.get("arousal", True) else 1.0))
            p["img_name"] = mem["img"]
            p["delay"] = max(delay, 10)
            p["delay_list"] = list(mem["delay_list"])
            p["loop"] = True
            p["swing"] = mem["reverse"]
            p["effect"] = char_pos(ctrl.mod_pos()) if mem["nostruggle"] else struggle(ctrl.mod_pos())
            p["dimensions"] = enemy_get_dimensions(inenemy=enemy, img_name=mem["img"])
            p["sound_animation_frame_list"] = []          # the game's own sound screen is NOT used in the idle loop (it restarted/overlapped); see hl_snd
            if mem is not hl_snd["mem"] or not hl_snd["on"]:
                _hl_snd_start(mem, p["delay"])
            p["control"] = ctrl
            return p

        def enemimage(*args, **kwargs):
            global hl_pool
            try:
                if HL_LOOP_ENABLED:
                    ba = _hl_sig.bind(*args, **kwargs)
                    ba.apply_defaults()
                    p = ba.arguments
                    enemy = p.get("enemy")
                    img = p.get("img_name")
                    _hl_event("%s:%s" % ("player" if enemy is get_enemy_player() else _hl_name(enemy), img))
                    if enemy is not None and enemy is not get_enemy_player() and _hl_vol["on"]:
                        if _hl_g("active_enemy") is not get_enemy_player():
                            _hl_snd_stop()
                            _hl_vol_restore()            # a monster's turn: sounds back to normal
                    if enemy is not None and enemy is get_enemy_player():
                        ex = _hl_g("e_attackextra")
                        props = _hl_g("e_attackproperties")
                        hl_state["active"] = False
                        # ---- record / clear when the game plays a player_anim on the player
                        if (isinstance(ex, _bt.dict) and "player_anim" in ex and img == ex["player_anim"]
                                and _hl_g("computers_target") is enemy and is_battle_in_session()):
                            grabber = _hl_g("active_enemy")
                            molest = props is not None and "arousalspeed" in props
                            base_delay = ex.get("player_anim_delay", 100)
                            # loopable = a grab action that really animates: molesting, or e.g. a blowjob / kiss.
                            # Strips use the same pictures but with a huge delay (a still frame): they are not looped.
                            loopable = base_delay < 3000 and (molest or "t_must_begrabbed" in ex)
                            if loopable:
                                # same monster + same animation: replace;  its other animations stay in the pool
                                hl_pool = [m for m in hl_pool if not (m["grabber"] is grabber and m["img"] == img)]
                            else:
                                hl_pool = [m for m in hl_pool if m["grabber"] is not grabber]
                            if loopable:
                                area = where_grab_who(enemy, grabber) if grabber is not None else None
                                snd = list(ex.get("player_sound_animation_frame_list", []) or [])
                                if not snd:
                                    snd = _hl_fallback_sounds(img, enemy)
                                hl_pool.append({
                                    "img": img, "base_delay": base_delay, "arousal": molest,
                                    "delay_list": list(ex.get("player_anim_delay_list", []) or []),
                                    "reverse": "reverse_anim" in props, "nostruggle": "player_anim_nostruggle" in props,
                                    "sounds": snd,
                                    "grabber": grabber, "area": area,
                                })
                                _hl_log("RECORD %s grabber=%s area=%s sounds=%d%s (pool size %d)" % (img, _hl_name(grabber), area, len(snd), "" if molest else " [not a molest move]", len(hl_pool)))
                            else:
                                _hl_log("CLEAR %s's entries (not a loop animation: %s, delay %s)" % (_hl_name(grabber), img, base_delay))
                        # ---- replay a random pool entry instead of the still image
                        elif hl_pool and img in _hl_idle_names(enemy):
                            pool = _hl_valid_pool(enemy)
                            if pool:
                                ctrl = p.get("control") or find_screen_controller(enemy)
                                if ctrl is not None:
                                    cur = hl_state["current"]
                                    quick = cur in pool and time.time() - hl_state.get("replayed", 0.0) < 1.0
                                    if quick or (cur in pool and hl_state.get("swap_off")):
                                        mem = cur        # the game refreshes the image several times in a row: don't re-pick each time
                                    else:
                                        mem = _hl_pick(pool, cur)
                                    if mem is not cur:
                                        hl_state["changed"] = time.time()
                                    hl_state["replayed"] = time.time()
                                    hl_state["current"] = mem
                                    hl_state["active"] = True
                                    _hl_schedule_swap()
                                    if not quick:
                                        _hl_log("REPLAY %s (%s)  pool=%d sounds=%d" % (mem["img"], _hl_name(mem["grabber"]), len(pool), len(mem["sounds"])))
                                    return _hl_call_orig("replay", **_hl_apply(p, mem, enemy, ctrl))
            except Exception as e:
                _hl_log("ERROR %r" % (e,))
            try:
                _hl_snd_stop()                       # anything but a loop refresh = not idle: cut the idle sound, volume back to normal
                _hl_vol_restore()
            except Exception:
                pass
            t0 = time.time()
            r = _hl_orig_enemimage(*args, **kwargs)
            dt = time.time() - t0
            if dt > HL_SLOW_LOG:
                _hl_log("SLOW %.2fs in the game's enemimage (normal call, %s)" % (dt, kwargs.get("img_name", args[1] if len(args) > 1 else "?")))
            return r

        def _hl_tick():
            # while she is idle in a loop and there are several animations in the pool, switch to another one now and then
            try:
                _hl_watch()
                if not is_battle_in_session():
                    hl_state["swap_off"] = False
                if not (HL_LOOP_ENABLED and hl_state["active"]):
                    _hl_snd_stop()
                    if _hl_vol["on"]:
                        _hl_vol_restore()
                    return
                enemy = get_enemy_player()
                if enemy is None or not is_battle_in_session():
                    hl_state["active"] = False
                    _hl_snd_stop()
                    _hl_vol_restore()
                    return
                if _hl_g("active_enemy") is not enemy:
                    # a monster's turn is running: no swapping now (it would load another big sheet in the middle of its action)
                    _hl_snd_stop()
                    _hl_vol_restore()
                    return
                _hl_snd_tick()
                if time.time() < hl_state["next"] or hl_state.get("swap_off"):
                    return
                pool = _hl_valid_pool(enemy)
                if not pool:
                    hl_state["active"] = False
                    return
                _hl_schedule_swap()
                if len(pool) < 2:
                    return
                ctrl = find_screen_controller(enemy)
                if ctrl is None:
                    return
                mem = _hl_pick(pool, hl_state["current"])
                hl_state["current"] = mem
                hl_state["changed"] = time.time()
                full = _hl_sig.bind(enemy=enemy, img_name=mem["img"])
                full.apply_defaults()
                p = _hl_apply(full.arguments, mem, enemy, ctrl)
                _hl_call_orig("swap", **p)
                renpy.restart_interaction()
                _hl_log("SWAP -> %s (%s)" % (mem["img"], _hl_name(mem["grabber"])))
            except Exception as e:
                hl_state["active"] = False
                _hl_log("TICK ERROR %r" % (e,))

        if _hl_tick.__name__ not in [getattr(f, "__name__", "") for f in config.periodic_callbacks]:
            config.periodic_callbacks.append(_hl_tick)
