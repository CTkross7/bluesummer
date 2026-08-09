
# -*- coding: utf-8 -*-
import os, sys, glob, shutil
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST, bs_common as P

SEL = os.path.join(ST.BASE, "lora_src", "selected")
DS  = os.path.join(ST.BASE, "dataset")
TOML = os.path.join(ST.BASE, "toml")
REPEATS = 6

def caption(code):
    """외형 태그는 트리거로 흡수 → 의상/표정/구도만 캡션에 남긴다."""
    return P.TRIGGER[code]

def run(chars=None):
    chars = chars or ST.CHARS
    os.makedirs(TOML, exist_ok=True)
    for c in chars:
        src = os.path.join(SEL, c)
        if not os.path.isdir(src) or not glob.glob(src + "/*.png"):
            print(f"{c}: 선별본 없음 — 건너뜀")
            continue
        img_dir = os.path.join(DS, c, f"{REPEATS}_{P.TRIGGER[c]}")
        os.makedirs(img_dir, exist_ok=True)
        for f in sorted(glob.glob(src + "/*.png")):
            b = os.path.basename(f)
            d = os.path.join(img_dir, b)
            if not os.path.exists(d):
                shutil.copy2(f, d)
            txt = os.path.splitext(d)[0] + ".txt"
            if not os.path.exists(txt):
                with open(txt, "w", encoding="utf-8") as fh:
                    fh.write(caption(c))
        toml = f"""[general]
shuffle_caption = false
caption_extension = ".txt"
keep_tokens = 1

[[datasets]]
resolution = 768
batch_size = 1
enable_bucket = true
min_bucket_reso = 512
max_bucket_reso = 1024
bucket_no_upscale = false

  [[datasets.subsets]]
  image_dir = "{img_dir}"
  num_repeats = {REPEATS}
"""
        with open(os.path.join(TOML, f"{c}.toml"), "w", encoding="utf-8") as fh:
            fh.write(toml)
        n = len(glob.glob(img_dir + "/*.png"))
        print(f"{c}: {n}장 · repeats {REPEATS} · toml 작성")
        ST.mark(f"dataset_{c}", "done", str(n))
    return True
