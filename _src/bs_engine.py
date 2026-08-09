# -*- coding: utf-8 -*-
"""생성 엔진. txt2img(Hires:4x-UltraSharp) -> extras(UltraSharp+AnimeSharp 블렌드)
   -> LANCZOS 다운샘플 -> WebP 저장. 실패는 예외 대신 상태값으로 돌려준다."""
import io, os, sys, base64, time, json, requests
from PIL import Image
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_config as C, bs_log as L, bs_state as ST, bs_forge as FG

API = FG.API
S = requests.Session()
_CKPT_TITLE = None
_UPS = {}


def resolved_ckpt():
    global _CKPT_TITLE
    if _CKPT_TITLE is None:
        _CKPT_TITLE = FG.resolve_checkpoint() or C.CKPT_NAME
    return _CKPT_TITLE


def resolved_upscaler(name):
    if name in _UPS:
        return _UPS[name]
    val = name
    try:
        for u in FG.upscalers():
            if u.lower().replace("-", "") == name.lower().replace("-", ""):
                val = u
                break
    except Exception:
        pass
    _UPS[name] = val
    return val


def b64_to_img(b):
    return Image.open(io.BytesIO(base64.b64decode(b.split(",", 1)[-1]))).convert("RGB")


def img_to_b64(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def adetailer_args(hand=True):
    units = [True, False, {
        "ad_model": C.AD_FACE,
        "ad_prompt": C.AD_PROMPT,
        "ad_negative_prompt": C.AD_NEG,
        "ad_confidence": C.AD_CONF,
        "ad_denoising_strength": C.AD_DENOISE,
        "ad_mask_blur": C.AD_BLUR,
        "ad_inpaint_only_masked": True,
        "ad_inpaint_only_masked_padding": 32,
        "ad_use_steps": True, "ad_steps": 20,
        "ad_use_cfg_scale": True, "ad_cfg_scale": C.CFG,
    }]
    if hand:
        units.append({
            "ad_model": C.AD_HAND,
            "ad_prompt": C.AD_HAND_PROMPT,
            "ad_negative_prompt": C.AD_NEG,
            "ad_confidence": 0.35,
            "ad_denoising_strength": C.AD_HAND_DENOISE,
            "ad_mask_blur": C.AD_BLUR,
            "ad_inpaint_only_masked": True,
            "ad_inpaint_only_masked_padding": 24,
            "ad_use_steps": True, "ad_steps": 16,
        })
    return {"ADetailer": {"args": units}}


OPTIONAL_KEYS = ["hr_cfg", "hr_additional_modules", "scheduler", "hr_scheduler",
                 "hr_sampler_name", "distilled_cfg_scale", "hr_checkpoint_name"]


def _post(endpoint, payload, timeout=2400, retries=3):
    p = dict(payload)
    last = ""
    for attempt in range(retries):
        try:
            r = S.post(API + endpoint, json=p, timeout=timeout)
        except Exception as e:
            last = "conn %s" % e
            L.warn("   [engine] 연결 실패(%s) - Forge 상태 확인" % e)
            if not FG.alive(5):
                FG.launch()
            time.sleep(5)
            continue
        if r.status_code == 200:
            return r.json()
        last = r.text[:300]
        if r.status_code in (400, 422):
            removed = [k for k in OPTIONAL_KEYS if k in p]
            if removed:
                for k in removed:
                    p.pop(k, None)
                L.warn("   [engine] 미지원 키 제거 후 재시도: %s" % removed)
                continue
        L.warn("   [engine] HTTP %s : %s" % (r.status_code, last))
        if "alwayson_scripts" in p and attempt == retries - 2:
            L.warn("   [engine] ADetailer 제외하고 마지막 재시도")
            p.pop("alwayson_scripts", None)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("%s 실패 : %s" % (endpoint, last))


def txt2img(prompt, negative, seed=-1, steps=None, cfg=None, width=None, height=None,
            hr=True, hr_steps=None, hr_denoise=None, hr_cfg=None, adetailer=True,
            hr_scale=None, hands=True):
    payload = {
        "prompt": prompt,
        "negative_prompt": negative,
        "sampler_name": C.SAMPLER,
        "scheduler": C.SCHEDULER,
        "steps": steps or C.STEPS,
        "cfg_scale": cfg or C.CFG,
        "width": width or C.WIDTH,
        "height": height or C.HEIGHT,
        "seed": seed,
        "batch_size": 1, "n_iter": 1,
        "save_images": False, "send_images": True,
        "override_settings": {
            "sd_model_checkpoint": resolved_ckpt(),
            "sd_vae": C.VAE_NAME,
            "CLIP_stop_at_last_layers": C.CLIP_SKIP,
        },
        "override_settings_restore_afterwards": False,
    }
    if hr:
        payload.update({
            "enable_hr": True,
            "hr_scale": hr_scale or C.HR_SCALE,
            "hr_upscaler": resolved_upscaler(C.UPSCALER_HIRES),
            "hr_second_pass_steps": hr_steps or C.HR_STEPS,
            "denoising_strength": hr_denoise or C.HR_DENOISE,
            "hr_cfg": hr_cfg or C.HR_CFG,
            "hr_sampler_name": C.SAMPLER,
        })
    if adetailer and C.AD_ENABLE:
        payload["alwayson_scripts"] = adetailer_args(hand=hands)
    r = _post("/sdapi/v1/txt2img", payload)
    used = seed
    try:
        info = json.loads(r.get("info", "{}"))
        used = info.get("seed", seed)
    except Exception:
        pass
    return b64_to_img(r["images"][0]), used


def refine(im, scale=None, blend=None):
    """4x-UltraSharp + 4x-AnimeSharp 동시 적용으로 라인아트를 살린다."""
    payload = {
        "resize_mode": 0,
        "upscaling_resize": scale or C.EXTRAS_SCALE,
        "upscaler_1": resolved_upscaler(C.UPSCALER_HIRES),
        "upscaler_2": resolved_upscaler(C.UPSCALER_LINE),
        "extras_upscaler_2_visibility": C.EXTRAS_BLEND if blend is None else blend,
        "upscale_first": False,
        "gfpgan_visibility": 0, "codeformer_visibility": 0,
        "image": img_to_b64(im),
    }
    r = _post("/sdapi/v1/extra-single-image", payload, timeout=1200, retries=2)
    return b64_to_img(r["image"])


def finalize(im, path, w=None, h=None):
    w, h = w or C.OUT_W, h or C.OUT_H
    tw, th = im.size
    target = float(w) / float(h)
    if float(tw) / float(th) > target:
        nw = int(th * target)
        im = im.crop(((tw - nw) // 2, 0, (tw - nw) // 2 + nw, th))
    else:
        nh = int(tw / target)
        im = im.crop((0, 0, tw, nh))
    im = im.resize((w, h), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    im.save(tmp, "WEBP", quality=C.WEBP_QUALITY, method=C.WEBP_METHOD)
    os.replace(tmp, path)
    return path


def make(prompt, negative, path, seed=-1, bg=False, adetailer=True,
         do_refine=True, overwrite=False):
    """원스톱 생성. 반환 (path, used_seed, note). 실패 시 note='fail'."""
    if (not overwrite) and os.path.exists(path) and os.path.getsize(path) > 8000:
        return path, None, "skip"
    t0 = time.time()
    try:
        if bg:
            im, used = txt2img(prompt, negative, seed, steps=C.BG_STEPS, cfg=C.BG_CFG,
                               hr_steps=C.BG_HR_STEPS, hr_denoise=C.BG_HR_DENOISE,
                               adetailer=False)
        else:
            im, used = txt2img(prompt, negative, seed, adetailer=adetailer)
    except Exception as e:
        L.err("   [engine] 생성 실패 %s : %s" % (os.path.basename(path), e))
        return path, None, "fail"
    if do_refine:
        try:
            im = refine(im)
        except Exception as e:
            L.warn("   [engine] refine 실패(원본 사용): %s" % e)
    try:
        finalize(im, path)
    except Exception as e:
        L.err("   [engine] 저장 실패: %s" % e)
        return path, used, "fail"
    dt = time.time() - t0
    ST.timing_add("bg" if bg else "char", dt)
    return path, used, "%.0fs" % dt


def health(verbose=True):
    try:
        ms = [m.get("model_name", "") for m in FG.models()]
        us = FG.upscalers()
    except Exception as e:
        L.err("Forge 조회 실패: %s" % e)
        return False
    ok_ck = any("v190" in m.lower() for m in ms)
    ok_up = all(any(n.lower().replace("-", "") == u.lower().replace("-", "")
                    for u in us) for n in (C.UPSCALER_HIRES, C.UPSCALER_LINE))
    if verbose:
        L.log("체크포인트 v19 : %s / 업스케일러 2종 : %s"
              % ("OK" if ok_ck else "NG", "OK" if ok_up else "NG"))
    return ok_ck and ok_up
