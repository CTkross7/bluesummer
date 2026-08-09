
# -*- coding: utf-8 -*-
import os, sys, time
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST, bs_common as P, bs_engine as E, bs_upload as U, bs_autosave as AS

OUT = os.path.join(ST.DIST, "bg")
SIZE = (1280, 720)

def one(code):
    path = os.path.join(OUT, code + ".webp")
    if E.exists_ok(path):
        return False
    img = E.txt2img(P.bg_prompt(code), 1344, 768, seed=E.seed_of("bg" + code),
                    use_ad=False)
    E.save_webp(img, path, SIZE, 80)
    U.tick(code)
    return True

def run(codes=None, deadline=None):
    codes = codes or ST.BG_CODES
    todo = [c for c in codes if not E.exists_ok(os.path.join(OUT, c + ".webp"))]
    print(f"배경 {len(todo)}장 생성")
    for i, c in enumerate(todo):
        if deadline and time.time() > deadline:
            U.flush("bg partial"); return False
        try:
            one(c)
        except Exception as e:
            print("  실패:", c, e)
        if (i + 1) % 10 == 0:
            print(f"   {i+1}/{len(todo)}")
    ST.rescan(); AS.flush("bg done")
    return True

def redo(codes):
    for c in codes:
        p = os.path.join(OUT, c + ".webp")
        if os.path.exists(p):
            os.remove(p)
        try:
            one(c)
        except Exception as e:
            print("  redo 실패:", c, e)
    U.flush("redo bg")
