
# -*- coding: utf-8 -*-
import os, sys, time
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST, bs_common as P, bs_engine as E, bs_upload as U, bs_autosave as AS

OUT = os.path.join(ST.DIST, "c")
SIZE = (640, 960)

def one(code):
    c, o, e = code[:3], code[3], code[4:]
    path = os.path.join(OUT, code + ".webp")
    if E.exists_ok(path):
        return False
    pr = P.char_prompt(c, o, e)
    img = E.txt2img(pr, 832, 1216, seed=E.seed_of(code), use_ad=True,
                    face_prompt=f"{P.TRIGGER[c]}, detailed face, clean eyes")
    E.save_webp(img, path, SIZE, 82)
    U.tick(code)
    return True

def run(chars=None, deadline=None):
    chars = chars or ST.CHARS
    for c in chars:
        todo = [f"{c}{o}{e}" for o in ST.OUTFIT for e in ST.EMO
                if not E.exists_ok(os.path.join(OUT, f"{c}{o}{e}.webp"))]
        if not todo:
            print(f"{c}: 60/60 완료")
            continue
        print(f"── {c} : {len(todo)}장 남음")
        for i, code in enumerate(todo):
            if deadline and time.time() > deadline:
                U.flush("char partial"); return False
            try:
                one(code)
            except Exception as ex:
                print("  실패:", code, ex)
            if (i + 1) % 20 == 0:
                print(f"   {i+1}/{len(todo)}")
        ST.rescan(); AS.flush(f"char {c}")
    return True

def redo(ch, combos):
    for cb in combos:
        p = os.path.join(OUT, f"{ch}{cb}.webp")
        if os.path.exists(p):
            os.remove(p)
        try:
            one(f"{ch}{cb}")
        except Exception as e:
            print("  redo 실패:", ch + cb, e)
    U.flush(f"redo {ch}")
