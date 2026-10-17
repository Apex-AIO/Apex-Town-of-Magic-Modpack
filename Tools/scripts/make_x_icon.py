"""make_x_icon.py OUT.png - draws the pixel-art red X icon (66x75, same size as the game's attire icons)."""
import sys
from PIL import Image
W, H, S = 22, 25, 3                       # drawn on a 22x25 grid, scaled x3 = 66x75 (game pixel size)
grid = [[None] * W for _ in range(H)]
FILL, LIGHT, EDGE = (220, 30, 40, 255), (255, 110, 110, 255), (70, 0, 8, 255)
x0, y0, n = 4, 4, 14                      # X spans 14 cells, top-left at (4,4)
inside = set()
for i in range(n):
    for dx in (0, 1, 2):
        inside.add((x0 + i + dx - 1, y0 + i))
        inside.add((x0 + n - 1 - i + dx - 1, y0 + i))
for (x, y) in inside:
    grid[y][x] = FILL
for (x, y) in inside:                     # highlight: the upper-left pixel of each stroke row
    if (x - 1, y) not in inside and (x, y - 1) not in inside:
        grid[y][x] = LIGHT
for y in range(H):                        # 1-cell dark outline
    for x in range(W):
        if grid[y][x] is None and any((x + a, y + b) in inside for a in (-1, 0, 1) for b in (-1, 0, 1)):
            grid[y][x] = EDGE
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
for y in range(H):
    for x in range(W):
        if grid[y][x]:
            img.putpixel((x, y), grid[y][x])
img.resize((W * S, H * S), Image.NEAREST).save(sys.argv[1])
