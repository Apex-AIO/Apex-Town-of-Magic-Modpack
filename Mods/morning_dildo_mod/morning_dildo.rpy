# morning_dildo.rpy  -  sometimes Celica starts her day with the dildo Nel gave her
#
# When Celica wakes up at home and nothing else is planned for the morning (no night/morning visit, no scene the
# game queued for after waking up, nothing scheduled where she is, no possession pending), there is a 1 in 9 chance
# she uses the dildo: the game's own scene plays (with Nel joining in if Nel is in the room, like in the game).
# Only when she has the dildo, it is her own body (not possessed), her Lewdness is at least 30 (the game's own
# rule for using it) and she hasn't used it yet today.
#
# How: the game picks morning scenes in label wake_up (wakeup_event_pick).  When the normal wake-up starts and the
# game picked nothing, this mod may put the dildo scene in that slot - the game then plays it like its own.
#
# Settings: MD_CHANCE, MD_MIN_LEWDNESS.   Debug log: MD_LOG = True -> game/morning_dildo_log.txt

init 999 python:
    # only when the shared guard says the game still matches what this mod was made for (tom_mod_guard.rpy)
    if tom_mod_ok('morning_dildo',
                  hooks=[],
                  needs=['count_item', 'celicavar_get', 'location_is_bed_or_bedroom', 'is_npc_at_location',
                         'enemy_get_possession_status', 'scheduler_location_has_schedule',
                         'scheduler_get_possession_event_scheduled_list', 'fairymode_get', 'succubus_get_twilight',
                         'darkworld_get_enabled', 'attribute_get', 'get_day_num', 'get_enemy_player', 'get_location']):
        import os as _md_os, io as _md_io, time as _md_time, random as _md_random

        # settings (gear in Apex's Modpack Manager); defaults: 1 in 9 mornings, Lewdness 30 (the game's own rule)
        MD_CHANCE = 1.0 / tom_setting('morning_dildo', 'chance', 9)
        MD_MIN_LEWDNESS = tom_setting('morning_dildo', 'min_lewdness', 30)
        MD_LOG = False
        _MD_DEFAULTS = dict(MD_CHANCE=MD_CHANCE, MD_MIN_LEWDNESS=MD_MIN_LEWDNESS, MD_LOG=MD_LOG)

        def _md_restore_settings():
            # settings always come from this file, never from a save (a value changed while testing must not stick)
            for k, v in _MD_DEFAULTS.items():
                setattr(store, k, v)

        if _md_restore_settings not in config.after_load_callbacks:
            config.after_load_callbacks.append(_md_restore_settings)
        MD_LABELS = ("wake_up", "wake_up.normal_wakeup", "event_use_dildo", "event_use_dildo_with_nel")

        def _md_log(msg):
            if not MD_LOG:
                return
            try:
                with _md_io.open(_md_os.path.join(config.basedir, "game", "morning_dildo_log.txt"), "a", encoding="utf8") as f:
                    f.write(u"%s  %s\n" % (_md_time.strftime("%H:%M:%S"), msg))
            except Exception:
                pass

        def _md_why_not():
            """None if the dildo scene may play this morning, otherwise the reason it can't"""
            dildo = getattr(store, "i_dildo", None)
            if dildo is None or count_item(dildo) <= 0:
                return "no dildo"
            if get_enemy_player() is not e_celica or enemy_get_possession_status(e_celica) is not None:
                return "not Celica in her own body"
            if attribute_get(a_lewdness) < MD_MIN_LEWDNESS:
                return "Lewdness below %d" % MD_MIN_LEWDNESS
            if celicavar_get("use_dildo_day") == int(get_day_num()):
                return "already used today"
            if fairymode_get() is not None or succubus_get_twilight() or darkworld_get_enabled():
                return "fairy / twilight / dark world"
            if not location_is_bed_or_bedroom(get_location()):
                return "not in a bed or bedroom"
            if scheduler_location_has_schedule(get_location()):
                return "something is scheduled here"
            if len(scheduler_get_possession_event_scheduled_list()) > 0:
                return "a possession event is scheduled"
            return None

        def _md_on_label(name, abnormal):
            if name != "wake_up.normal_wakeup":
                return
            try:
                if getattr(store, "wakeup_event_pick", "") != "":
                    _md_log("morning: the game already has a scene (%s)" % store.wakeup_event_pick)
                    return
                why = _md_why_not()
                if why:
                    _md_log("morning: no (%s)" % why)
                    return
                if _md_random.random() < MD_CHANCE:
                    store.wakeup_event_pick = "afterwakeup_tom_morning_dildo"     # the game calls events_tom_morning_dildo
                    _md_log("morning: dildo scene!")
                else:
                    _md_log("morning: not today (1 in %d)" % int(round(1 / MD_CHANCE)))
            except Exception as e:
                _md_log("error %r" % (e,))

        if all(renpy.has_label(l) for l in MD_LABELS):
            if _md_on_label not in config.label_callbacks:
                config.label_callbacks.append(_md_on_label)
        else:
            tom_mod_status["morning_dildo"] = "off: game labels changed"


# the game's own dildo scene; with Nel if she is in the room (same rule as using the item)
label events_tom_morning_dildo:
    if is_npc_at_location(e_ghost, get_location()):
        jump event_use_dildo_with_nel
    jump event_use_dildo
