# nel_taunt.rpy  -  Nel teases the monsters during her auto-battle
#
# While Nel possesses Celica and fights on her own:
#   1. On her turn there is a 1 in 16 chance she TAUNTS: she strikes a teasing pose (turns around and touches her
#      backside / lifts her skirt / fondles herself), says a teasing line, goes back to her stance and ends her turn.
#   2. From then on every monster that can, grabs her on its turn (its own grab moves).  Monsters already holding
#      her molest her (their own animations, sounds and Nel's own reactions) and tear the clothing on that spot in the
#      same turn while there is any left.  Monsters that can't do anything to her just end their turn.
#      Nel lets them (she waits on her turns), and takes no damage while this lasts.
#   3. When she climaxes, the game's own orgasm plays out (her turns pass).  Afterwards, on her turn, she says
#      "That's enough…" and throws every monster off her (always succeeds).  Then the normal auto-battle goes on.
#   4. After that she can't taunt again for her next 3 turns.
#   5. The more she climaxes in a day, the less lust it takes: 100% -> 60% -> 40% -> 30% -> 20% (resets each day).
#   6. While taunting she talks only about 1/3 as much (waiting lines and reactions).  The taunt turn itself has
#      exactly one line: her teasing line.
#   7. While Nel is in control, Celica gets only 50% of the battle XP (Nel does the killing).
#   8. Nel never kills a monster with her first hit on it: that hit leaves it on 1 HP, the next one kills.
#   9. A climax while Nel possesses her raises Nel's body influence on Celica by 0.5 (the game: 10).
# Monsters switched off in the game's preferences (sex monsters) are left alone.
#
# Settings (below): NT_CHANCE, NT_COOLDOWN, NT_MAX_TURNS, NT_TALK, NT_ORGASM_LUST, NT_XP_SHARE.   Debug log: NT_LOG = True -> game/nel_taunt_log.txt
# Testing: in the Ren'Py console (Shift+O) type   nt_force_next()   and her next turn is a taunt.

init 999 python:
    import builtins as _bt     # dict/list in Ren'Py scripts are Ren'Py's own types; check against the real ones
    # only when the shared guard says the game still matches what this mod was made for (tom_mod_guard.rpy)
    if tom_mod_ok('nel_taunt',
                  hooks=['enemy_decides', 'enemy_mod_hp', 'attribute_mod', 'print_reward_message', 'body_influencelvl_mod'],
                  needs=['can_execute_move', 'unpack_move', 'enemy_print_sorted_moves', 'grab_dict_list', 'where_grab_who',
                         'rem_all_grabbers', 'is_battle_in_session', 'enemy_has_status', 'battle_has_battlesex',
                         'enemy_is_hostile', 'get_active_enemy_list', 'clothes_get_equip_level', 'enemimage',
                         'enemy_can_be_targeted', 'is_being_grabbed', 'clothes_get', 'attribute_get',
                         'attribute_get_max_value', 'get_day_num', 'get_total_enemies', 'enemy_get_hp']):
        import os as _nt_os, io as _nt_io, time as _nt_time, random as _nt_random

        # settings: the defaults are the last argument; players change them with the gear in Apex's Modpack Manager
        _nt_set = lambda key, default: tom_setting('nel_taunt', key, default)
        NT_CHANCE = 1.0 / _nt_set('chance', 16)          # chance on each of her turns (1 in 16)
        NT_COOLDOWN = _nt_set('cooldown', 3)             # her turns without a taunt after one ends
        NT_MAX_TURNS = _nt_set('max_turns', 40)          # safety: a taunt ends by itself after this many monster actions on her
        NT_TALK = _nt_set('talk', 33) / 100.0            # while taunting she says something only this often (teasing line, waiting, reactions)
        NT_ORGASM_LUST = [_nt_set('lust_%d' % i, d) for i, d in enumerate([100, 60, 40, 30, 20], 1)]
                                                         # % of the lust bar needed to climax: 1st time today, 2nd, 3rd ...
        NT_XP_SHARE = _nt_set('xp_share', 50) / 100.0 if _nt_set('half_xp', True) else 1.0
                                                         # Celica's share of the battle XP while Nel is in control
        NT_NO_ONE_SHOT = _nt_set('no_one_shot', True)    # her first hit on a monster leaves it on 1 HP
        NT_ORGASM_INFLUENCE = _nt_set('influence', 0.5)  # Nel's body influence gained per climax while she possesses Celica (game: 10)
        NT_LOG = False
        NT_TEST_WEAK = False       # TESTING ONLY: Nel's hits do 1 damage so monsters live long enough to see the taunt
        _NT_DEFAULTS = dict(NT_CHANCE=NT_CHANCE, NT_COOLDOWN=NT_COOLDOWN, NT_MAX_TURNS=NT_MAX_TURNS, NT_TALK=NT_TALK,
                            NT_ORGASM_LUST=list(NT_ORGASM_LUST), NT_XP_SHARE=NT_XP_SHARE, NT_NO_ONE_SHOT=NT_NO_ONE_SHOT,
                            NT_ORGASM_INFLUENCE=NT_ORGASM_INFLUENCE, NT_LOG=NT_LOG, NT_TEST_WEAK=NT_TEST_WEAK)

        def _nt_restore_settings():
            # settings always come from this file, never from a save (a value changed while testing must not stick)
            for k, v in _NT_DEFAULTS.items():
                setattr(store, k, list(v) if isinstance(v, _bt.list) else v)

        if _nt_restore_settings not in config.after_load_callbacks:
            config.after_load_callbacks.append(_nt_restore_settings)

        NT_LINES = [
            "Mmmm… You look like fun. Come here!",
            "Celica's body is all warmed up… and it's all yours. Come and take it~",
            "Why fight when we could play? Come on, I don't bite… much.",
            "Look at this cute little body, just begging to be touched~",
            "I'll even let you go first. Go on… get a good grip.",
            "Don't be shy~ Celica is far too busy to complain right now.",
        ]
        NT_POSE_LINES = {
            "back": ["See something you like? Come and get a closer look~",
                     "All this, and you're just going to stand there…?"],
            "liftskirt": ["Want a peek? Come closer and I'll show you everything~",
                          "Oops~ Did you see that? Want to see more?"],
            "selffondle": ["Mmm… I could use some help with these~",
                           "My hands are getting tired… want a turn?"],
        }
        NT_RELEASE_LINE = "That's enough…"

        def _nt_log(msg):

            tom_mod_log_check('nel_taunt', msg)
            if not NT_LOG:
                return
            try:
                with _nt_io.open(_nt_os.path.join(config.basedir, "game", "nel_taunt_log.txt"), "a", encoding="utf8") as f:
                    f.write(u"%s  %s\n" % (_nt_time.strftime("%H:%M:%S"), msg))
            except Exception:
                pass

        def _nt_state():
            # per battle (battle_temp_vars is emptied by the game at every battle start)
            btv = main_vars.setdefault("battle_temp_vars", {})
            return btv.setdefault("tom_nel_taunt", {"phase": "idle", "cooldown": 0, "turns": 0, "climaxed": False, "force": False})

        def _nt_active():
            try:
                return is_battle_in_session() and enemy_has_status(e_celica, s_possessionnel)
            except Exception:
                return False

        def _nt_effects(eff):
            if eff is None:
                return []
            return [e for e in (eff if isinstance(eff, (_bt.list, _bt.tuple)) else [eff]) if isinstance(e, str)]

        def _nt_monsters():
            out = []
            for m in get_active_enemy_list({"undefeated": True}):
                if m is e_celica or not enemy_is_hostile(m, e_celica):
                    continue
                if not battle_has_battlesex(m) or not enemy_can_be_targeted(intarget=e_celica, inenemy=m):
                    continue
                out.append(m)
            return out

        def _nt_moves(m, kind, area=None):
            """this monster's usable moves on Celica:  kind = grab / molest / strip"""
            out = []
            for mv in enemy_print_sorted_moves(m):
                try:
                    u = unpack_move(mv, m)
                except Exception:
                    continue
                if u[2] is None:
                    continue
                effs, extra = _nt_effects(u[6]), u[15] or {}
                if kind == "grab":
                    ok = any(e in grab_dict_list() for e in effs)
                elif kind == "molest":
                    ok = (any(e.startswith(("molest", "fondle", "kiss")) for e in effs) or "arousalspeed" in (u[8] or [])) \
                         and not any(e.startswith("strip") for e in effs) and "t_must_begrabbed" in extra
                else:
                    ok = any(e.startswith("strip") for e in effs)
                if not ok:
                    continue
                try:
                    if not can_execute_move(m, e_celica, u):
                        continue
                except Exception:
                    continue
                out.append(u)
            return out

        def _nt_as_decision(u, tear_area=None):
            """unpacked move -> what enemy_decides returns (17 values, target last).  Optional tear after the molest."""
            order_id, attackid, name, anim, dmg, eff, typ, props, mp, cdr, cd, lvl, mlvl, img, extra, desc = u[1:]
            mute = _nt_state().get("mute_reactions") or not _nt_talks()
            if extra and "target_say" in extra and mute:
                extra = dict(extra)
                del extra["target_say"]                      # Nel's reaction line only now and then
            if tear_area:
                anim = list(anim) + ["sound|rip_cloth"] + ([] if "add_enemy_effect" in anim else ["add_enemy_effect"]) \
                       + ["calllabel|tom_nel_refresh"]
                extra = dict(extra or {})
                extra["extra_remove_clothes"] = [tear_area]
            return (order_id, attackid, name, anim, dmg, eff, typ, props, mp, cdr, cd, lvl, mlvl, img, extra, desc, e_celica)

        def _nt_custom_move(move_id, name, label):
            return (0, move_id, name, ["calllabel|" + label], 0, None, "Normal", ["battleonly", "unconfusable"],
                    0, 0, 0, 0, 0, "ICON/unknown.png", {}, "", e_celica)

        def _nt_pass(quiet_ok=False):
            # "pass_turn" lets Nel say one of her waiting lines; "wait" passes silently
            store.player_action = "wait" if (quiet_ok and _nt_random.random() >= NT_TALK) else "pass_turn"
            return (None,) * 17

        def _nt_talks():
            return _nt_random.random() < NT_TALK

        def _nt_anyone_can_play():
            return any(_nt_moves(m, "grab") or where_grab_who(e_celica, m) for m in _nt_monsters())

        def _nt_nel_turn(st):
            st["mute_reactions"] = False
            if enemy_has_status(e_celica, s_climax):
                st["climaxed"] = True
            if st["phase"] == "idle":
                if st["cooldown"] > 0:
                    st["cooldown"] -= 1
                    return None
                force = main_vars.get("tom_nel_taunt_force", False)
                if (force or _nt_random.random() < NT_CHANCE) and _nt_anyone_can_play():
                    main_vars["tom_nel_taunt_force"] = False
                    _nt_log("TAUNT")
                    return _nt_custom_move("_tom_taunt", "Taunt", "tom_nel_taunt")
                return None
            # taunting / climaxing: let them play
            _nt_log("  Nel's turn: lust %.1f" % attribute_get(a_lust))
            if enemy_has_status(e_celica, s_climax):
                return _nt_pass(quiet_ok=True)
            if st["climaxed"] or st["turns"] > NT_MAX_TURNS or not _nt_anyone_can_play():
                _nt_log("RELEASE (climaxed=%s monster actions=%d)" % (st["climaxed"], st["turns"]))
                return _nt_custom_move("_tom_release", "Enough", "tom_nel_release")
            return _nt_pass(quiet_ok=True)

        def _nt_monster_turn(st, m):
            if m not in _nt_monsters():
                return None
            st["turns"] += 1                                  # monster actions during this taunt (safety cap)
            area = where_grab_who(e_celica, m)
            if not area:
                g = _nt_moves(m, "grab")
                if g:
                    u = _nt_random.choice(g)
                    _nt_log("%s grabs (%s)" % (m.get_name(), u[2]))
                    return _nt_as_decision(u)
                _nt_log("%s can't grab: ends turn" % m.get_name())
                return _nt_pass()
            spot = "top" if "top" in area else "bottom" if "bottom" in area else None
            mol = _nt_moves(m, "molest")
            if mol:
                u = _nt_random.choice(mol)
                tear = spot if (spot and clothes_get_equip_level(spot) != -1) else None
                _nt_log("%s molests %s (%s)%s" % (m.get_name(), area, u[2], " + tears " + tear if tear else ""))
                return _nt_as_decision(u, tear)
            strip = _nt_moves(m, "strip")
            if strip:
                return _nt_as_decision(_nt_random.choice(strip))
            return _nt_pass()

        _nt_orig_enemy_decides = enemy_decides

        def enemy_decides(in_enemy=None, overide_move_list=[], in_target_list=None, flags={}):
            try:
                if _nt_active() and not overide_move_list and in_target_list is None:
                    st = _nt_state()
                    if in_enemy is e_celica:
                        r = _nt_nel_turn(st)
                        if r is not None:
                            return r
                    elif st["phase"] != "idle":
                        if enemy_has_status(e_celica, s_climax):
                            st["climaxed"] = True
                        r = _nt_monster_turn(st, in_enemy)
                        if r is not None:
                            return r
            except Exception as e:
                _nt_log("ERROR %r" % (e,))
            return _nt_orig_enemy_decides(in_enemy, overide_move_list, in_target_list, flags)

        _nt_orig_enemy_mod_hp = enemy_mod_hp

        def enemy_mod_hp(in_enemy=None, in_var=0):
            # no damage to Nel/Celica while she is teasing, being played with or climaxing
            try:
                if NT_NO_ONE_SHOT and in_var < 0 and in_enemy is not e_celica and _nt_active()                         and getattr(store, "active_enemy", None) is e_celica and enemy_is_hostile(in_enemy, e_celica):
                    hit = _nt_state().setdefault("hit_once", [])
                    if in_enemy not in hit:
                        hit.append(in_enemy)
                        hp = enemy_get_hp(in_enemy)
                        if hp + in_var <= 0:
                            _nt_log("first hit on %s: %s -> leaves 1 HP" % (in_enemy.get_name(), in_var))
                            in_var = -(hp - 1)
                            if in_var == 0:
                                return
                if NT_TEST_WEAK and in_var < 0 and in_enemy is not e_celica and _nt_active()                         and getattr(store, "active_enemy", None) is e_celica:
                    in_var = -1                              # testing: Nel's attacks barely hurt
                if in_var < 0 and in_enemy is e_celica and _nt_active() and _nt_state()["phase"] != "idle":
                    _nt_log("blocked %s damage" % in_var)
                    return
            except Exception:
                pass
            return _nt_orig_enemy_mod_hp(in_enemy, in_var)

        def _nt_day():
            d = main_vars.setdefault("tom_nel_taunt_day", {"day": None, "orgasms": 0})
            if d["day"] != int(get_day_num()):
                d.update(day=int(get_day_num()), orgasms=0)
            return d

        def _nt_threshold():
            n = _nt_day()["orgasms"]
            return NT_ORGASM_LUST[min(n, len(NT_ORGASM_LUST) - 1)]

        _nt_orig_attribute_mod = attribute_mod

        def attribute_mod(in_attribute=None, value=None):
            # later climaxes of the day need less lust: reaching the (lower) threshold fills the bar -> the game's climax
            try:
                if in_attribute is a_lust and value and value > 0 and _nt_active() and not enemy_has_status(e_celica, s_climax):
                    pct = _nt_threshold()
                    if pct < 100:
                        cur, mx = attribute_get(a_lust), attribute_get_max_value(a_lust)
                        if cur + value >= mx * pct / 100.0:
                            _nt_log("lust %.0f + %.0f reaches today's %d%% threshold -> climax" % (cur, value, pct))
                            value = mx - cur
            except Exception as e:
                _nt_log("attribute_mod error %r" % (e,))
            return _nt_orig_attribute_mod(in_attribute, value)

        _nt_orig_body_influencelvl_mod = body_influencelvl_mod

        def body_influencelvl_mod(victim=None, enemy=None, value=0, flags={}):
            # the game adds 10 influence to the possessor when the possessed body climaxes; for Nel make it 0.5
            try:
                if value == 10 and enemy is e_ghost and victim is e_celica and enemy_has_status(e_celica, s_possessionnel)                         and enemy_has_status(e_celica, s_climax):
                    _nt_log("climax body influence 10 -> %s" % NT_ORGASM_INFLUENCE)
                    value = NT_ORGASM_INFLUENCE
            except Exception:
                pass
            return _nt_orig_body_influencelvl_mod(victim, enemy, value, flags)

        _nt_orig_print_reward_message = print_reward_message

        def print_reward_message(in_dictionary, in_bonus_dictionary):
            # battle won while Nel is in control: Celica only gets her share of the XP (shown and paid)
            try:
                if _nt_active() and get_total_enemies() <= 0 and i_xp in in_dictionary:
                    btv = main_vars.setdefault("battle_temp_vars", {})
                    if not btv.get("tom_xp_shared"):
                        btv["tom_xp_shared"] = True
                        in_dictionary[i_xp] = int(round(in_dictionary[i_xp] * NT_XP_SHARE))
                        if i_xp in in_bonus_dictionary:
                            in_bonus_dictionary[i_xp] = int(round(in_bonus_dictionary[i_xp] * NT_XP_SHARE))
                        _nt_log("XP share: %s" % in_dictionary[i_xp])
            except Exception as e:
                _nt_log("XP share error %r" % (e,))
            return _nt_orig_print_reward_message(in_dictionary, in_bonus_dictionary)

        def _nt_mood(pose, want):
            """a mood whose face picture exists for this pose.  While Nel has the body the game looks for
            <pose>_nelpossessed_face_<mood> (only 'normal' exists for most poses) and, unlike other faces, does not
            fall back to 'normal' by itself - a missing one draws her with no face at all"""
            try:
                prefix = ""
                try:
                    prefix = str(s_possessionnel.extra.get("prefixstr", "")) if enemy_has_status(e_celica, s_possessionnel) else ""
                except Exception:
                    prefix = "_nelpossessed"
                files = [f for f in list_files_containing("/" + pose + prefix + "_face_") if f.startswith("images/CHAR/")]
                for m in (want, "normal"):
                    if any(("%s_face_%s-" % (prefix, m)) in f or ("%s_face_%s_talk-" % (prefix, m)) in f for f in files):
                        if m != want:
                            tom_mod_error("nel_taunt", "no '%s' face for %s%s - using normal" % (want, pose, prefix))
                        return m
            except Exception as e:
                tom_mod_error("nel_taunt", "checking the face for " + pose, e)
            return "normal"

        def nt_force_next():
            """console helper: her next possible turn is a taunt (kept until it happens, across battles)"""
            main_vars["tom_nel_taunt_force"] = True
            if is_battle_in_session():
                _nt_state()["cooldown"] = 0
            return "Nel will taunt on her next turn where a monster can grab her"

        def _nt_report(event):
            f = getattr(store, "apex_nr_event", None)       # Nel's Battle Report, when it is on
            if f is not None:
                f(event)

        def _nt_begin():
            _nt_report("taunt")
            st = _nt_state()
            st.update(phase="taunt", turns=0, climaxed=False)

        def _nt_end():
            st = _nt_state()
            if st.get("climaxed"):
                _nt_report("climax")
                _nt_day()["orgasms"] += 1
                _nt_log("orgasms today: %d -> next climax at %d%% lust" % (_nt_day()["orgasms"], _nt_threshold()))
            st.update(phase="idle", cooldown=NT_COOLDOWN, turns=0, climaxed=False)

        def _nt_pick_pose():
            poses = ["back", "selffondle"]
            if clothes_get("bottom", 1) != "nude":
                poses.append("liftskirt")
            return _nt_random.choice(poses)

        def _nt_taunt_line(pose):
            # the taunt always has its one line - and nothing else is said until her next turn
            _nt_state()["mute_reactions"] = True
            return _nt_line(pose)

        def _nt_line(pose):
            return _nt_random.choice(NT_LINES + NT_POSE_LINES.get(pose, []))


# Nel's taunt: pose + line, back to her stance, end of turn
label tom_nel_taunt:
    $ nt_pose = _nt_pick_pose()
    $ nt_who = e_celica.get_extra("battlesay")
    if nt_pose == "back":
        $ enemimage(e_celica, "celica_back")
        $ scene("mood", e_celica, _nt_mood("celica_back", "grin"))
        $ wait(timeunit(4))
        $ enemimage(e_celica, "celica_back_asstouch")
    elif nt_pose == "liftskirt":
        $ scene("mood", e_celica, _nt_mood("celica_liftskirt", "liftskirtgrin"))
        $ enemimage(e_celica, "celica_liftskirt")
    else:
        $ scene("mood", e_celica, _nt_mood("celica_selffondlebreasts", "aroused"))
        $ enemimage(e_celica, "celica_selffondlebreasts", delay=110)
    $ nt_text = _nt_taunt_line(nt_pose)
    if nt_text:
        $ renpy.say(nt_who, nt_text + "{w=2}{nw}")
    else:
        $ wait(timeunit(15))
    $ wait(timeunit(4))
    $ enemimage(e_celica)
    $ scene("mood", e_celica, get_npc_default_mood(e_celica))
    $ _nt_begin()
    $ del nt_pose, nt_who, nt_text
    return

# after her climax: "That's enough…" and every monster is thrown off (always works)
label tom_nel_release:
    $ nt_who = e_celica.get_extra("battlesay")
    $ scene("mood", e_celica, sayer_get_struggle_mood(e_celica))
    $ renpy.say(nt_who, NT_RELEASE_LINE + "{w=1}{nw}")
    if is_being_grabbed(e_celica):
        $ rem_all_grabbers(e_celica)
        $ renpy.play("/audio/sound/jab.mp3")
    $ _nt_end()
    call battle_refresh_character_animation ("all")
    $ scene("mood", e_celica, get_npc_default_mood(e_celica))
    $ del nt_who
    return

# a torn clothing layer shows right away
label tom_nel_refresh:
    call battle_refresh_character_animation (e_celica)
    return
