"""Make a README GIF from recorded frames (Tools/media/rec_helpers.py).

    python make_gif.py <frames dir> <out.gif> [--crop x0,y0,x1,y1] [--width 760] [--hold i:ms,...] [--ms 120]

--crop is in the 1066x600 game canvas (scaled to the screenshot size); --hold sets how long given frames stay;
without times.txt every frame lasts --ms.  Colours: one shared adaptive palette, so the GIF stays small.
"""
import os, sys, argparse
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--crop"); ap.add_argument("--width", type=int, default=760)
ap.add_argument("--hold", default=""); ap.add_argument("--ms", type=int, default=120)
ap.add_argument("--colors", type=int, default=192)
ap.add_argument("--frames", default="", help="e.g. 0-12 or 3,5,7-9")
a = ap.parse_args()

files = sorted(f for f in os.listdir(a.src) if f.endswith(".png"))
if a.frames:
    keep = set()
    for part in a.frames.split(","):
        lo, _, hi = part.partition("-")
        keep.update(range(int(lo), int(hi or lo) + 1))
    files = [f for f in files if int(f[:4]) in keep]
frames = []
for f in files:
    im = Image.open(os.path.join(a.src, f)).convert("RGB")
    if a.crop:
        x0, y0, x1, y1 = [float(v) for v in a.crop.split(",")]
        s = im.width / 1066.0
        im = im.crop((int(x0 * s), int(y0 * s), int(x1 * s), int(y1 * s)))
    if im.width != a.width:
        im = im.resize((a.width, int(im.height * a.width / im.width)), Image.LANCZOS)
    frames.append(im)

times = os.path.join(a.src, "times.txt")
if os.path.exists(times) and not a.frames:
    t = [float(x) for x in open(times).read().split()]
    dur = [max(20, int(round((t[i + 1] - t[i]) * 1000))) for i in range(len(t) - 1)] + [a.ms]
    dur = dur[:len(frames)] + [a.ms] * (len(frames) - len(dur))
else:
    dur = [a.ms] * len(frames)
for h in filter(None, a.hold.split(",")):
    i, ms = h.split(":")
    i = int(i) if int(i) >= 0 else len(frames) + int(i)
    dur[i] = int(ms)

# one palette for every frame (from a strip of samples), no dithering noise between frames
sample = Image.new("RGB", (frames[0].width, frames[0].height * min(len(frames), 8)))
for k, im in enumerate(frames[:: max(1, len(frames) // 8)][:8]):
    sample.paste(im, (0, k * im.height))
pal = sample.quantize(colors=a.colors, method=Image.MEDIANCUT)
out = [im.quantize(palette=pal, dither=Image.NONE) for im in frames]
out[0].save(a.out, save_all=True, append_images=out[1:], duration=dur, loop=0, optimize=True, disposal=1)
print("%s: %d frames, %.0f KB, %dx%d" % (a.out, len(out), os.path.getsize(a.out) / 1024, out[0].width, out[0].height))
