# -*- coding: utf-8 -*-
"""candidates -> selected 자동 선별. 선예도 상위 + dHash 중복 제거."""
import os, sys, glob, shutil
import numpy as np
from PIL import Image
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_config as C, bs_common as K, bs_state as ST, bs_log as L


def sharpness(path):
    im = np.asarray(Image.open(path).convert("L").resize((512, 512)), dtype=np.float32)
    lap = (im[:-2, 1:-1] + im[2:, 1:-1] + im[1:-1, :-2] + im[1:-1, 2:]
           - 4.0 * im[1:-1, 1:-1])
    return float(lap.var())


def dhash(path, size=8):
    im = np.asarray(Image.open(path).convert("L").resize((size + 1, size)),
                    dtype=np.int16)
    bits = (im[:, 1:] > im[:, :-1]).flatten()
    v = 0
    for b in bits:
        v = (v << 1) | int(b)
    return v


def hamming(a, b):
    return bin(a ^ b).count("1")


def select(code, top_n=None, min_dist=6):
    top_n = top_n or C.LORA_SELECT_N
    src = os.path.join(ST.BASE, "lora", code, "candidates")
    dst = os.path.join(ST.BASE, "lora", code, "selected")
    os.makedirs(dst, exist_ok=True)
    files = sorted(glob.glob(src + "/*.png"))
    if not files:
        L.warn("[%s] 후보 없음" % code)
        return 0
    if len(os.listdir(dst)) >= min(top_n, len(files)) * 0.8:
        L.log("[%s] selected 이미 %d장 - 건너뜀" % (code, len(os.listdir(dst))))
        return len(os.listdir(dst))
    scored = []
    for f in files:
        try:
            scored.append((sharpness(f), dhash(f), f))
        except Exception as e:
            L.warn("   점수 계산 실패 %s: %s" % (os.path.basename(f), e))
    scored.sort(reverse=True, key=lambda x: x[0])
    picked = []
    for s, h, f in scored:
        if len(picked) >= top_n:
            break
        if all(hamming(h, ph) >= min_dist for _, ph, _ in picked):
            picked.append((s, h, f))
    if len(picked) < min(12, len(scored)):
        for item in scored:
            if len(picked) >= min(top_n, len(scored)):
                break
            if item not in picked:
                picked.append(item)
    for _, _, f in picked:
        shutil.copy2(f, os.path.join(dst, os.path.basename(f)))
    L.ok("[%s] %d장 중 %d장 선별 (선예도 %.0f~%.0f, 중복 제거 포함)"
         % (code, len(files), len(picked),
            picked[-1][0] if picked else 0, picked[0][0] if picked else 0))
    return len(picked)


def select_all():
    total = 0
    for c in K.CHARS:
        total += select(c)
    ST.mark("cellA2_select", "done", "selected=%d" % total)
    return total
