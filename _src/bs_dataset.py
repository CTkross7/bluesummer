# -*- coding: utf-8 -*-
"""selected/ -> kohya 규격 데이터셋 + 캡션.
   선별 이미지가 작으면 4x-AnimeSharp 우세 블렌드로 재선명화 후 리사이즈."""
import os, sys, glob, shutil
from PIL import Image
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_config as C, bs_common as K, bs_state as ST, bs_log as L

CLASS = "1girl"

FIXED = {
 "HRM": "tanned skin, long dark brown hair, high ponytail, amber eyes, athletic body",
 "SRA": "pale skin, black bob cut, blunt bangs, dark green eyes, glasses, slender",
 "MJO": "olive skin, long wavy ash brown hair, half updo, hazel eyes, mole under eye, tall",
 "HTI": "fair skin, short messy red orange hair, freckles, yellow green eyes, petite",
 "KYS": "very pale skin, long platinum silver hair, grey blue eyes, half-lidded eyes, tall",
 "LCH": "beige skin, long chestnut brown wavy hair, side ponytail, brown eyes",
 "BRW": "pale skin, chin length pale blue hair, asymmetric bangs, pale grey eyes, headphones",
 "CSM": "light brown low twin braids, round hazel eyes, floral hairpin",
 "JHO": "deeply tanned skin, short black undercut bob, dark grey eyes, muscular, shark tooth necklace",
 "YDH": "fair skin, medium orange hair, half-up bun, drooping green eyes, leaf hairpin",
 "PSA": "pale skin, long black hair, purple inner hair, dark purple eyes, eye bags, choker",
 "OMR": "porcelain skin, very long white hair, heterochromia, blue eye, gold eye, red ribbon",
}

VARI_TAGS = [
 "portrait, close-up, front view, looking at viewer, neutral expression, simple background",
 "portrait, close-up, front view, gentle smile, simple background",
 "portrait, close-up, three quarter view, calm expression, simple background",
 "portrait, close-up, from side, profile, simple background",
 "portrait, close-up, looking up, blush, simple background",
 "portrait, close-up, looking down, closed eyes, simple background",
 "upper body, front view, looking at viewer, simple background",
 "upper body, three quarter view, arms crossed, simple background",
 "upper body, from behind, looking back, simple background",
 "upper body, laughing, open mouth, simple background",
 "upper body, serious expression, simple background",
 "upper body, surprised, wide eyes, simple background",
 "cowboy shot, standing, front view, simple background",
 "cowboy shot, standing, three quarter view, simple background",
 "cowboy shot, hands on hips, simple background",
 "full body, standing, front view, simple background",
]
OUTFIT_TAGS = ["uniform, work clothes", "casual clothes", "loungewear, indoor clothes"]


def build(code, sharpen=True):
    code = code.upper()
    trig = K.CHARS[code]["trigger"]
    src = os.path.join(ST.BASE, "lora", code, "selected")
    dst = os.path.join(ST.BASE, "lora", code, "img",
                       "%d_%s %s" % (C.LORA_REPEATS, trig, CLASS))
    if not os.path.isdir(src):
        L.warn("[%s] selected 폴더 없음" % code)
        return 0
    files = sorted(glob.glob(src + "/*.png") + glob.glob(src + "/*.jpg"))
    if not files:
        L.warn("[%s] selected 비어있음" % code)
        return 0
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst, exist_ok=True)
    for sub in ("model", "log"):
        os.makedirs(os.path.join(ST.BASE, "lora", code, sub), exist_ok=True)

    E = None
    if sharpen:
        try:
            import bs_engine as _E
            if _E.health(verbose=False):
                E = _E
        except Exception:
            E = None

    for i, f in enumerate(files, 1):
        base = "%03d" % i
        im = Image.open(f).convert("RGB")
        if E is not None and min(im.size) < C.DATASET_RES * 1.2:
            try:
                im = E.refine(im, scale=1.5, blend=0.75)
            except Exception as e:
                L.warn("   refine 생략: %s" % e)
        w, h = im.size
        s = min(w, h)
        im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
        im.resize((C.DATASET_RES, C.DATASET_RES), Image.LANCZOS).save(
            os.path.join(dst, base + ".png"), "PNG")
        try:
            n = int(os.path.splitext(os.path.basename(f))[0])
        except ValueError:
            n = i
        vari = VARI_TAGS[(n - 1) % len(VARI_TAGS)]
        outf = OUTFIT_TAGS[((n - 1) // len(VARI_TAGS)) % len(OUTFIT_TAGS)]
        cap = ("%s, %s, solo, adult woman, %s, %s, %s, "
               "masterpiece, best quality, very aesthetic, newest"
               % (trig, CLASS, FIXED[code], outf, vari))
        with open(os.path.join(dst, base + ".txt"), "w", encoding="utf-8") as g:
            g.write(cap)

    steps = len(files) * C.LORA_REPEATS
    L.ok("[%s] %d장 -> %s | 1epoch=%d steps" % (code, len(files), dst, steps))
    return len(files)


def build_all():
    n = 0
    for c in K.CHARS:
        n += build(c)
    ST.mark("cellA3_dataset", "done", "images=%d" % n)
    return n
