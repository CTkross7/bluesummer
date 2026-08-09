# -*- coding: utf-8 -*-
"""LoRA 학습 소스 생성 (Hires + 업스케일러 2종 적용)."""
import os, sys, time
from PIL import Image
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_config as C, bs_common as K, bs_engine as E, bs_state as ST, bs_log as L

VARI = [
 ("portrait, close-up, face focus", "front view, looking at viewer, neutral expression"),
 ("portrait, close-up, face focus", "front view, gentle smile"),
 ("portrait, close-up, face focus", "three quarter view, calm"),
 ("portrait, close-up, face focus", "from side, profile view"),
 ("portrait, close-up, face focus", "looking up, slight blush"),
 ("portrait, close-up, face focus", "looking down, closed eyes"),
 ("upper body", "front view, looking at viewer, arms relaxed"),
 ("upper body", "three quarter view, arms crossed"),
 ("upper body", "from behind, looking back over shoulder"),
 ("upper body", "laughing, open mouth"),
 ("upper body", "serious expression, direct gaze"),
 ("upper body", "surprised, wide eyes"),
 ("cowboy shot", "standing, front view, full outfit visible"),
 ("cowboy shot", "standing, three quarter view"),
 ("cowboy shot", "hands on hips, confident"),
 ("full body", "standing, front view, whole outfit"),
]
BGS = ["simple background, white background",
       "simple background, light grey background",
       "blurred outdoor summer background, bokeh"]


def run(code, overwrite=False, limit=None, budget=None):
    code = code.upper()
    d = K.CHARS[code]
    OUT = os.path.join(ST.BASE, "lora", code, "candidates")
    os.makedirs(OUT, exist_ok=True)
    total = limit or C.LORA_SRC_N
    pr = L.Progress(total, "LoRA소스 " + code)
    n = 0
    for oi, outfit in enumerate(["W", "C", "N"]):
        for vi, (frame, extra) in enumerate(VARI):
            n += 1
            if n > total:
                break
            path = os.path.join(OUT, "%03d.png" % n)
            if (not overwrite) and os.path.exists(path):
                pr.step("skip %03d" % n)
                continue
            if budget is not None and not budget.can(C.EST_LORASRC_MIN):
                L.warn("[%s] 시간 예산 부족 - LoRA 소스 중단 (%d/%d)" % (code, n - 1, total))
                return False
            bg = BGS[(oi + vi) % 3]
            prompt = ("%s, %s, %s, %s, %s, %s, %s, soft even lighting, clean lineart, "
                      "BREAK, %s" % (C.QUALITY_HEAD, C.STYLE_BA, d["anchor"],
                                     d["outfits"][outfit], frame, extra, bg, C.TAIL))
            try:
                im, _ = E.txt2img(prompt, C.NEG_DATASET,
                                  seed=K.seed_of(code, outfit, "%02d" % vi, salt=7),
                                  adetailer=True, hands=False)
                im = E.refine(im, scale=1.3, blend=0.7)
                w, h = im.size
                s = min(w, h)
                top = int((h - s) * 0.25)
                im = im.crop(((w - s) // 2, top, (w - s) // 2 + s, top + s))
                im.resize((C.DATASET_RES, C.DATASET_RES), Image.LANCZOS).save(path, "PNG")
                pr.step("%03d.png" % n)
            except Exception as e:
                L.err("[%s] %03d 실패: %s" % (code, n, e))
    pr.done()
    return True


def run_all(codes=None, **kw):
    for c in (codes or list(K.CHARS)):
        run(c, **kw)


if __name__ == "__main__":
    run(sys.argv[1])
