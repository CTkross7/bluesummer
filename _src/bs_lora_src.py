
# -*- coding: utf-8 -*-
import os, sys, time
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST, bs_common as P, bs_engine as E, bs_autosave as AS

CAND = os.path.join(ST.BASE, "lora_src", "candidates")
N = 48

def run(chars=None, deadline=None):
    chars = chars or ST.CHARS
    for c in chars:
        d = os.path.join(CAND, c)
        os.makedirs(d, exist_ok=True)
        have = len([f for f in os.listdir(d) if f.endswith(".png")])
        if have >= N:
            print(f"{c}: 이미 {have}장 — 건너뜀")
            continue
        print(f"── {c} 소스 생성 ({have}→{N})")
        for i in range(have, N):
            if deadline and time.time() > deadline:
                print("   시간 예산 도달 — 중단(다음 세션에서 이어감)")
                return False
            p = P.src_prompt(c, i)
            img = E.txt2img(p, 832, 1216, seed=E.seed_of(f"{c}src{i}"),
                            use_ad=True, face_prompt="detailed face, clean eyes")
            img.save(os.path.join(d, f"{c}_{i:03d}.png"))
            if (i + 1) % 12 == 0:
                print(f"   {i+1}/{N}")
        ST.mark(f"lora_src_{c}", "done", str(N))
        AS.flush(f"lora_src {c}")
    return True
