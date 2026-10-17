ART TOOLKIT - the game's sprites, catalogued (all run with ComfyUI's Python:
    "%USERPROFILE%\Documents\ComfyUI\.venv\Scripts\python.exe" Tools\art\<tool>.py )
Output goes to  Claude Workspace\Catalog\  (never published: it contains the game's art).

BUILD (after a game update, or when you want fresh status flags)
  catalog.py       every character sprite (29,155) read straight from images1/2.rpa: size, frames, unique frames,
                   visible/glow/shadow pixels, colour, skin share, exact pixel hash, character (Enemy list, Male flag),
                   scenes that name it, our status (HD made / queued / seen in game)        -> Catalog\art.db  (~100 s)
  roles.py         what each sprite IS (face, outfit_body, body, head, hair, clothing, glow, shadow, ghost ...),
                   which HD recipe it needs, and its CONTEXT (layers drawn under it) chosen by measuring pixel coverage
                   (best-covering head type: forward/down/felt/up/raised/tilt/front/lowered/back)   (~90 s)
  stacks_check.py  compares that context with the REAL layer stacks the game builds (recorded by the debug bridge
                   into game\claude_debug\stacks.txt); --import stores them in art.db.  2026-10-18: 3422 OK, 2 off.

USED BY THE PIPELINE
  artdb.py         lookup module: hd_batch.py takes recipe + context from it, and "render once, copy" twins
                   (same pixels AND same layers under it -> same HD result; 44% of the game's files are copies).
                   hd_queue.py uses it to say how many renders a run really needs.

CHECK / DEBUG
  audit.py         every rendered + queued sprite: floating face layers, recipe changes, copies    -> Catalog\audit.txt
  redo_check.py    rendered files made with a worse context / wrong recipe than the catalog gives;
                   --write -> Tools\upscale\sets\redo.txt (run_hd_pending.bat redoes it first, then retires it)
  whats_under.py   <sprite name>: which layers of its pose cover it, how much, their roles
  qa.py            HD vs original: drift / structure / outline per sprite -> Catalog\qa.tsv, qa_worst.png;
                   --sheet a,b,c  side-by-side sheet (original | HD shrunk | HD).  Numbers miss subtle face problems:
                   for faces trust the sheet, not the score.
  atlas.py         local web pages: character -> pose -> layer cards (original | on its context | HD) with role,
                   recipe, coverage, frames, twins, scenes.  Catalog\atlas\index.html (open in any browser);
                   --folder evie for one whole character, --all for everything
  dither_test.py   checkerboard dithering (blush) turns into stripes when upscaled; smoothing it first gives a soft
                   blush.  --count / sprite names -> Catalog\dither_test.png.  hd_batch: SMOOTH_DITHER / --smooth-dither

NAMING FACTS LEARNED (2026-10-18)
  * Celica: the pose file is her body; layers are <pose>_<part>.  Real drawing order: body, back hair, neck, behind-arm,
    breasts, clothing, (arms), head, face, front hair, bottoms, arms.  Several head types per pose (see roles.py HEADS).
  * Most other characters: <pose> = only the floor shadow; <pose>_face_<expr> = eyes/mouth;
    <pose>_face_<expr>_<outfit> (normalpanties, nopanties, piratepanties ...) = the whole body with a blank face.
  * Nel (ghost): her _face_ files are her whole see-through body.  "...grab_<x>_<monster>_face_<expr>" = the monster's
    face on its grab layer.

BACKGROUNDS (2026-10-18)
  bg_catalog.py    images/BG, BGANIM, EVENT -> art.db table "backgrounds" + Catalog/backgrounds.txt.
                   All BG are 532x374.  A location = base picture (window holes / see-through sky are transparent)
                   + time-of-day window views (_day/_evening/_night, drawn BEHIND the holes) + _lights/_glow overlays.
  ..\upscale\bg_batch.py + run_hd_backgrounds.bat   HD backgrounds with the locked recipe B (2026-10-18): ReboutBlend x8
                   -> x4 -> detailer 0.30 + tile CN 0.8 + DetailerILv2, scenery prompt.  Glow overlays and animation
                   frames: upscale only (no flicker).  Seen-in-game first.  @2 + @4 into Mods/hd_sprites_mod/images/BG...
                   bg_test.py = the A/B/C comparison that chose it (Upscale/bg_test).

PROGRESS (2026-10-18)
  progress.py      HD done vs. the whole game, counted in pictures (male characters and empty files left out):
                   characters (per character), backgrounds (per kind), interface (planned later).
                   Writes Catalog/progress.json, docs/images/progress*.svg and the README block between
                   <!-- PROGRESS:START --> and <!-- PROGRESS:END -->.  build_modpack.py runs it on every build and
                   embeds the numbers in the Mod Manager's HD Project page.
