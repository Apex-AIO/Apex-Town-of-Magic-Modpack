# storyboard: Inventory Scroll Mod + Movable Inventory Items on the HUD grid (run in game after rec_helpers.py)
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

v = APEX_INV_VIEW
g = v["grid"]
rows = len(apex_inv_slots()) // 3
steps = []
def top(n):
    return lambda: APEX_GRID_TOP.__setitem__(g, n)
steps.append((top(0), 0.6))
for n in list(range(1, rows - 2)) + list(range(rows - 4, -1, -1)):
    steps.append((top(n), 0.35))
# drag: square 0 -> square 8 along a line (grid-local coords)
def pick():
    store._ag_pg = _FakePg()
    s = apex_inv_slots()
    APEX_DRAG.update(gid=g, slot=0, key=s[0], img=v["entries"][s[0]]["img"], press=(35, 35), active=True,
                     mouse=(35, 35), off=(33, 33), scroll_t=0.0)
steps.append((pick, 0.4))
for k in range(1, 9):
    x, y = 35 + (134 + 35 - 35) * k / 8.0, 35 + 150 * k / 8.0
    steps.append(((lambda x=x, y=y: APEX_DRAG.__setitem__("mouse", (x, y))), 0.15))
def drop():
    apex_inv_on_move(0, 8)
    apex_drag_cancel()
    store._ag_pg = store._rec_real_pg
steps.append((drop, 0.6))
steps.append((None, 0.6))
story("inventory", steps)
RESULT = "%d steps, %d rows" % (len(steps), rows)
