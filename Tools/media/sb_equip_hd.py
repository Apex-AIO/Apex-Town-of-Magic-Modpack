# storyboards: Equip grid scroll + drag ("equip"), then HD toggle ("hd") - run after rec_helpers.py
class _FakeMouse(object):
    @staticmethod
    def get_pressed():
        return (1, 0, 0)
class _FakePg(object):
    mouse = _FakeMouse
    def __getattr__(self, k):
        return getattr(store._rec_real_pg, k)
if not hasattr(store, "_rec_real_pg"):
    store._rec_real_pg = store._ag_pg

def open_equip():
    renpy.run([SetVariable('setup_frame_select', 'Appearance'), Function(update_gui_vars, 'equip_showclothes', 'set', True),
               Function(update_gui_vars, 'equip_zoom', 'set', 0.55), Function(update_gui_vars, 'equip_ypos', 'set', 0),
               SetVariable('equip_page', 0), Function(renpy.show_screen, 'action_frame'), SetVariable('equip_inv_page', 0),
               Show('setup_frame', in_color=ColorMain1), Function(update_gui_vars, 'frame_currentequip', 'set', 1),
               Function(outfitset_initialize)])

def top(n):
    return lambda: APEX_GRID_TOP.__setitem__("equip:app", n)

def pick():
    v = apex_equip_view()
    s = apex_grid_slots(v["grid"], v["keys"])
    store._ag_pg = _FakePg()
    APEX_DRAG.update(gid=v["grid"], slot=1, key=s[1], img=v["entries"][s[1]]["img"], press=(100, 35), active=True,
                     mouse=(100, 35), off=(33, 33), scroll_t=0.0)

def drop():
    v = apex_equip_view()
    apex_equip_on_move(1, 6)
    apex_drag_cancel()
    store._ag_pg = store._rec_real_pg

steps = [(open_equip, 1.2), (top(0), 0.5), (top(1), 0.35), (top(2), 0.35), (top(1), 0.35), (top(0), 0.6), (pick, 0.4)]
for k in range(1, 8):
    steps.append(((lambda k=k: APEX_DRAG.__setitem__("mouse", (100 - 67 * k / 7.0, 35 + 150 * k / 7.0))), 0.15))
steps += [(drop, 0.6), (None, 0.5)]
story("equip", steps)
RESULT = len(steps)
