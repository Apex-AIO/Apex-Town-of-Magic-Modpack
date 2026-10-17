"""make_bmc_button.py - draws the "Buy me a coffee" button and the settings gear for Apex's Modpack Manager (Ren'Py can't run the web script).

Same look as the buymeacoffee.com button: yellow #FFDD00, black outline, white cup, black "Cookie" font text.
Writes bmc_button.png / bmc_button_hover.png (+ @2 versions for big windows) into Mods/apex_modpack_manager/.
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(WS, "Mods", "apex_modpack_manager")
FONT = os.path.join(WS, "Tools", "fonts", "Cookie-Regular.ttf")
W, H = 200, 48            # size in the game (1066x600 canvas)
SS = 8                    # drawn this many times bigger, then shrunk (smooth edges)


def draw(scale, fill, lift):
    s = scale * SS
    img = Image.new("RGBA", (W * s, H * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    off = 0 if lift else 2 * s
    # shadow, then the button
    d.rounded_rectangle((3 * s, 4 * s, (W - 1) * s, (H - 1) * s), radius=10 * s, fill=(0, 0, 0, 110))
    d.rounded_rectangle((1 * s, 1 * s + off // 2, (W - 3) * s, (H - 3) * s + off // 2), radius=10 * s,
                        fill=fill, outline=(0, 0, 0, 255), width=2 * s)
    y0 = off // 2
    # coffee cup (white, black outline) with a handle and two steam lines
    cx, cy = 26 * s, 26 * s + y0
    cup = (cx - 10 * s, cy - 8 * s, cx + 8 * s, cy + 11 * s)
    d.rounded_rectangle((cx + 4 * s, cy - 4 * s, cx + 15 * s, cy + 6 * s), radius=5 * s, outline=(0, 0, 0, 255),
                        width=2 * s)
    d.polygon([(cup[0], cup[1]), (cup[2], cup[1]), (cup[2] - 2 * s, cup[3]), (cup[0] + 2 * s, cup[3])],
              fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=2 * s)
    d.line((cup[0] - 1 * s, cup[1], cup[2] + 1 * s, cup[1]), fill=(0, 0, 0, 255), width=2 * s)
    for sx in (cx - 5 * s, cx + 2 * s):
        d.arc((sx - 2 * s, cy - 20 * s, sx + 4 * s, cy - 13 * s), 90, 270, fill=(0, 0, 0, 255), width=2 * s)
        d.arc((sx - 2 * s, cy - 15 * s, sx + 4 * s, cy - 9 * s), 270, 90, fill=(0, 0, 0, 255), width=2 * s)
    # text
    font = ImageFont.truetype(FONT, 31 * s)
    text = "Buy me a coffee"
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    tx = 46 * s + ((W - 52) * s - (r - l)) // 2 - l
    ty = (H * s - (b - t)) // 2 - t - 2 * s + y0
    d.text((tx, ty), text, font=font, fill=(0, 0, 0, 255))
    return img.resize((W * scale, H * scale), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fill, lift in (("bmc_button", (255, 221, 0, 255), True), ("bmc_button_hover", (255, 232, 77, 255), False)):
        for scale, suffix in ((1, ""), (2, "@2")):
            draw(scale, fill, lift).save(os.path.join(OUT, name + suffix + ".png"))
    print("written to", OUT)


def gear(scale, color):
    """the settings gear (cog with 8 teeth) shown at the right of each module"""
    import math
    size, s = 22 * scale, 22 * scale * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, r_out, r_in, r_hole = s / 2, s * 0.47, s * 0.34, s * 0.14
    pts = []
    for i in range(8 * 4):
        a = 2 * math.pi * i / 32
        r = r_out if (i % 4) in (1, 2) else r_in
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    d.polygon(pts, fill=color)
    d.ellipse((c - r_in * 0.95, c - r_in * 0.95, c + r_in * 0.95, c + r_in * 0.95), fill=color)
    d.ellipse((c - r_hole, c - r_hole, c + r_hole, c + r_hole), fill=(0, 0, 0, 0))
    return img.resize((size, size), Image.LANCZOS)


def make_gears():
    for name, col in (("gear", (190, 180, 205, 255)), ("gear_hover", (255, 210, 77, 255))):
        for scale, suffix in ((1, ""), (2, "@2")):
            gear(scale, col).save(os.path.join(OUT, name + suffix + ".png"))


if __name__ == "__main__":
    main()
    make_gears()
