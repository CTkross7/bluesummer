
# -*- coding: utf-8 -*-
import os, sys, io, json, time, base64, hashlib, requests
from PIL import Image
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST, bs_common as P, bs_forge as F

API = F.API
_AD = None

def ad_available():
    global _AD
    if _AD is None:
        _AD = F.has_adetailer()
        print("[engine] ADetailer:", "사용" if _AD else "미사용(폴백)")
    return _AD

def seed_of(key):
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16) % (2**31)

def _payload(prompt, w, h, steps=28, cfg=5.0, seed=-1, hires=True):
    d = {"prompt": prompt, "negative_prompt": P.NEG,
         "width": w, "height": h, "steps": steps, "cfg_scale": cfg,
         "sampler_name": "Euler a", "scheduler": "Automatic",
         "seed": seed, "batch_size": 1, "n_iter": 1,
         "save_images": False, "send_images": True}
    if hires:
        d.update({"enable_hr": True, "hr_scale": 1.35,
                  "hr_upscaler": "Latent", "denoising_strength": 0.35,
                  "hr_second_pass_steps": 12})
    return d

def _ad_args(face_prompt=""):
    return {"ADetailer": {"args": [True, False, {
        "ad_model": "face_yolov8n.pt",
        "ad_prompt": face_prompt,
        "ad_negative_prompt": P.NEG,
        "ad_confidence": 0.3,
        "ad_denoising_strength": 0.35,
        "ad_inpaint_only_masked": True,
        "ad_inpaint_only_masked_padding": 32,
    }]}}

def txt2img(prompt, w, h, seed=-1, use_ad=False, face_prompt="", tries=3):
    body = _payload(prompt, w, h, seed=seed)
    if use_ad and ad_available():
        body["alwayson_scripts"] = _ad_args(face_prompt)
    last = None
    for i in range(tries):
        try:
            r = requests.post(f"{API}/sdapi/v1/txt2img", json=body, timeout=900)
            r.raise_for_status()
            b64 = r.json()["images"][0]
            return Image.open(io.BytesIO(base64.b64decode(b64.split(",")[-1]))).convert("RGB")
        except Exception as e:
            last = e
            print(f"   재시도 {i+1}/{tries}: {e}")
            if not F.alive():
                F.start(); F.select_model()
            body.pop("alwayson_scripts", None)   # 2회차부터는 AD 없이
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"txt2img 실패: {last}")

def save_webp(img, path, size=None, quality=82):
    if size:
        img = img.resize(size, Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    img.save(tmp, "WEBP", quality=quality, method=6)
    os.replace(tmp, path)
    return path

def exists_ok(path, minkb=4):
    return os.path.exists(path) and os.path.getsize(path) > minkb * 1024
