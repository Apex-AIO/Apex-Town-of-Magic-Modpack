"""make_inf_icon.py OUTDIR - draws the pixel-art infinity icons (green / orange / red), 66x75 like the game's icons."""
import sys, os, math
import numpy as np
from PIL import Image
W, H, S = 33, 37, 2                       # drawn on a 33x37 grid, scaled x2 (+ padding) -> 66x75
COLORS = {                                # (fill, light, dark edge)
    "green":  ((60, 200, 70), (170, 255, 150), (10, 60, 15)),
    "orange": ((240, 140, 30), (255, 215, 130), (90, 40, 0)),
    "red":    ((220, 30, 40), (255, 130, 120), (70, 0, 8)),
}
# distance from each grid cell to a lemniscate of Bernoulli (sideways 8)
cx, cy, a = 16.0, 15.0, 13.5
pts = []
for i in range(2000):
    t = i / 2000.0 * 2 * math.pi
    d = 1 + math.sin(t) ** 2
    pts.append((cx + a * math.cos(t) / d, cy + a * math.sin(t) * math.cos(t) / d * 1.25))
pts = np.array(pts)
yy, xx = np.mgrid[0:H, 0:W]
cells = np.stack([xx.ravel() + 0.5, yy.ravel() + 0.5], 1)
dist = np.sqrt(((cells[:, None, :] - pts[None, :, :]) ** 2).sum(-1)).min(1).reshape(H, W)
inside = dist <= 1.9
edge = (dist <= 2.9) & ~inside
# highlight on the upper side of the stroke
up = np.roll(inside, 1, 0)
light = inside & ~up
os.makedirs(sys.argv[1], exist_ok=True)
for name, (fill, lt, dk) in COLORS.items():
    img = np.zeros((H, W, 4), np.uint8)
    img[edge] = dk + (255,)
    img[inside] = fill + (255,)
    img[light] = lt + (255,)
    im = Image.fromarray(img).resize((W * S, H * S), Image.NEAREST)
    out = Image.new("RGBA", (66, 75), (0, 0, 0, 0))
    out.paste(im, (0, 2))
    out.save(os.path.join(sys.argv[1], "helper_%s.png" % name))
