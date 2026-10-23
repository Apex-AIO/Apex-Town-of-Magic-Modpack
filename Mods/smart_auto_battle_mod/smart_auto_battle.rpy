# smart_auto_battle.rpy  -  Celica's Smart Auto Battle
#
# A button under the Attributes frame ("Auto Battle Mode: On/Off", shown while Explore is available, or while the mode is
# on) lets Celica explore and fight by herself:
#   * in a fight the game's own computer-control is used (the same one Nel's auto-battle uses): enemy_decides(e_celica) is
#     answered by this mod.  Target = the foe with the least HP (all equal: random, then kept until it falls); spell = the one
#     with the best expected damage against that foe (the game's own damage formulas: element table, weakness / strength
#     list, level, arcane), never counting damage beyond what the foe has left; a spell that kills is the cheapest one that
#     does.  Cooldowns, MP and other rules come from the game itself (enemy_decides_append_move).
#   * struggling only when every living foe holds Celica, or nothing castable is left.
#   * potions: Health under a HP limit, Magic when MP runs out, Cleanse / Anti-potions for bad statuses.
#   * out of a fight: crafts the potions it needs (stock + what this region's monsters can inflict), uses potions, presses
#     Explore, clicks through dialogs and "you got" windows.  Stops when Explore is not offered any more (energy 0 ...),
#     when something needs a decision, when health is low and no potion is left, or when it is stuck.
#   * Nel's Battle Report (nel_report) records everything and opens when the mode ends.
# The player can switch it off at any moment, also in the middle of a fight.
#
# Nothing of the game is changed in what it does: two game functions are wrapped (enemy_is_playable, enemy_decides).
# Spec: SPEC.md

init 998 python:
    # the guard looks at the game's functions as they are NOW: this runs before Nel's Auto Battler (999) wraps enemy_decides
    SA_OK = tom_mod_ok('smart_auto',
                  hooks=['enemy_is_playable', 'enemy_decides'],
                  needs=['enemy_decides_append_move', 'enemy_print_sorted_moves', 'unpack_move', 'is_move_offensive',
                         'enemy_get_attack_lvl_dmg', 'element_dmg_multiplier', 'dmg_weakness_multiplier', 'dmg_arcane_bonus',
                         'enemy_get_element_list', 'enemy_get_level', 'enemy_get_hp', 'enemy_get_hp_perc', 'enemy_get_mp_perc',
                         'get_active_enemy_list', 'enemy_is_hostile', 'enemy_can_be_targeted', 'is_battle_in_session',
                         'is_being_grabbed', 'is_enemy_grabbing', 'enemy_has_boundstatus', 'enemy_has_status',
                         'enemy_get_cleansable_bad_status_list', 'count_item', 'craft_formula',
                         'get_location_enemies', 'refresh_action_btns', 'is_menu_enabled', 'scene',
                         'get_enemy_player', 'attribute_get', 'equip_procedure', 'get_location',
                         'refresh_gui_screen', 'get_random_list_element', 'Status', 'Item'])

# ... and this wraps it AFTER Nel's Auto Battler has (so Nel's own turns are passed to her code untouched)
init 1000 python:
    if SA_OK:
        import builtins as _sa_bt, time as _sa_time, random as _sa_random

        SA_HP_LIMIT = tom_setting('smart_auto', 'potion_hp', 35)         # % of health: drink a Health Potion below this
        SA_HP_STOCK, SA_MP_STOCK = 1, 2                                   # exactly this many Health / Magic potions are kept in the bag (never more)
        SA_USE_POTIONS = tom_setting('smart_auto', 'use_potions', True)
        SA_CRAFT = tom_setting('smart_auto', 'craft', True)
        SA_LOG = False

        SA = _sa_bt.dict(on=False, since=0.0, tick=0.0, progress=0.0, jump=False, report=False, gone=0)
        _SA_STOP_AFTER_STUCK = 90.0
        _SA_TICK = 0.4
        _SA_GRACE = 6.0                           # seconds after the last fight tick in which end-of-fight windows are clicked through
        _SA_NONE = (None,) * 17
        APEX_NR_IGNORE = False                    # nel_report: do not count what the mod crafts as "loot"

        def _sa_log(msg):
            tom_mod_log_check('smart_auto', msg)
            if not SA_LOG:
                return
            try:
                import os as _o, io as _io
                with _io.open(_o.path.join(config.basedir, "game", "smart_auto_log.txt"), "a", encoding="utf8") as f:
                    f.write(u"%s  %s\n" % (_sa_time.strftime("%H:%M:%S"), msg))
            except Exception:
                pass

        # ------------------------------------------------------------------ state
        def apex_auto_active():
            return bool(SA["on"])

        def _sa_nel():
            try:
                return enemy_has_status(e_celica, s_possessionnel)
            except Exception:
                return False

        def _sa_cpu_turn():
            """Celica is computer-controlled right now (mode on, a fight, Nel not in control)"""
            try:
                return bool(SA["on"]) and is_battle_in_session() and get_enemy_player() is e_celica and not _sa_nel()
            except Exception:
                return False

        def _sa_explore_button():
            try:
                for b in action_btn_list.print_sorted_list():
                    if b.get_text() == "<<Explore>>":
                        return b
            except Exception:
                pass
            return None

        def _sa_blocked():
            """a window of the game is open over the main screen (shop, Equip, map, a question ...)"""
            f = getattr(store, "apex_ui_blocked", None)
            if f is not None:
                return f()
            for n in ("select_item_frame", "confirm_frame", "shopmenu_frame", "fusemenu_frame", "book_frame", "map_frame", "setup_frame"):
                if renpy.get_screen(n) is not None:
                    return True
            return False

        def apex_auto_btn_visible():
            try:
                if store._menu or store.main_menu or renpy.get_screen("action_frame") is None:
                    return False
                if flag_list.has("enable_event_viewer") or get_enemy_player() is not e_celica or _sa_nel():
                    return False
                if SA["on"]:
                    return not _sa_blocked() or is_battle_in_session()
                return _sa_explore_button() is not None and not is_battle_in_session() and not _sa_blocked()
            except Exception:
                return False

        def apex_auto_toggle():
            if SA["on"]:
                _sa_stop("switched off")
            else:
                if _sa_explore_button() is None:
                    return
                SA.update(on=True, since=_sa_time.time(), progress=_sa_time.time(), tick=0.0, jump=False, report=True, snap=None, same=0, gone=0, grace=_sa_time.time())
                try:
                    nr = getattr(store, "_nr_rec", None)
                    if nr is not None:
                        nr()
                except Exception as e:
                    tom_mod_error("smart_auto", "starting the report", e)
                if is_battle_in_session():
                    SA["jump"] = True             # it is Celica's own turn right now: hand it over
                renpy.notify("Auto Battle Mode: On")
            renpy.restart_interaction()

        def _sa_stop(why):
            was = SA["on"]
            SA["on"] = False
            SA["jump"] = False
            if why == "Nel took over":
                SA["report"] = False                  # the record goes on as Nel's: her own report opens when she leaves
            _sa_log("STOP: " + why)
            if was:
                renpy.notify("Auto Battle Mode: Off (%s)" % why if why != "switched off" else "Auto Battle Mode: Off")
                f = getattr(store, "apex_nr_finish_auto", None)
                if f is not None and SA["report"]:
                    try:
                        f()
                    except Exception as e:
                        tom_mod_error("smart_auto", "opening the report", e)
            SA["report"] = False

        def _sa_after_load():
            SA["on"] = False
            SA["jump"] = False
            SA["report"] = False

        if _sa_after_load not in config.after_load_callbacks:
            config.after_load_callbacks.append(_sa_after_load)

        # ------------------------------------------------------------------ wrapped game functions
        _sa_orig_is_playable = enemy_is_playable

        def enemy_is_playable(enemy=None):
            if enemy is not None and enemy is e_celica and _sa_cpu_turn():
                return False
            return _sa_orig_is_playable(enemy)

        _sa_orig_decides = enemy_decides

        def enemy_decides(in_enemy=None, overide_move_list=[], in_target_list=None, flags={}):
            try:
                if in_enemy is e_celica and not overide_move_list and in_target_list is None and _sa_cpu_turn():
                    r = _sa_decide()
                    if r is not None:
                        return r
            except Exception as e:
                tom_mod_error("smart_auto", "choosing Celica's move", e)
            return _sa_orig_decides(in_enemy, overide_move_list, in_target_list, flags)

        # ------------------------------------------------------------------ fight logic
        def _sa_foes():
            return [m for m in get_active_enemy_list({"undefeated": True})
                    if m is not e_celica and enemy_is_hostile(e_celica, m) and enemy_can_be_targeted(intarget=m)]

        def _sa_item(name):
            return getattr(store, name, None)

        _SA_HEALTH = ("i_health_potion_1", "i_health_potion_2", "i_health_potion_3")
        _SA_MAGIC = ("i_magic_potion_1", "i_magic_potion_2", "i_magic_potion_3")

        def _sa_owned(names):
            return [i for i in (_sa_item(n) for n in names) if i is not None and count_item(i) > 0]

        def _sa_can_use(item):
            # not can_use_item(): that one answers for the player's buttons and says "no" while the computer plays her turn
            try:
                return count_item(item) > 0 and item.get_cooldown() <= 0 and item.has_property("usable")
            except Exception:
                return False

        def _sa_pick_potion(names, missing):
            """the smallest potion that heals what is missing, else the biggest one she has"""
            usable = [i for i in _sa_owned(names) if _sa_can_use(i)]
            if not usable:
                return None
            for i in usable:
                if getattr(i, "value", 0) >= missing:
                    return i
            return usable[-1]

        def _sa_use(item):
            store.player_action = item
            store.players_ally_target = e_celica
            _sa_log("uses " + item.get_name())
            return _SA_NONE

        def _sa_anti_item(status):
            """the Anti-potion for a status (it gives the "<status> Immunity" buff when drunk), or None"""
            want = status.get_name() + " Immunity"
            for it in all_items.print_list():
                try:
                    a = getattr(it, "attribute", None)
                    if it.get_type() == "Potion" and isinstance(a, Status) and a.get_name() == want:
                        return it
                except Exception:
                    pass
            return None

        def _sa_anti_for(status):
            """an Anti-potion she owns for this status and is not protected by yet"""
            it = _sa_anti_item(status)
            if it is not None and _sa_can_use(it) and not enemy_has_status(e_celica, it.attribute):
                return it
            return None

        def _sa_expected(dec, foes):
            """expected damage of one decision (a move on its target) with the game's own formulas; area moves: all foes"""
            props = dec[7] or []
            base = dec[4]
            if not base or base <= 0:
                return 0.0
            me = enemy_get_level(e_celica)
            targets = foes if "multiple_targets" in props else [dec[16]]
            total = 0.0
            for t in targets:
                d = enemy_get_attack_lvl_dmg(base, me, enemy_get_level(t), dec[11], dec[12], props, dec[14] or {})
                d = d * element_dmg_multiplier(props, enemy_get_element_list(t)) * dmg_weakness_multiplier(t, props)
                d = d + dmg_arcane_bonus(d)
                total += min(d, enemy_get_hp(t))
            return total

        def _sa_focus(foes):
            btv = main_vars.setdefault("battle_temp_vars", {})
            low = min(enemy_get_hp(m) for m in foes)
            lows = [m for m in foes if enemy_get_hp(m) == low]
            keep = btv.get("sa_focus")
            if keep in lows:
                return keep
            f = _sa_random.choice(lows)
            btv["sa_focus"] = f
            return f

        def _sa_candidates(moves, target):
            out = []
            for mv in moves:
                if isinstance(mv, str) or all_items.in_list(mv):
                    continue
                try:
                    if not is_move_offensive(mv):
                        continue
                    c = enemy_decides_append_move(e_celica, target, mv)
                except Exception:
                    c = None
                if c:
                    out.append(c[0])
            return out

        def _sa_support(moves):
            """non-offensive moves she can use on herself (Cleanse)"""
            out = []
            for mv in moves:
                if isinstance(mv, str) or all_items.in_list(mv):
                    continue
                try:
                    if is_move_offensive(mv):
                        continue
                    c = enemy_decides_append_move(e_celica, e_celica, mv)
                except Exception:
                    c = None
                if c:
                    out.append(c[0])
            return out

        def _sa_struggle():
            if enemy_has_boundstatus(e_celica) and e_celica.is_status_normal():
                _sa_log("struggles (bound)")
                store.player_action = "unbound_status"
                return _SA_NONE
            if is_being_grabbed(e_celica):
                _sa_log("struggles (grabbed)")
                store.player_action = "unbound_grab"
                return _SA_NONE
            return None

        def _sa_living():
            """every living monster, also the ones holding her (those can't be targeted while they do)"""
            return [m for m in get_active_enemy_list({"undefeated": True}) if m is not e_celica and enemy_is_hostile(e_celica, m)]

        def _sa_decide():
            foes = _sa_foes()
            living = _sa_living()
            # held by every monster there is: struggle (before anything else but an emergency potion)
            all_hold = bool(living) and is_being_grabbed(e_celica) and all(is_enemy_grabbing(m) for m in living)
            if not foes and not all_hold:
                return None                       # the game's own code ends the turn
            hp, mp = enemy_get_hp_perc(e_celica), enemy_get_mp_perc(e_celica)
            moves = list(enemy_print_sorted_moves(e_celica))
            # 1. emergencies
            if SA_USE_POTIONS and hp < SA_HP_LIMIT / 100.0:
                p = _sa_pick_potion(_SA_HEALTH, 1.0 - hp)
                if p is not None:
                    return _sa_use(p)
            bad = enemy_get_cleansable_bad_status_list(e_celica)
            if bad:
                sup = [d for d in _sa_support(moves) if "cleanse" in (d[7] or [])]
                if sup:
                    _sa_log("casts %s against %s" % (sup[0][1], ", ".join(s.get_name() for s in bad)))
                    return sup[0]
                if SA_USE_POTIONS:
                    for st in bad:
                        p = _sa_anti_for(st)
                        if p is not None:
                            return _sa_use(p)
            if SA_USE_POTIONS and mp < 0.12:
                p = _sa_pick_potion(_SA_MAGIC, 1.0 - mp)
                if p is not None:
                    return _sa_use(p)
            # 2. held by everyone: struggle
            if all_hold:
                s = _sa_struggle()
                if s is not None:
                    return s
            if not foes:
                return None
            # losing badly with nothing left to drink: run (random chance, like the player's own Escape)
            if hp < 0.2 and SA_USE_POTIONS and not _sa_owned(_SA_HEALTH) and not is_being_grabbed(e_celica) and e_celica.has_property("canescapebattle"):
                _sa_log("escapes (health %.0f%%, no potion)" % (hp * 100))
                store.player_action = "escape"
                return _SA_NONE
            # 3. the attack
            focus = _sa_focus(foes)
            cands = _sa_candidates(moves, focus)
            best, best_key = None, None
            for d in cands:
                val = _sa_expected(d, foes)
                if val <= 0:
                    continue
                kills = val >= enemy_get_hp(focus) - 0.5 or val >= sum(enemy_get_hp(m) for m in foes) - 0.5
                # a kill first (cheapest in MP), else the most damage (cheapest in MP on a tie)
                key = (1 if kills else 0, -(d[8] or 0) if kills else val, val if kills else -(d[8] or 0))
                if best_key is None or key > best_key:
                    best, best_key = d, key
            if best is not None:
                _sa_log("%s -> %s (%.0f dmg, hp %d)" % (best[1], getattr(focus, "name", "?"), _sa_expected(best, foes), enemy_get_hp(focus)))
                return best
            # 4. nothing castable
            s = _sa_struggle()
            if s is not None:
                return s
            return None                           # the game's own choice (a basic move or a pass)

        # ------------------------------------------------------------------ the driver (between fights, dialogs)
        def _sa_region_statuses(loc):
            """statuses the monsters of this region can inflict (read once per place)"""
            cache = _SA_REGION.setdefault(loc.get_name(), None)
            if cache is not None:
                return cache
            found = []
            try:
                seen = []
                for bv in ("battle_06", "battle_08", "battle_10", "battle_12", "battle_14", "battle_16", "battle_18",
                           "battle_20", "battle_22", "battle_00", "battle_02", "battle_04"):
                    try:
                        lst = get_location_enemies(bv, loc)[0]
                    except Exception:
                        lst = []
                    for m in lst or []:
                        if m not in seen:
                            seen.append(m)
                for m in seen:
                    for mv in enemy_print_sorted_moves(m):
                        if isinstance(mv, str) or all_items.in_list(mv):
                            continue
                        u = unpack_move(mv, m)
                        _sa_scan(u[6], found)
                        _sa_scan((u[15] or {}).get("extra_add_status"), found)
            except Exception as e:
                tom_mod_error("smart_auto", "reading the monsters of this place", e)
            _SA_REGION[loc.get_name()] = found
            return found

        _SA_REGION = {}

        def _sa_scan(obj, out, depth=0):
            if obj is None or depth > 3:
                return
            if isinstance(obj, Status):
                if obj not in out:
                    out.append(obj)
            elif isinstance(obj, (_sa_bt.list, _sa_bt.tuple, _sa_bt.set)):
                for x in obj:
                    _sa_scan(x, out, depth + 1)

        def _sa_formula_for(family):
            best = None
            for f in all_formulas.print_sorted_list():
                try:
                    r = f.get_result()
                    if r in family and f.has_ingredients():
                        if best is None or family.index(r) > family.index(best.get_result()):
                            best = f
                except Exception:
                    pass
            return best

        def _sa_craft():
            """potions for the next fights: stock of Health / Magic, one Anti-potion per status this region can inflict"""
            if not SA_CRAFT:
                return
            # priority: 1. the Anti-potion of every status this region's monsters can inflict (only while its buff is off,
            # so one is crafted again only when the protection has run out), 2. Health, 3. Magic
            families = []
            for st in _sa_region_statuses(get_location()):
                it = _sa_anti_item(st)
                if it is not None and not enemy_has_status(e_celica, it.attribute):
                    families.append(([it], 1))
            families.append(([i for i in (_sa_item(n) for n in _SA_HEALTH) if i], SA_HP_STOCK))
            families.append(([i for i in (_sa_item(n) for n in _SA_MAGIC) if i], SA_MP_STOCK))
            store.APEX_NR_IGNORE = True
            try:
                crafted = 0
                for fam, want in families:
                    while sum(count_item(i) for i in fam) < want and crafted < 8:
                        f = _sa_formula_for(fam)
                        if f is None or not craft_formula(f):
                            break
                        crafted += 1
                        _sa_log("crafted " + f.get_result().get_name())
            finally:
                store.APEX_NR_IGNORE = False

        def _sa_click():
            """one click through a dialog (the "say" window)"""
            sd = renpy.get_screen("say")
            if sd is not None:
                renpy.end_interaction(True)
                return True
            return False

        def _sa_tick():
            try:
                if not SA["on"]:
                    return
                now = _sa_time.time()
                if now - SA["tick"] < _SA_TICK:
                    return
                SA["tick"] = now
                if get_enemy_player() is not e_celica or _sa_nel():
                    _sa_stop("Nel took over")
                    return
                # a window with only an OK button (level up, messages): press it.  Anything with a choice needs the player: stop
                cf = renpy.get_screen("confirm_frame")
                if cf is not None:
                    try:
                        info = not cf.scope.get("cancel_name")
                        acts = cf.scope.get("confirm_action")
                    except Exception:
                        info, acts = False, None
                    if info and acts:
                        SA["progress"] = now
                        renpy.run(acts)
                        renpy.hide_screen("confirm_frame")
                        return
                    if renpy.get_screen("gotitem_frame") is None:
                        _sa_stop("a question needs you")
                        return
                for n in ("choice", "select_item_frame"):
                    if renpy.get_screen(n) is not None:
                        _sa_stop("a question needs you")
                        return
                if renpy.get_screen("gotitem_frame") is not None:
                    renpy.hide_screen("gotitem_frame")
                    SA["progress"] = now
                    return
                if is_battle_in_session():
                    SA["progress"] = now
                    SA["grace"] = now                  # the windows right after a fight (victory text, loot) are part of the fight
                    if SA["jump"] and store.menu_state == "battle" and store.player_action is None and store.active_enemy is e_celica:
                        SA["jump"] = False
                        renpy.jump("battle_enemies.player_decided")      # it was her turn while waiting for the player
                    _sa_click()
                    return
                SA["jump"] = False
                btn = _sa_explore_button()
                menu_free = (is_menu_enabled() and not scene("is_active") and not _sa_blocked()
                             and renpy.get_screen("action_frame") is not None)
                if not menu_free:
                    SA["gone"] = 0
                    # no monsters on screen and no clickable Explore: either the end of a fight (victory text, loot: only for a few
                    # seconds after the last fight tick) or a cut scene / story event.  A cut scene is never clicked through.
                    talking = renpy.get_screen("say") is not None or scene("is_active")
                    # the game names every story scene (current_event_scene); exploring finds ("It's a Spirell Flower!") are named
                    # explore_find_*, and a monster's appearance has no scene name: those belong to exploring, only the rest is a cut scene
                    ces = str(getattr(store, "current_event_scene", "") or "")
                    story = bool(ces) and not ces.startswith("explore_find")
                    if talking and story and now - SA.get("grace", 0) > _SA_GRACE:
                        _sa_log("cut scene: no fight, no Explore, text on screen")
                        _sa_stop("a cut scene started")
                        return
                    if _sa_click():
                        SA["progress"] = now
                    elif now - SA["progress"] > _SA_STOP_AFTER_STUCK:
                        _sa_stop("nothing is happening")
                    return
                if btn is None:
                    SA["gone"] = SA.get("gone", 0) + 1           # the button list is rebuilt now and then: three looks in a row
                    if SA["gone"] >= 3:
                        _sa_stop("Explore is not available any more")
                    return
                SA["gone"] = 0
                SA["progress"] = now
                if not getattr(btn, "sensitive", True):
                    return
                # out of a fight, menu free, Explore offered
                if SA_USE_POTIONS:
                    hp = enemy_get_hp_perc(e_celica)
                    if hp < SA_HP_LIMIT / 100.0 + 0.2:
                        p = _sa_pick_potion(_SA_HEALTH, 1.0 - hp)
                        if p is not None:
                            SA["progress"] = now
                            _sa_log("drinks " + p.get_name())
                            equip_procedure(p, "use")
                            return
                        if hp < SA_HP_LIMIT / 100.0:
                            _sa_stop("health is low and there is no potion")
                            return
                    mp = enemy_get_mp_perc(e_celica)
                    if mp < 0.25:
                        p = _sa_pick_potion(_SA_MAGIC, 1.0 - mp)
                        if p is not None:
                            SA["progress"] = now
                            _sa_log("drinks " + p.get_name())
                            equip_procedure(p, "use")
                            return
                # an Explore that changes nothing (too dark, no time or energy used) must not loop forever
                snap = (round(attribute_get(a_energy), 2), int(get_day_num()), store.day_hour, store.day_min)
                if snap == SA.get("snap"):
                    SA["same"] = SA.get("same", 0) + 1
                    if SA["same"] >= 3:
                        _sa_stop("exploring does nothing here")
                        return
                else:
                    SA["same"] = 0
                SA["snap"] = snap
                _sa_craft()
                if SA_USE_POTIONS:
                    # protection first: the Anti-potion of every status this place can cause, unless its buff is already on
                    for st in _sa_region_statuses(get_location()):
                        p = _sa_anti_for(st)
                        if p is not None:
                            SA["progress"] = now
                            SA["snap"] = None                  # drinking is progress: do not count this round as "nothing changed"
                            _sa_log("drinks " + p.get_name())
                            equip_procedure(p, "use")
                            return
                SA["progress"] = now
                _sa_log("explores")
                renpy.run(btn.action)
            except Exception as e:
                if e.__class__.__module__.startswith("renpy"):
                    raise                              # Ren'Py's own control flow (jump, call, end of interaction): let it through
                tom_mod_error("smart_auto", "the auto-battle driver", e)
                _sa_stop("a problem, see apex_mod_errors.txt")

        # periodic callbacks only: Ren'Py handles a jump / call / end of interaction raised there; an interact callback does not
        if _sa_tick not in config.periodic_callbacks:
            config.periodic_callbacks.append(_sa_tick)
        if "apex_auto_btn" not in config.overlay_screens:
            config.overlay_screens.append("apex_auto_btn")


# the button: dead center under the Attributes / Relations frame
screen apex_auto_btn():
    zorder -17
    # shown screens are saved: with the mod switched off, a loaded save must not crash here
    if hasattr(store, "apex_auto_btn_visible") and apex_auto_btn_visible():
        $ _on = apex_auto_active()
        frame area (32, 421, 204, 24) padding 0,0 background Solid("#000"):
            imagebutton idle CustomBox(color=ColorMain1, xsize=204, ysize=24) hover CustomBox(color=light_color(ColorMain1), xsize=204, ysize=24) action Function(apex_auto_toggle) tooltip ("Celica explores and fights by herself (smart spell choice, focus kill, potions).\nClick again to take control back, also in the middle of a fight." if not _on else "Click to stop and take control back.\nA report opens when it ends.")
            add CustomBox(color=(ColorOK if _on else ColorClick), xsize=203, ysize=23, shapestyle=1, line_size=1)
            text ("Auto Battle Mode: " + ("On" if _on else "Off")) outlines [(absolute(0), "#000", absolute(1), absolute(1))] xalign 0.5 yalign 0.5 size 14 color (ColorOK if _on else "#FFFFFF")
