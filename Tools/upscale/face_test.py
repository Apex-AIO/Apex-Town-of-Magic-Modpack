"""face_test.py - finds out why Celica's mouth/nose break, and tests a fix.  (needs ComfyUI running)

The mouth is a ~4x2 pixel island on its own layer (celica_face_normal); the skin under it is another layer
(celica_headforward).  Upscaling the face layer on its own = the AI sees a lone pink blob with nothing around it.

Head stack shown in each column (3x close-up of the @2 result):
  1 vanilla (enlarged)
  2 current method: every layer alone, detailer 0.28
  3 every layer alone, NO detailer                      -> is it the upscaler or the detailer?
  4 IN CONTEXT: face layer upscaled/detailed while lying on the head, detailer 0.28, then cut back out
  5 in context, detailer 0.10
Output: Upscale/face_test.png (opens by itself)
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spandrel
from compare_upscalers import WS, MODEL_DIR, ALPHA_MODEL, DEV, font, upscale4
from refine_compare import color_match, detailer, comfy, COMFY
from hd_batch import full_sheet

C = "images/CHAR/celica/%s-530-530-1.png"
BELOW = ["celica_headforwardhair_normalb", "celica_headforwardneck", "celica_headforward"]   # under the face
FACE = "celica_face_normal"
ABOVE = ["celica_headforwardhair_normal"]
BOX = (245, 62, 312, 155)                                                                  # head area at 1x


def stack(layers):
    out = Image.new("RGBA", layers[0].size, (0, 0, 0, 0))
    for l in layers:
        out.alpha_composite(l)
    return out


def main():
    try:
        comfy("/system_stats")
    except Exception:
        sys.exit("ComfyUI is not running at %s - start ComfyUI first." % COMFY)
    L = spandrel.ModelLoader()
    model = L.load_from_file(os.path.join(MODEL_DIR, "4x-ReboutBlend.pth")).to(DEV).eval()
    amodel = L.load_from_file(os.path.join(MODEL_DIR, ALPHA_MODEL)).to(DEV).eval()

    def x8(img):
        w, h = img.size
        x4 = upscale4(model, amodel, img)
        return color_match(upscale4(model, amodel, x4.resize((w * 2, h * 2), Image.LANCZOS)), img)

    van = {n: full_sheet(C % n) for n in BELOW + [FACE] + ABOVE}
    print("upscaling layers...", flush=True)
    up = {n: x8(van[n]) for n in van}                               # every layer alone, no detailer
    print("detailer 0.28 on each layer alone...", flush=True)
    det = {n: detailer(up[n], 0.28) for n in van}

    def in_context(denoise):
        # face drawn onto the layers below it, upscaled + detailed together, then cut back out with the face's own alpha
        ctx = stack([van[n] for n in BELOW] + [van[FACE]])
        u = x8(ctx)
        if denoise:
            u = detailer(u, denoise)
        rgb = np.array(u)[..., :3]
        a = np.array(up[FACE])[..., 3]
        return Image.fromarray(np.dstack([rgb, a]), "RGBA")

    print("in context, detailer 0.28...", flush=True)
    ctx28 = in_context(0.28)
    print("in context, detailer 0.10...", flush=True)
    ctx10 = in_context(0.10)

    def at2(d, face):
        layers = [d[n] for n in BELOW] + [face] + [d[n] for n in ABOVE]
        return stack([l.resize((1060, 1060), Image.LANCZOS) for l in layers])

    cols = [
        ("1 Vanilla", stack([van[n] for n in BELOW + [FACE] + ABOVE]).resize((1060, 1060), Image.NEAREST)),
        ("2 Now: layers alone + detailer 0.28", at2(det, det[FACE])),
        ("3 Layers alone, no detailer", at2(up, up[FACE])),
        ("4 Face in context + detailer 0.28", at2(det, ctx28)),
        ("5 Face in context + detailer 0.10", at2(det, ctx10)),
    ]
    b = tuple(v * 2 for v in BOX)
    z = 3
    cw, ch = (b[2] - b[0]) * z, (b[3] - b[1]) * z
    can = Image.new("RGBA", (20 + len(cols) * (cw + 20), ch + 60), (34, 24, 42, 255))
    d = ImageDraw.Draw(can)
    for i, (n, im) in enumerate(cols):
        x = 20 + i * (cw + 20)
        d.text((x, 14), n, font=font(16), fill=(240, 220, 255))
        can.alpha_composite(im.crop(b).resize((cw, ch), Image.NEAREST), (x, 45))
    out = os.path.join(WS, "Upscale", "face_test.png")
    can.convert("RGB").save(out)
    print("wrote", out)
    if "--no-open" not in sys.argv:
        os.startfile(out)


if __name__ == "__main__":
    main()
