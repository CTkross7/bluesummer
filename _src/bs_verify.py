# -*- coding: utf-8 -*-
"""무결성 + 화질 검사(라플라시안 분산) 및 자동 재생성."""
import os, sys, json, glob
import numpy as np
from PIL import Image
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST, bs_log as L, bs_config as C

MIN_BYTES = 12000
BLUR_THRESH = 90.0
MAX_RETRY = 2


def lap_var(path):
    im = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    lap = (im[:-2, 1:-1] + im[2:, 1:-1] + im[1:-1, :-2] + im[1:-1, 2:]
           - 4.0 * im[1:-1, 1:-1])
    return float(lap.var())


def verify():
    miss, bad, blurry, extra = [], [], [], []
    total_bytes = 0
    want = {"c": ST.WANT_CHAR, "bg": ST.WANT_BG, "ui": ST.WANT_UI}
    for sub, codes in want.items():
        d = os.path.join(ST.DIST, sub)
        have = set(os.path.basename(p)[:-5] for p in glob.glob(d + "/*.webp"))
        for code in codes:
            p = os.path.join(d, code + ".webp")
            if not os.path.exists(p):
                miss.append((sub, code))
                continue
            sz = os.path.getsize(p)
            total_bytes += sz
            if sz < MIN_BYTES:
                bad.append((sub, code, "용량 %dB" % sz))
                continue
            try:
                with Image.open(p) as im:
                    size = im.size
                if sub in ("c", "bg") and size != (C.OUT_W, C.OUT_H):
                    bad.append((sub, code, "해상도 %s" % (size,)))
                    continue
                v = lap_var(p)
                if v < BLUR_THRESH:
                    blurry.append((sub, code, "선예도 %.0f" % v))
            except Exception as e:
                bad.append((sub, code, str(e)))
        for h in sorted(have - set(codes)):
            extra.append((sub, h))

    def pick(sub):
        s = set(c for (x, c) in miss if x == sub)
        s |= set(c for (x, c, _) in bad if x == sub)
        s |= set(c for (x, c, _) in blurry if x == sub)
        return sorted(x for x in s if ST.retry_of(x) <= MAX_RETRY)

    rep = {"total_mb": round(total_bytes / 1024.0 / 1024.0, 2),
           "miss": ["%s/%s" % t for t in miss],
           "bad": ["%s/%s (%s)" % t for t in bad],
           "blurry": ["%s/%s (%s)" % t for t in blurry],
           "extra": ["%s/%s" % t for t in extra],
           "redo_char": pick("c"), "redo_bg": pick("bg"), "redo_ui": pick("ui")}
    with open(os.path.join(ST.BASE, "verify_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)

    L.log("총 용량 %.1f MB" % rep["total_mb"])
    L.log("누락 %d · 손상 %d · 흐림 %d · 규격외 %d"
          % (len(miss), len(bad), len(blurry), len(extra)))
    for x in (rep["miss"][:10] + rep["bad"][:10] + rep["blurry"][:10]):
        L.log("   " + x)
    for x in rep["extra"][:10]:
        L.warn("   규격외 : %s (jsDelivr 는 대소문자를 구분합니다)" % x)
    clean = not (miss or bad or blurry)
    ST.mark("cell09_verify", "done" if clean else "partial",
            "miss=%d bad=%d blur=%d" % (len(miss), len(bad), len(blurry)))
    return rep


def redo(rep=None, budget=None):
    import importlib
    from collections import defaultdict
    rep = rep or verify()
    rc, rb, ru = rep["redo_char"], rep["redo_bg"], rep["redo_ui"]
    L.log("재생성 대상 : 인물 %d / 배경 %d / UI %d" % (len(rc), len(rb), len(ru)))
    if rc:
        import bs_run_char as R
        importlib.reload(R)
        need = defaultdict(list)
        for code in rc:
            need[code[:3]].append(code[3:])
        for ch, combos in need.items():
            L.log("재생성 인물 %s : %s" % (ch, combos))
            try:
                R.redo(ch, sorted(combos), budget=budget)
            except Exception as e:
                L.err("   %s 실패: %s" % (ch, e))
            ST.rescan()
    if rb:
        import bs_bg as BG
        importlib.reload(BG)
        L.log("재생성 배경 : %s" % rb)
        try:
            BG.redo(rb, budget=budget)
        except Exception as e:
            L.err("   배경 실패: %s" % e)
    if ru:
        import bs_ui as UI
        importlib.reload(UI)
        L.log("재생성 UI : %s" % ru)
        try:
            UI.redo(ru)
        except Exception as e:
            L.err("   UI 실패: %s" % e)
    ST.rescan()
    ST.mark("cell09R_redo", "done",
            "char=%d bg=%d ui=%d" % (len(rc), len(rb), len(ru)))
    return rep
