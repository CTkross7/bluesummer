# -*- coding: utf-8 -*-
"""UI 배너 8장 (1216x192 -> 1000x160 webp) + 한글 문구 삽입."""
import os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_config as C, bs_engine as E, bs_state as ST, bs_upload as U, bs_log as L

DEST = os.path.join(ST.DIST, "ui")

HEAD = ("masterpiece, best quality, amazing quality, very aesthetic, absurdres, newest, "
        "ui banner design, horizontal wide banner, minimal flat vector design, "
        "no humans, clean, high contrast, sharp focus, official art")
NEG = C.NEG_BG + ", letter, character, cluttered, texture noise, gradient banding"

UI = {
 "status": "deep navy blue background, subtle white wave silhouette on the right, thin horizontal white line, empty left space for a title, calm and clean",
 "album": "dark teal background, scattered polaroid photo frames, film grain texture, soft warm light leak, nostalgic",
 "talk": "light sky blue background, simple rounded chat bubble icons, minimal, friendly",
 "town": "grey blue background, retro bulletin board texture, thin frame lines, old internet forum aesthetic",
 "map": "cream paper texture background, hand drawn coastline map lineart, dotted route lines, small compass rose, vintage",
 "card": "ivory paper texture, postage stamp corner, circular postmark, thin airmail border stripes, warm and quiet",
 "sns": "white background, minimal line icons of heart and comment, thin grey divider, modern clean feed style",
 "radio": "very dark blue background, glowing radio dial and frequency scale, faint sound wave lines, late night mood, cyan accent",
}

TEXT = {"status": "BLUE SUMMER", "album": "SUMMER ALBUM", "talk": "여름톡",
        "town": "해윤타운", "map": "해윤시 MAP", "card": "POSTCARD · HAEYUN",
        "sns": "해윤 피드", "radio": "89.1MHz 새벽바다"}
DARK = {"status", "album", "radio", "town"}
FONT = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"


def _label(path, key):
    if not os.path.exists(FONT) or not os.path.exists(path):
        return False
    try:
        im = Image.open(path).convert("RGB")
        d = ImageDraw.Draw(im)
        f = ImageFont.truetype(FONT, 52)
        fg = (255, 255, 255) if key in DARK else (30, 40, 60)
        sh = (0, 0, 0) if key in DARK else (255, 255, 255)
        d.text((42, 52), TEXT[key], font=f, fill=sh)
        d.text((40, 50), TEXT[key], font=f, fill=fg)
        im.save(path, "WEBP", quality=C.WEBP_QUALITY, method=C.WEBP_METHOD)
        return True
    except Exception as e:
        L.warn("텍스트 삽입 실패 %s: %s" % (key, e))
        return False


def _gen(keys, overwrite=False):
    os.makedirs(DEST, exist_ok=True)
    pr = L.Progress(len(keys), "UI")
    fails = []
    for k in keys:
        if k not in UI:
            L.warn("미정의 UI 코드 %s" % k)
            continue
        path = os.path.join(DEST, k + ".webp")
        if (not overwrite) and os.path.exists(path) and os.path.getsize(path) > 4000:
            pr.step("%s skip" % k)
            continue
        try:
            im, _ = E.txt2img("%s, %s, BREAK, soft volumetric lighting" % (HEAD, UI[k]),
                              NEG, seed=-1, width=1216, height=192, steps=26, cfg=4.5,
                              hr=True, hr_steps=10, hr_denoise=0.35, adetailer=False,
                              hr_scale=1.5)
            try:
                im = E.refine(im, scale=1.2, blend=0.7)
            except Exception:
                pass
            im = im.resize((1000, 160), Image.LANCZOS)
            im.save(path, "WEBP", quality=C.WEBP_QUALITY, method=C.WEBP_METHOD)
            _label(path, k)
            pr.step("%s.webp" % k)
        except Exception as e:
            L.err("UI %s 실패: %s" % (k, e))
            fails.append(k)
    pr.done()
    ST.rescan()
    U.push("ui", force=True)
    return fails


def run(overwrite=False):
    return _gen(list(UI.keys()), overwrite)


def redo(keys):
    return _gen(list(keys), True)


if __name__ == "__main__":
    run()
