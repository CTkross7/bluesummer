
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST, bs_common as P, bs_engine as E, bs_upload as U, bs_autosave as AS

OUT = os.path.join(ST.DIST, "ui")
SIZE = (1024, 256)

def one(code):
    path = os.path.join(OUT, code + ".webp")
    if E.exists_ok(path):
        return False
    img = E.txt2img(P.ui_prompt(code), 1344, 448, seed=E.seed_of("ui" + code),
                    use_ad=False)
    E.save_webp(img, path, SIZE, 85)
    U.tick(code)
    return True

def run(codes=None, deadline=None):
    codes = codes or ST.UI_CODES
    for c in codes:
        try:
            one(c)
        except Exception as e:
            print("  실패:", c, e)
    ST.rescan(); AS.flush("ui done")
    return True

def redo(codes):
    for c in codes:
        p = os.path.join(OUT, c + ".webp")
        if os.path.exists(p):
            os.remove(p)
    return run(codes)
