"""Stress test of the item-grid layout (Mods/inventory_scroll_mod/apex_grid.rpy) - no game needed.

    python Tools/tests/test_apex_grid.py [rounds]

Pulls the pure layout functions out of apex_grid.rpy and throws random inventories at them: items gained, used up,
sold, duplicated names, moves to any square (including far outside the grid), moves of empty squares, a corrupted
saved layout.  After every step it checks the rules the mod promises:
    * every item the game has is in the grid exactly once - nothing lost, nothing doubled
    * nothing that isn't in the inventory is shown
    * the grid always has 3+ rows and 3+ empty squares
    * a move only swaps the two squares, everything else stays where it was
"""
import os, re, sys, random, builtins

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "Mods", "inventory_scroll_mod", "apex_grid.rpy")


def load():
    text = open(SRC, encoding="utf8").read()
    ns = {"_ag_bt": builtins, "APEX_GRID_COLS": 3, "APEX_GRID_VIEW_ROWS": 3}
    for name in ("apex_grid_reconcile", "apex_grid_rows", "apex_grid_swap", "apex_grid_check", "apex_grid_keys"):
        m = re.search(r"(?ms)^    def %s\(.*?(?=^    def |^    # ----------)" % name, text)
        assert m, name
        exec("\n".join(l[4:] for l in m.group(0).splitlines()), ns)
    return ns


def main(rounds=3000):
    g = load()
    rec, rows, swap, check, keys_of = (g["apex_grid_reconcile"], g["apex_grid_rows"], g["apex_grid_swap"],
                                       g["apex_grid_check"], g["apex_grid_keys"])
    rnd = random.Random(7)
    names = ["Potion", "Ether", "Apple", "Herb", "Crystal", "Mushroom", "Lily", "Star", "Dildo", "Orb", "Spool",
             "Tablet", "Gem"] + ["Item %d" % i for i in range(60)]
    problems = 0
    steps = 0

    def verify(layout, keys, where):
        nonlocal problems
        used = [k for k in layout if k is not None]
        r = rows(layout)
        ok = (sorted(used) == sorted(keys) and len(used) == len(set(used)) and r >= 3
              and r * 3 - len(used) >= 3 and r * 3 >= len(layout))
        if not ok:
            problems += 1
            if problems < 10:
                print("PROBLEM", where, layout, keys)
        return ok

    for rnd_i in range(rounds):
        inv = rnd.sample(names, rnd.randint(0, 40))
        if rnd.random() < 0.2:
            inv += [rnd.choice(inv)] if inv else []          # two items with the same name
        keys = keys_of(inv)
        layout = rec([], keys)
        verify(layout, keys, "start")
        if rnd.random() < 0.1:                               # a damaged saved layout
            layout = [rnd.choice(names + [None, "ghost item"]) for _ in range(rnd.randint(0, 50))]
            layout = rec(layout, keys)
            verify(layout, keys, "repair")
        for _ in range(60):
            steps += 1
            op = rnd.random()
            if op < 0.25 and names:                          # gain an item
                inv.append(rnd.choice(names))
            elif op < 0.45 and inv:                          # use up / sell an item
                inv.remove(rnd.choice(inv))
            elif op < 0.95:                                  # move
                n = rows(layout) * 3
                a, b = rnd.randrange(n), rnd.randrange(n + (12 if rnd.random() < 0.1 else 0))
                before = list(layout)
                if a < len(layout) and layout[a] is not None and a != b:
                    new = swap(layout, a, b)
                    if not check(new, keys):
                        problems += 1
                        print("PROBLEM move broke the check", a, b, before)
                    pad = lambda l, k: l + [None] * (k - len(l))
                    m = max(len(before), len(new), a + 1, b + 1)
                    pb, pn = pad(before, m), pad(new, m)
                    for i in range(m):
                        want = pb[b] if i == a else pb[a] if i == b else pb[i]
                        if pn[i] != want:
                            problems += 1
                            print("PROBLEM move changed another square", a, b, before, new)
                            break
                    layout = new
            else:                                            # the game re-sorts its own list
                rnd.shuffle(inv)
            keys = keys_of(sorted(set(inv), key=inv.index))  # the game lists each item once
            layout = rec(layout, keys)
            verify(layout, keys, "step")
    print("%d inventories, %d steps, %d problems" % (rounds, steps, problems))
    return problems == 0


if __name__ == "__main__":
    sys.exit(0 if main(int(sys.argv[1]) if len(sys.argv) > 1 else 3000) else 1)
