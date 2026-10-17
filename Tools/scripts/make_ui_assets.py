"""make_ui_assets.py - draws the Mod Manager's interface pieces (rounded panels, switches, icons) as PNGs.

    python make_ui_assets.py   -> Mods/apex_modpack_manager/ui/*.png  (+ @2 versions for big windows)

White shapes are tinted in the game (Transform(matrixcolor=TintMatrix(...))), so one file serves every colour.
Drawn 8x bigger and shrunk, so edges are smooth.
"""
import os, math
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "Mods", "apex_modpack_manager", "ui"))
SS = 8
W = (255, 255, 255, 255)


def canvas(w, h, scale):
    return Image.new("RGBA", (w * scale * SS, h * scale * SS), (0, 0, 0, 0))


def done(img, w, h, scale):
    return img.resize((w * scale, h * scale), Image.LANCZOS)


def save(name, fn):
    for scale, suf in ((1, ""), (2, "@2")):
        fn(scale).save(os.path.join(OUT, name + suf + ".png"))


def rrect(w, h, r, fill=W, outline=None, width=0):
    def f(scale):
        k = scale * SS
        im = canvas(w, h, scale)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=r * k, fill=fill,
                            outline=outline, width=width * k if outline else 0)
        return done(im, w, h, scale)
    return f


def ring(w, h, r, width):
    return rrect(w, h, r, fill=(0, 0, 0, 0), outline=W, width=width)


def circle(d_, scale):
    k = scale * SS
    im = canvas(d_, d_, scale)
    ImageDraw.Draw(im).ellipse((0, 0, d_ * k - 1, d_ * k - 1), fill=W)
    return done(im, d_, d_, scale)


def icon(name, draw):
    s = 20

    def f(scale):
        k = scale * SS
        im = canvas(s, s, scale)
        d = ImageDraw.Draw(im)
        draw(d, k, lambda *p: tuple(v * k for v in p))
        return done(im, s, s, scale)
    save("ic_" + name, f)


def main():
    os.makedirs(OUT, exist_ok=True)
    save("panel", rrect(32, 32, 10))                   # 9-slice: Frame(..., 12, 12)
    save("panel_ring", ring(32, 32, 10, 1))
    save("pill", rrect(24, 24, 12))                    # 9-slice: Frame(..., 12, 12) - fully rounded ends
    save("bar", rrect(12, 12, 6))
    save("thin", rrect(8, 8, 4))                       # 9-slice: Frame(..., 4, 4) - thin progress bars
    save("dot", lambda sc: circle(10, sc))
    save("knob", lambda sc: circle(18, sc))
    save("glow", lambda sc: done(_glow(sc), 64, 64, sc))
    L = 2

    icon("overview", lambda d, k, p: [d.rounded_rectangle(p(2, 2, 9, 9), radius=2 * k, outline=W, width=L * k),
                                      d.rounded_rectangle(p(11, 2, 18, 9), radius=2 * k, outline=W, width=L * k),
                                      d.rounded_rectangle(p(2, 11, 9, 18), radius=2 * k, outline=W, width=L * k),
                                      d.rounded_rectangle(p(11, 11, 18, 18), radius=2 * k, fill=W)])
    icon("star", lambda d, k, p: d.polygon([p(10 + 8 * math.cos(math.radians(-90 + i * 36)) * (1 if i % 2 == 0 else 0.45),
                                                10 + 8 * math.sin(math.radians(-90 + i * 36)) * (1 if i % 2 == 0 else 0.45))
                                              for i in range(10)], fill=W))
    icon("puzzle", lambda d, k, p: [d.rounded_rectangle(p(3, 6, 15, 18), radius=2 * k, fill=W),
                                    d.ellipse(p(7, 2, 11, 6), fill=W), d.ellipse(p(14, 10, 18, 14), fill=W)])
    icon("sparkle", lambda d, k, p: [d.polygon([p(10, 1), p(12, 8), p(19, 10), p(12, 12), p(10, 19), p(8, 12), p(1, 10), p(8, 8)], fill=W)])
    icon("wrench", lambda d, k, p: [d.line(p(4, 16, 13, 7), fill=W, width=3 * k), d.ellipse(p(10, 2, 18, 10), outline=W, width=L * k),
                                    d.rectangle(p(13, 1, 16, 5), fill=(0, 0, 0, 0))])
    icon("heart", lambda d, k, p: [d.ellipse(p(2, 3, 11, 12), fill=W), d.ellipse(p(9, 3, 18, 12), fill=W),
                                   d.polygon([p(2.5, 9), p(17.5, 9), p(10, 18)], fill=W)])
    icon("folder", lambda d, k, p: [d.rounded_rectangle(p(2, 5, 18, 16), radius=2 * k, fill=W), d.rectangle(p(2, 3, 9, 6), fill=W)])
    icon("plus", lambda d, k, p: [d.rounded_rectangle(p(9, 3, 11, 17), radius=k, fill=W), d.rounded_rectangle(p(3, 9, 17, 11), radius=k, fill=W)])
    icon("check", lambda d, k, p: d.line([p(4, 10), p(8, 14), p(16, 5)], fill=W, width=3 * k, joint="curve"))
    icon("warn", lambda d, k, p: [d.polygon([p(10, 2), p(19, 18), p(1, 18)], fill=W),
                                  d.rectangle(p(9.2, 7, 10.8, 13), fill=(0, 0, 0, 0)), d.rectangle(p(9.2, 14.5, 10.8, 16), fill=(0, 0, 0, 0))])
    icon("info", lambda d, k, p: [d.ellipse(p(1, 1, 19, 19), fill=W), d.rectangle(p(9, 8, 11, 15), fill=(0, 0, 0, 0)),
                                  d.rectangle(p(9, 4.5, 11, 6.5), fill=(0, 0, 0, 0))])
    icon("book", lambda d, k, p: [d.rounded_rectangle(p(2, 3, 9.5, 17), radius=k, fill=W), d.rounded_rectangle(p(10.5, 3, 18, 17), radius=k, fill=W)])
    icon("search", lambda d, k, p: [d.ellipse(p(2, 2, 13, 13), outline=W, width=L * k), d.line(p(11.5, 11.5, 18, 18), fill=W, width=3 * k)])
    icon("restart", lambda d, k, p: [d.arc(p(3, 3, 17, 17), 40, 330, fill=W, width=L * k), d.polygon([p(14, 1), p(18, 7), p(12, 7)], fill=W)])
    icon("back", lambda d, k, p: d.line([p(12, 4), p(6, 10), p(12, 16)], fill=W, width=3 * k, joint="curve"))
    icon("close", lambda d, k, p: [d.line(p(4, 4, 16, 16), fill=W, width=3 * k), d.line(p(16, 4, 4, 16), fill=W, width=3 * k)])
    icon("doc", lambda d, k, p: [d.rounded_rectangle(p(4, 2, 16, 18), radius=2 * k, outline=W, width=L * k),
                                 d.line(p(7, 7, 13, 7), fill=W, width=int(k * 1.5)), d.line(p(7, 10, 13, 10), fill=W, width=int(k * 1.5)),
                                 d.line(p(7, 13, 11, 13), fill=W, width=int(k * 1.5))])
    print("written to", OUT)


def _glow(scale):
    k = scale * SS
    im = canvas(64, 64, scale)
    px = im.load()
    n = 64 * k
    for y in range(n):
        for x in range(n):
            r = math.hypot(x - n / 2, y - n / 2) / (n / 2)
            if r < 1:
                px[x, y] = (255, 255, 255, int(255 * (1 - r) ** 2))
    return im


if __name__ == "__main__":
    main()
