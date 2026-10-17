"""progress.py - how far the HD project is: done vs. the whole game (an estimate - the end goal is every picture).

    python progress.py            print the numbers and write docs/images/progress*.svg + Catalog/progress.json
    from progress import compute  (the build embeds it in the Mod Manager and the README)

Counted from the art catalog (catalog.py, roles.py, bg_catalog.py) and the HD files that exist right now:
  Characters   every sprite file of every non-male character (empty files left out); per character also its
               poses (a pose is done when all its pictures are)
  Backgrounds  every location picture, window view, light overlay, animation frame and event picture
  Interface    menus, icons, map, effects - planned later, counted so the end goal is honest
Male characters are not part of the HD project (not counted).
"""
import os, sys, json, sqlite3, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from catalog import DB, CAT, WS, read_index, ARCHIVES

MOD = os.path.join(WS, "Mods", "hd_sprites_mod")
ALIAS = {"ghost": "Nel", "celicaspirit": "Celica (spirit)", "e_celica": "Celica"}
UI_FOLDERS = ("images/GUI/", "images/ICON/", "images/MAP/", "images/FX/", "images/BOOK/", "images/LANG/", "gui/")


PRETTY = {"celicachild": "Celica (child)", "celicafairy": "Celica (fairy)", "galienespirit": "Galiene (spirit)",
          "faylenspirit": "Faylen (spirit)", "lenashopkeeper": "Lena (shop keeper)", "icearmor": "Ice Armor",
          "umbralgroper": "Umbral Groper", "fortuneteller": "Fortune Teller", "phantom sword": "Phantom Sword",
          "mana-stalker": "Mana Stalker"}


def pretty(folder, names):
    """the name players know, e.g. SlimeGirl -> Slime Girl, kitsune -> Kitsune"""
    import re
    n = ALIAS.get(folder) or names.get(folder) or folder
    n = PRETTY.get(n.lower(), n)
    n = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", n)
    return n[:1].upper() + n[1:]


def _hd(rel):
    return os.path.exists(os.path.join(MOD, rel.replace("/", os.sep))[:-4] + "@2.png")


def compute():
    db = sqlite3.connect(DB)
    names = dict(db.execute("select folder, name from characters"))
    male = {f for (f,) in db.execute("select folder from characters where male=1")}
    rows = db.execute("""select s.rel, s.folder, r.pose, r.role from sprites s join roles r using(rel)
                         where r.role <> 'empty'""").fetchall()
    per = collections.defaultdict(lambda: {"total": 0, "done": 0, "folders": set(),
                                           "poses": collections.defaultdict(lambda: [0, 0])})
    for rel, folder, pose, role in rows:
        if folder in male:
            continue
        d = per[pretty(folder, names)]          # folders with the same name (mask, child, big...) count as one character
        done = _hd(rel)
        d["total"] += 1
        d["done"] += done
        d["folders"].add(folder)
        d["poses"][(folder, pose)][0] += 1
        d["poses"][(folder, pose)][1] += done
    char_rows = []
    for name, d in per.items():
        poses = d["poses"]
        char_rows.append(dict(name=name, folder=",".join(sorted(d["folders"])), total=d["total"], done=d["done"],
                              poses=len(poses), poses_done=sum(1 for t, dn in poses.values() if dn == t),
                              poses_started=sum(1 for t, dn in poses.values() if dn)))
    char_rows.sort(key=lambda r: (-r["done"], -r["total"]))
    bg = db.execute("select rel, folder from backgrounds where rel not like '%/debug%'").fetchall()
    bg_by = collections.defaultdict(lambda: [0, 0])
    for rel, folder in bg:
        bg_by[folder][0] += 1
        bg_by[folder][1] += _hd(rel)
    label = {"BG": "Locations", "BGANIM": "Animated backgrounds", "EVENT": "Event pictures"}
    bg_rows = [dict(name=label.get(f, f), total=t, done=dn) for f, (t, dn) in sorted(bg_by.items())]
    ui_total = 0
    for a in ARCHIVES:
        ui_total += sum(1 for k in read_index(a) if k.startswith(UI_FOLDERS) and k.endswith(".png"))

    def cat(name, rows_, note=""):
        t, dn = sum(r["total"] for r in rows_), sum(r["done"] for r in rows_)
        return dict(name=name, total=t, done=dn, pct=int(100 * dn / t) if t else 0, rows=rows_, note=note)
    cats = [cat("Characters", char_rows, "every pose, face, outfit and animation frame of the female characters and creatures"),
            cat("Backgrounds", bg_rows, "locations, window views, lights, animated backgrounds and event pictures"),
            dict(name="Interface & icons", total=ui_total, done=0, pct=0, rows=[], note="menus, item icons, map, effects — planned later")]
    total, done = sum(c["total"] for c in cats), sum(c["done"] for c in cats)
    return dict(total=total, done=done, overall_pct=round(100.0 * done / total, 1) if total else 0, categories=cats,
                characters_started=sum(1 for r in char_rows if r["done"]), characters_total=len(char_rows),
                male_left_out=len(male))


def bar_svg(path, pct, label, w=820, h=44, color="#9b6bff"):
    fill = max(0.0, min(1.0, pct / 100.0)) * (w - 4)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#ffc94d"/><stop offset="1" stop-color="{color}"/></linearGradient></defs>
  <rect x="0" y="0" width="{w}" height="{h}" rx="{h/2}" fill="#1a1522" stroke="#2c2438"/>
  <rect x="2" y="2" width="{fill:.1f}" height="{h-4}" rx="{(h-4)/2}" fill="url(#g)"/>
  <text x="{w/2}" y="{h/2+6}" text-anchor="middle" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="17" font-weight="700" fill="#ffffff">{label}</text>
</svg>'''
    open(path, "w", encoding="utf8").write(svg)


def write_outputs(p):
    os.makedirs(os.path.join(WS, "docs", "images"), exist_ok=True)
    json.dump(p, open(os.path.join(CAT, "progress.json"), "w", encoding="utf8"), indent=1)
    bar_svg(os.path.join(WS, "docs", "images", "progress.svg"), p["overall_pct"],
            "HD project: %s%%  -  %s of %s pictures" % (p["overall_pct"], format(p["done"], ","), format(p["total"], ",")))
    for c in p["categories"]:
        slug = c["name"].split()[0].lower()
        bar_svg(os.path.join(WS, "docs", "images", "progress_%s.svg" % slug), c["pct"],
                "%s: %d%%  (%s / %s)" % (c["name"], c["pct"], format(c["done"], ","), format(c["total"], ",")),
                w=820, h=30, color={"characters": "#9b6bff", "backgrounds": "#38d6f2"}.get(slug, "#6d6580"))



def _tbar(done, total, n=20):
    k = int(round(n * done / total)) if total else 0
    return "█" * k + "░" * (n - k)


def update_readme(p, version="", date=""):
    """rewrite the HD progress block of the repository README (between the PROGRESS markers)"""
    path = os.path.join(WS, "README.md")
    if not os.path.exists(path):
        return False
    t = open(path, encoding="utf8").read()
    a, b = "<!-- PROGRESS:START -->", "<!-- PROGRESS:END -->"
    if a not in t or b not in t:
        return False
    chars, bgs, ui = p["categories"]
    L = ["<!-- written by Tools/art/progress.py - run it (or build a release) to update -->", "<div align=\"center\">", "",
         '<img src="docs/images/progress.svg" alt="HD project progress" width="820">', "",
         "<sub>An estimate of every picture the game has (the end goal). Updated with every release%s.</sub>"
         % ((" - v%s, %s" % (version, date)) if version else ""), "", "</div>", "",
         "| | Area | HD done | Whole game | |", "|:-:|---|--:|--:|---|"]
    icons = {"Characters": "🧑‍🎨", "Backgrounds": "🏞️", "Interface & icons": "🧭"}
    for c in p["categories"]:
        slug = c["name"].split()[0].lower()
        L.append("| %s | **%s**<br><sub>%s</sub> | %s | %s | %d%% |" % (
            icons.get(c["name"], ""), c["name"], c["note"], format(c["done"], ","), format(c["total"], ","), c["pct"]))
    L += ["", "<details>", "<summary><b>🧑‍🎨 Characters in detail — %d of %d started</b></summary>" % (
        p["characters_started"], p["characters_total"]), "", "| Character | HD pictures | Progress |", "|---|--:|---|"]
    for r in chars["rows"]:
        if r["done"]:
            L.append("| %s | %s / %s | `%s` %d%% |" % (r["name"], format(r["done"], ","), format(r["total"], ","),
                                                     _tbar(r["done"], r["total"]), int(100 * r["done"] / r["total"])))
    rest = [r for r in chars["rows"] if not r["done"]]
    if rest:
        L.append("")
        L.append("<sub>Not started yet (%d): %s</sub>" % (len(rest), ", ".join(sorted(r["name"] for r in rest))))
    L += ["", "</details>", "", "<details>", "<summary><b>🏞️ Backgrounds in detail</b></summary>", "",
          "| Kind | HD pictures | Progress |", "|---|--:|---|"]
    for r in bgs["rows"]:
        L.append("| %s | %s / %s | `%s` %d%% |" % (r["name"], format(r["done"], ","), format(r["total"], ","),
                                                 _tbar(r["done"], r["total"]), int(100 * r["done"] / r["total"]) if r["total"] else 0))
    L += ["", "</details>", "",
          "<sub>A \"picture\" is one image file of the game: a pose, a face, a piece of clothing, an animation sheet or a "
          "background layer. Male characters aren't part of the HD project.</sub>"]
    nl = "\n"
    t = t[:t.index(a) + len(a)] + nl + nl.join(L) + nl + t[t.index(b):]
    open(path, "w", encoding="utf8").write(t)
    return True

if __name__ == "__main__":
    p = compute()
    write_outputs(p)
    print("README progress block updated" if update_readme(p) else "(README has no progress markers)")
    print("HD project: %s%%  (%d of %d pictures)" % (p["overall_pct"], p["done"], p["total"]))
    for c in p["categories"]:
        print("  %-20s %6d / %-6d %3d%%" % (c["name"], c["done"], c["total"], c["pct"]))
    print("  characters started: %d of %d (male left out: %d)" % (p["characters_started"], p["characters_total"], p["male_left_out"]))
    for r in p["categories"][0]["rows"][:12]:
        print("     %-22s pictures %5d / %-5d  poses %d (%d started) / %d" % (r["name"], r["done"], r["total"], r["poses_done"],
                                                                         r["poses_started"], r["poses"]))
