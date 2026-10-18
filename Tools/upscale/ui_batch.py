"""ui_batch.py - HD (@2 / @4) for everything that is not a character or a background: main menu art, world map,
menus, buttons, bars, item icons, symbols, effects, book pages, language flags (images/GUI, ICON, MAP, FX, BOOK, LANG
and gui/).  Needs ComfyUI's Python and GPU, but NOT ComfyUI itself: no AI repainting.

    python ui_batch.py                 seen-in-game files first, then all the others (finished files are skipped)
    python ui_batch.py --seen-only     only what you have seen while playing
    python ui_batch.py --only MAP/ --force

Recipe U (upscale only): 4x-ReboutBlend x4, again x4 from x2 (= x8) + colour match to the original -> @4 (x4) and
@2 (x2).  No detailer on purpose: text, numbers, symbols and icon pixel art must stay exactly what they are (an AI pass
would invent letters and change icons), and see-through UI keeps its alpha (4x-SkyrimAlpha).
Identical files (same pixels) are upscaled once and copied.  GIFs are skipped (animated bars; Ren'Py draws them small).
Output: Mods/hd_sprites_mod/<same path>@2.png / @4.png, copied into game/ (--no-install skips).
"""
import os, sys, io, time, shutil, hashlib, argparse
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "art"))
import hd_batch as H
from compare_upscalers import upscale4, MODEL_DIR, ALPHA_MODEL, DEV
from refine_compare import color_match
from catalog import read_index, read_bytes, ARCHIVES
import spandrel

FOLDERS = ("images/GUI/", "images/ICON/", "images/MAP/", "images/FX/", "images/BOOK/", "images/LANG/", "gui/")
USED = os.path.join(H.GAME, "claude_debug", "used_images.txt")
LOGS = os.path.join(os.path.dirname(HERE), "debug", "logs")


def seen_set():
    s = set()
    files = [USED] + ([os.path.join(LOGS, f) for f in os.listdir(LOGS) if f.startswith("used_images")] if os.path.isdir(LOGS) else [])
    for f in files:
        if os.path.exists(f):
            for l in open(f, encoding="utf8", errors="replace"):
                rel = l.split("\t")[0].strip().replace("\\", "/")
                rel = rel.lower()
                if not rel.startswith(("images/", "gui/")):
                    rel = "images/" + rel              # the recorder writes MAP/..., the archive has images/MAP/...
                s.add(rel)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seen-only", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-install", action="store_true")
    a = ap.parse_args()

    idx = {}
    for arch in ARCHIVES:
        for k, v in read_index(arch).items():
            if k.startswith(FOLDERS) and k.lower().endswith(".png") and "@" not in k:
                idx.setdefault(k, (arch, v))
    seen = seen_set()
    rels = sorted(idx, key=lambda r: (r.lower() not in seen, r))
    if a.seen_only:
        rels = [r for r in rels if r.lower() in seen]
    if a.only:
        rels = [r for r in rels if a.only in r]

    def out_path(rel, s):
        return os.path.join(H.MOD, rel.replace("/", os.sep))[:-4] + "@%d.png" % s

    def done(rel):
        return all(os.path.exists(out_path(rel, s)) for s in (2, 4))

    def install(p):
        if not a.no_install:
            dst = os.path.join(H.GAME, os.path.relpath(p, H.MOD))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(p, dst)

    def save(rel, img4):
        w, h = img4.width // 4, img4.height // 4
        for s, im in ((4, img4), (2, img4.resize((w * 2, h * 2), Image.LANCZOS))):
            p = out_path(rel, s)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            H.clean_alpha(im).save(p, compress_level=1)
            install(p)

    # files finished earlier (maybe by a --no-install test) but not in the game yet: install them
    if not a.no_install:
        for r in rels:
            if done(r) and not all(os.path.exists(os.path.join(H.GAME, os.path.relpath(out_path(r, s), H.MOD))) for s in (2, 4)):
                for s in (2, 4):
                    install(out_path(r, s))
    todo = [r for r in rels if a.force or not done(r)]
    print("%d interface pictures, %d to make (%d seen in game, first)" % (len(rels), len(todo),
          sum(1 for r in todo if r.lower() in seen)), flush=True)
    if not todo:
        return
    L = spandrel.ModelLoader()
    model = L.load_from_file(os.path.join(MODEL_DIR, H.MODEL)).to(DEV).eval()
    amodel = L.load_from_file(os.path.join(MODEL_DIR, ALPHA_MODEL)).to(DEV).eval()

    def up4(img):
        w, h = img.size
        x4 = upscale4(model, amodel, img)
        x8 = color_match(upscale4(model, amodel, x4.resize((w * 2, h * 2), Image.LANCZOS)), img)
        return x8.resize((w * 4, h * 4), Image.LANCZOS)

    made = {}                                   # pixel hash -> rel already made (identical files are copied)
    t0, n, failed = time.time(), 0, []
    for rel in todo:
        n += 1
        try:
            arch, e = idx[rel]
            img = Image.open(io.BytesIO(read_bytes(arch, e))).convert("RGBA")
            key = hashlib.md5(img.tobytes() + str(img.size).encode()).hexdigest()
            if key in made and done(made[key]):
                for s in (2, 4):
                    os.makedirs(os.path.dirname(out_path(rel, s)), exist_ok=True)
                    shutil.copy2(out_path(made[key], s), out_path(rel, s))
                    install(out_path(rel, s))
                print("[%d/%d] %s  (copy of %s)" % (n, len(todo), rel, os.path.basename(made[key])), flush=True)
                continue
            save(rel, up4(img))
            made[key] = rel
            left = (time.time() - t0) / n * (len(todo) - n) / 60
            print("[%d/%d] %s  %dx%d  ~%.0f min left" % (n, len(todo), rel, img.width, img.height, left), flush=True)
        except Exception as ex:
            failed.append((rel, repr(ex)))
            print("[%d/%d] %s  FAILED: %r" % (n, len(todo), rel, ex), flush=True)
    H.free_vram()
    if failed:
        with open(os.path.join(os.path.dirname(H.MOD), "..", "Upscale", "ui_failed.txt"), "a", encoding="utf8") as f:
            for r, e in failed:
                f.write("%s\t%s\n" % (r, e))
    print("all done in %.1f min, %d failed%s" % ((time.time() - t0) / 60, len(failed),
          " (listed in Upscale/ui_failed.txt)" if failed else ""))


if __name__ == "__main__":
    main()
