# apex_grid.rpy  -  the scrolling, drag-and-drop item grid shared by the Inventory Scroll Mod and the
#                   Appearance/Accessories Scroll Mod.  Defines things only; it changes nothing in the game.
#
# Safety by design: the grid only stores WHERE each item is drawn (a list of item names per grid, in main_vars,
# so it is saved and rolled back with the game).  It never adds, removes or moves the game's own items:
#   * every item the game lists is always drawn exactly once (missing ones are put in the first empty square),
#   * a picked-up item stays in its square (shown as a faded "ghost") until it is dropped on another square,
#   * dropping anywhere else (outside the grid, between squares) cancels the move,
#   * if anything doesn't add up, the grid falls back to the game's own order.

init -5 python:
    import builtins as _ag_bt
    import pygame_sdl2 as _ag_pg

    APEX_GRID_COLS = 3
    APEX_GRID_VIEW_ROWS = 3
    APEX_GRID_CELL = (67, 75)
    APEX_GRID_SIZE = (205, 229)
    APEX_GRID_DRAG_START = 6          # pixels the mouse must move before a press becomes a drag
    APEX_GRID_MOVABLE = False         # switched on by the Movable Inventory Items mod (inventory_move.rpy)

    # runtime only (plain dicts: never saved, never rolled back)
    APEX_GRID_TOP = _ag_bt.dict()     # grid id -> first visible row
    APEX_DRAG = _ag_bt.dict(gid=None, slot=None, key=None, img=None, press=None, active=False, mouse=(0, 0), off=(0, 0),
                            scroll_t=0.0)
    APEX_GRID_LOG = []                # problems found by the checks (newest last), shown in game/apex_grid_log.txt

    def apex_grid_log(msg):
        if "restored" not in msg:
            tom_mod_error("inventory", msg)        # every grid problem is also an error report
        APEX_GRID_LOG.append(msg)
        del APEX_GRID_LOG[:-50]
        try:
            import io, os, time
            with io.open(os.path.join(config.basedir, "game", "apex_grid_log.txt"), "a", encoding="utf8") as f:
                f.write(u"%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
        except Exception:
            pass

    # ---------- the layout: pure functions (tested by Tools/tests) ----------

    def apex_grid_reconcile(layout, keys):
        """layout = saved list of item keys / None (empty square); keys = the items the game has now (unique).
        Returns the new layout: every key exactly once, squares of items that are gone become empty, new items go
        into the first empty square (or at the end), empty squares at the end are dropped."""
        present = _ag_bt.set(keys)
        seen = _ag_bt.set()
        out = []
        for k in (layout or ()):
            if k is not None and k in present and k not in seen:
                out.append(k)
                seen.add(k)
            else:
                out.append(None)
        hole = 0
        for k in keys:
            if k in seen:
                continue
            while hole < len(out) and out[hole] is not None:
                hole += 1
            if hole < len(out):
                out[hole] = k
            else:
                out.append(k)
            seen.add(k)
        while out and out[-1] is None:
            out.pop()
        return out

    def apex_grid_rows(layout):
        """rows to show: at least 3, every used square, and always 3+ empty squares (a new row is added when
        7 of 9 squares are taken, 10 of 12, ...)"""
        occupied = sum(1 for k in layout if k is not None)
        return max(APEX_GRID_VIEW_ROWS, (len(layout) + APEX_GRID_COLS - 1) // APEX_GRID_COLS,
                   (occupied + 3 + APEX_GRID_COLS - 1) // APEX_GRID_COLS)

    def apex_grid_swap(layout, a, b):
        """swap squares a and b (either may be empty); returns the new layout"""
        n = max(a, b) + 1
        out = list(layout) + [None] * max(0, n - len(layout))
        out[a], out[b] = out[b], out[a]
        while out and out[-1] is None:
            out.pop()
        return out

    def apex_grid_check(layout, keys):
        """True when every key is in the layout exactly once and nothing else is"""
        used = [k for k in layout if k is not None]
        return len(used) == len(_ag_bt.set(used)) and _ag_bt.set(used) == _ag_bt.set(keys)

    def apex_grid_keys(names):
        """unique keys for a list of item names in game order: a second item with the same name gets '#2'"""
        count, out = {}, []
        for n in names:
            n = str(n)
            count[n] = count.get(n, 0) + 1
            out.append(n if count[n] == 1 else "%s#%d" % (n, count[n]))
        return out

    # ---------- saved state ----------

    def _apex_grid_store():
        mv = getattr(store, "main_vars", None)
        if mv is None:
            return None
        if "apex_grid" not in mv:
            mv["apex_grid"] = {}
        return mv["apex_grid"]

    def apex_grid_slots(gid, keys):
        """the squares of grid gid for these keys (padded to whole rows); saves the layout when it changed"""
        st = _apex_grid_store()
        old = list(st.get(gid, [])) if st is not None else []
        new = apex_grid_reconcile(old, keys)
        if not apex_grid_check(new, keys):
            apex_grid_log("grid %s: layout check failed - using the game's order" % gid)
            new = list(keys)
        if st is not None and new != old:
            st[gid] = new
        rows = apex_grid_rows(new)
        return new + [None] * (rows * APEX_GRID_COLS - len(new))

    def apex_grid_move(gid, keys, a, b):
        """move the item in square a to square b (swapping with whatever is there)"""
        st = _apex_grid_store()
        if st is None or a == b:
            return False
        cur = apex_grid_reconcile(list(st.get(gid, [])), keys)
        if a >= len(cur) or cur[a] is None:
            return False
        new = apex_grid_swap(cur, a, b)
        if not apex_grid_check(new, keys):
            apex_grid_log("grid %s: move %d -> %d refused (check failed)" % (gid, a, b))
            return False
        st[gid] = new
        return True

    def apex_grid_reset(gid=None):
        st = _apex_grid_store()
        if st is None:
            return
        for k in list(st.keys()):
            if gid is None or k == gid or k.startswith(gid + ":"):
                del st[k]
        APEX_GRID_TOP.clear()
        renpy.restart_interaction()

    def apex_grid_top(gid, rows):
        top = APEX_GRID_TOP.get(gid, 0)
        top = max(0, min(top, rows - APEX_GRID_VIEW_ROWS))
        APEX_GRID_TOP[gid] = top
        return top

    def apex_grid_scroll(gid, rows, delta):
        old = APEX_GRID_TOP.get(gid, 0)
        APEX_GRID_TOP[gid] = max(0, min(old + delta, rows - APEX_GRID_VIEW_ROWS))
        return APEX_GRID_TOP[gid] != old

    def apex_grid_show_key(gid, slots, key):
        """scroll so that the square holding key is visible (used when the game points at an item)"""
        if key in slots:
            row = slots.index(key) // APEX_GRID_COLS
            top = APEX_GRID_TOP.get(gid, 0)
            if row < top or row >= top + APEX_GRID_VIEW_ROWS:
                APEX_GRID_TOP[gid] = max(0, row - 1)

    # ---------- what may be touched (the "UI overlap" check) ----------

    APEX_GRID_BLOCKING = ("select_item_frame", "gotitem_frame", "confirm_frame", "shopmenu_frame", "fusemenu_frame",
                          "book_frame", "map_frame")
    APEX_GRID_OWN = ("action_frame", "apex_inv_hud", "apex_equip_grid", "apex_hd_toggle", "quick_menu")

    def apex_ui_blocked(allow=()):
        """True when another window is open over the game (equip, shop, map, a question...), so the grid must not
        react: the game's own grid would be covered by that window too"""
        for n in APEX_GRID_BLOCKING:
            if n not in allow and renpy.get_screen(n) is not None:
                return True
        if "setup_frame" not in allow and renpy.get_screen("setup_frame") is not None:
            return True
        try:
            for tag in renpy.get_showing_tags("screens"):
                if tag in APEX_GRID_OWN or tag in allow:
                    continue
                sd = renpy.get_screen(tag)
                if sd is not None and getattr(sd, "modal", False) is True:
                    return True
        except Exception:
            pass
        return False

    def apex_drag_cancel():
        if APEX_DRAG["press"] is not None or APEX_DRAG["active"]:
            was = APEX_DRAG["active"]
            APEX_DRAG.update(gid=None, slot=None, key=None, img=None, press=None, active=False)
            if was:
                renpy.restart_interaction()

    def apex_drag_is(gid, slot):
        return APEX_DRAG["active"] and APEX_DRAG["gid"] == gid and APEX_DRAG["slot"] == slot

    # ---------- the input layer: mouse wheel + drag and drop ----------

    class ApexGridInput(renpy.Displayable):
        """invisible layer on top of a grid: scrolls with the mouse wheel, picks up and drops items.
        A plain click is left alone, so the game's own button under it still uses the item."""

        def __init__(self, gid, slots, entries, movable, on_move, **kw):
            super(ApexGridInput, self).__init__(**kw)
            self.gid = gid
            self.slots = slots
            self.entries = entries
            self.movable = movable
            self.on_move = on_move
            self.rows = len(slots) // APEX_GRID_COLS

        def slot_at(self, x, y):
            cw, ch = APEX_GRID_CELL
            if not (3 <= x < 3 + cw * APEX_GRID_COLS and 3 <= y < 3 + ch * APEX_GRID_VIEW_ROWS):
                return None
            col, row = int((x - 3) // cw), int((y - 3) // ch)
            return (apex_grid_top(self.gid, self.rows) + row) * APEX_GRID_COLS + col

        def render(self, width, height, st, at):
            w, h = APEX_GRID_SIZE
            r = renpy.Render(w, h)
            d = APEX_DRAG
            if d["active"] and d["gid"] == self.gid:
                if not _ag_pg.mouse.get_pressed()[0]:
                    apex_drag_cancel()            # the button was let go outside the window: nothing moves
                    return r
                mx, my = d["mouse"]
                # near the top/bottom edge: scroll one row at a time
                if st - d["scroll_t"] > 0.35:
                    if my < 18 and apex_grid_scroll(self.gid, self.rows, -1):
                        d["scroll_t"] = st
                        renpy.restart_interaction()
                    elif my > h - 18 and apex_grid_scroll(self.gid, self.rows, 1):
                        d["scroll_t"] = st
                        renpy.restart_interaction()
                if d["img"] is not None:
                    cr = renpy.render(renpy.displayable(d["img"]), width, height, st, at)
                    r.blit(cr, (int(mx - d["off"][0]), int(my - d["off"][1])))
                renpy.redraw(self, 0.03)
            return r

        def event(self, ev, x, y, st):
            w, h = APEX_GRID_SIZE
            inside = 0 <= x < w and 0 <= y < h
            d = APEX_DRAG
            if inside and renpy.map_event(ev, "viewport_wheelup"):
                if apex_grid_scroll(self.gid, self.rows, -1):
                    renpy.restart_interaction()
                raise renpy.IgnoreEvent()          # also stops the wheel from rolling the story back
            if inside and renpy.map_event(ev, "viewport_wheeldown"):
                if apex_grid_scroll(self.gid, self.rows, 1):
                    renpy.restart_interaction()
                raise renpy.IgnoreEvent()
            if not self.movable:
                if d["gid"] == self.gid:
                    apex_drag_cancel()
                return None
            if ev.type == _ag_pg.MOUSEBUTTONDOWN and ev.button == 1:
                apex_drag_cancel()
                s = self.slot_at(x, y) if inside else None
                if s is not None and s < len(self.slots) and self.slots[s] is not None:
                    e = self.entries.get(self.slots[s])
                    if e is not None and e.get("img") is not None:
                        cw, ch = APEX_GRID_CELL
                        vis = s - apex_grid_top(self.gid, self.rows) * APEX_GRID_COLS
                        cx, cy = 3 + cw * (vis % APEX_GRID_COLS), 3 + ch * (vis // APEX_GRID_COLS)
                        d.update(gid=self.gid, slot=s, key=self.slots[s], img=e["img"], press=(x, y), active=False,
                                 mouse=(x, y), off=(x - cx + 1, y - cy + 1), scroll_t=st)
                return None
            if d["gid"] != self.gid or d["press"] is None:
                return None
            if ev.type == _ag_pg.MOUSEMOTION:
                d["mouse"] = (x, y)
                if not d["active"]:
                    px, py = d["press"]
                    if abs(x - px) + abs(y - py) >= APEX_GRID_DRAG_START:
                        d["active"] = True
                        renpy.restart_interaction()
                renpy.redraw(self, 0)
                return None
            if ev.type == _ag_pg.MOUSEBUTTONUP and ev.button == 1:
                was_active, src, key = d["active"], d["slot"], d["key"]
                target = self.slot_at(x, y) if inside else None
                d.update(gid=None, slot=None, key=None, img=None, press=None, active=False)
                if not was_active:
                    return None                    # a normal click: the game's button uses the item
                if target is not None and target != src and self.slots[src] == key:
                    try:
                        self.on_move(src, target)
                    except Exception as e:
                        apex_grid_log("move failed: %r" % (e,))
                renpy.restart_interaction()
                raise renpy.IgnoreEvent()          # the drop must not also click the square under the mouse
            return None

        def visit(self):
            return []


# one grid of squares, drawn like the game's own (same square, same item picture, same numbers)
screen apex_grid_view(gid, gx, gy, slots, entries, icon_color, movable, blocked, on_move, keys=True):
    $ _rows = len(slots) // APEX_GRID_COLS
    $ _top = apex_grid_top(gid, _rows)
    frame area (gx, gy, APEX_GRID_SIZE[0], APEX_GRID_SIZE[1]) padding 0,0 background None:
        add Solid(icon_color)
        add "GUI/GUI_INV_ITEM.png"
        for _vi in range(APEX_GRID_COLS * APEX_GRID_VIEW_ROWS):
            $ _si = _top * APEX_GRID_COLS + _vi
            $ _k = slots[_si] if _si < len(slots) else None
            if _k is not None and _k in entries:
                $ _e = entries[_k]
                $ _x = 3 + APEX_GRID_CELL[0] * (_vi % APEX_GRID_COLS)
                $ _y = 3 + APEX_GRID_CELL[1] * (_vi // APEX_GRID_COLS)
                if apex_drag_is(gid, _si):
                    # the ghost: the real item, faded, still in its square until it is dropped somewhere valid
                    use itemicon_frame(icon_xpos=_x, icon_ypos=_y, icon_color=icon_color, icon_img=_e["img"], icon_shadowimg=_e["shadow_img"], icon_alpha=0.3, icon_counttotal=_e["count_total"], icon_sensitive=False, icon_action=NullAction(), icon_tooltiptext="", icon_keysymlist=[])
                else:
                    use itemicon_frame(icon_xpos=_x, icon_ypos=_y, icon_color=icon_color, icon_img=_e["img"], icon_shadowimg=_e["shadow_img"], icon_outline=_e["outline"], icon_outlinecolor=_e["outline_color"], icon_alpha=_e["alpha"], icon_grayscale=_e["grayscale"], icon_bar=_e["bar"], icon_barcolor=_e["bar_color"], icon_barperc=_e["bar_perc"], icon_cooldownperc=_e["cooldown_perc"], icon_counttotal=_e["count_total"], icon_sensitive=_e["sensitive"] and not blocked, icon_action=_e["action"], icon_tooltiptext=_e["tooltiptext"], icon_keysymlist=(get_button_keysymlist(spellnum_to_keysym(_vi)) if keys and not blocked else []))
        add ApexGridInput(gid, slots, entries, movable and not blocked, on_move)
        if blocked:
            # another window is open: like the game's own grid, nothing here reacts
            button area (0, 0, APEX_GRID_SIZE[0], APEX_GRID_SIZE[1]) action NullAction() background None
    if _rows > APEX_GRID_VIEW_ROWS:
        # scroll bar where the game's page arrows were
        frame area (gx + APEX_GRID_SIZE[0] + 3, gy + 4, 5, APEX_GRID_SIZE[1] - 8) padding 0,0 background Solid("#00000080"):
            add Solid(ColorClick) ypos int((APEX_GRID_SIZE[1] - 8) * _top / float(_rows)) ysize max(10, int((APEX_GRID_SIZE[1] - 8) * APEX_GRID_VIEW_ROWS / float(_rows)))
