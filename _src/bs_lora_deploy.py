
# -*- coding: utf-8 -*-
import os, sys, json, glob, shutil, requests
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST, bs_forge as F

ENV = json.load(open("/kaggle/temp/bs_env.json", encoding="utf-8"))
DST = ENV["cfg"]["MODEL_DIR"] + "/Lora"

def run():
    os.makedirs(DST, exist_ok=True)
    n = 0
    for p in glob.glob(ST.LORA_OUT + "/*.safetensors"):
        d = os.path.join(DST, os.path.basename(p))
        if not os.path.exists(d) or os.path.getsize(d) != os.path.getsize(p):
            shutil.copy2(p, d)
            n += 1
    F.ensure(); F.select_model()
    try:
        requests.post(F.API + "/sdapi/v1/refresh-loras", timeout=120)
    except Exception as e:
        print("refresh 실패(무시 가능):", e)
    print(f"LoRA 배치 {n}개 갱신 / 총 {len(glob.glob(DST + '/*.safetensors'))}개")
    ST.mark("cellB1_lora_deploy", "done")
    return True
