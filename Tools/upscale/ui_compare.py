"""ui_compare.py - vanilla | x8 upscale only (recipe U, what the interface got) | recipe P (the character/clothing recipe:
x8 + AI detail pass) for a few interface pictures.  Needs ComfyUI running.   python ui_compare.py [name ...]
Output: Upscale/ui_compare/sheet.png (+ the single results)."""
import os, sys, io, time
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "art"))
import hd_batch as H
from compare_upscalers import upscale4, MODEL_DIR, ALPHA_MODEL, DEV, font
from refine_compare import color_match
from catalog import read_index, read_bytes, ARCHIVES
import spandrel

PICKS = [("Accessory", "images/ICON/gold_watch.png"), ("Accessory", "images/ICON/lucky_cat.png"),
         ("Accessory", "images/ICON/mithril_allure_pendant.png"),
         ("Symbol", "images/GUI/pin_enabled.png"), ("Symbol", "images/ICON/arrow_right.png"), ("Symbol", "images/BOOK/tick.png"),
         ("Text", "images/BOOK/skills_tutorial_accessory_desc.png"), ("Text", "images/BOOK/skills_tutorial_skil_learning_1.png"),
         ("Text", "images/BOOK/mysticfoxshrine_tutorial_bodyproficiency_1.png")]
OUT = os.path.join(H.WS, "Upscale", "ui_compare")


def main():
    os.makedirs(OUT, exist_ok=True)
    idx = {}
    for a in ARCHIVES:
        for k, v in read_index(a).items():
            idx.setdefault(k, (a, v))
    L = spandrel.ModelLoader()
    model = L.load_from_file(os.path.join(MODEL_DIR, H.MODEL)).to(DEV).eval()
    amodel = L.load_from_file(os.path.join(MODEL_DIR, ALPHA_MODEL)).to(DEV).eval()

    def up4(img):
        w, h = img.size
        x4 = upscale4(model, amodel, img)
        x8 = color_match(upscale4(model, amodel, x4.resize((w * 2, h * 2), Image.LANCZOS)), img)
        H.free_vram()
        return x8.resize((w * 4, h * 4), Image.LANCZOS)

    P = dict(denoise=H.DENOISE, loras=H.P_LORAS, cn=(H.CN_TILE, H.CN_STRENGTH), steps=H.P_STEPS, pos=H.POS_P, neg=H.NEG_P)
    rows = []
    for kind, rel in PICKS:
        a, e = idx[rel]
        img = Image.open(io.BytesIO(read_bytes(a, e))).convert("RGBA")
        big = up4(img)                                              # = what the interface batch makes (x4 file)
        t = H.detail_submit(big, **P)
        res = big if t is None else None
        while res is None:
            res = H.detail_poll(t)
            if res is None:
                time.sleep(0.4)
        name = os.path.basename(rel)[:-4]
        big.save(os.path.join(OUT, name + "_U.png")); res.save(os.path.join(OUT, name + "_P.png"))
        rows.append((kind, name, img, big, res))
        print("done", rel, flush=True)
    # sheet: every row scaled so the picture is ~300 px tall (max 520 wide), three columns on a checker-free dark background
    f = font(15)
    cw = 520
    cells = []
    for kind, name, o, u, p in rows:
        s = min(cw / o.width, 300.0 / o.height)
        s = max(1, int(s)) if s >= 1 else s
        size = (max(1, int(o.width * s)), max(1, int(o.height * s)))
        cells.append((kind, name, o.resize(size, Image.NEAREST), u.resize(size, Image.LANCZOS), p.resize(size, Image.LANCZOS)))
    H_ROWS = [max(c[2].height for c in cells[i:i + 1]) + 34 for i in range(len(cells))]
    sheet = Image.new("RGB", (3 * (cw + 20) + 20, sum(H_ROWS) + 50), "#1b1722")
    d = ImageDraw.Draw(sheet)
    for j, title in enumerate(("Original (enlarged, nearest)", "x8 upscale only (interface recipe)", "Recipe P (x8 + AI detail, as characters)")):
        d.text((20 + j * (cw + 20), 8), title, fill="#ffd24d", font=font(18))
    y = 40
    for (kind, name, o, u, p), hh in zip(cells, H_ROWS):
        d.text((20, y), "%s: %s" % (kind, name), fill="#9aa", font=f)
        for j, im in enumerate((o, u, p)):
            bg = Image.new("RGBA", im.size, (44, 36, 56, 255))
            bg.alpha_composite(im.convert("RGBA"))
            sheet.paste(bg.convert("RGB"), (20 + j * (cw + 20), y + 22))
        y += hh
    sheet.save(os.path.join(OUT, "sheet.png"))
    print("sheet:", os.path.join(OUT, "sheet.png"))


if __name__ == "__main__":
    main()
