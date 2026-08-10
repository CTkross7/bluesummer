# -*- coding: utf-8 -*-
"""
BLUE SUMMER - Generation Engine v10

v9 -> v10 변경점
----------------
1. refine(extras) 기본 비활성화. C.EXTRAS_ENABLE 로 제어하며, 호출되더라도
   · 입력 픽셀을 EXTRAS_MAX_INPUT_PX 로 선축소
   · 기본은 업스케일러 1종(AnimeSharp)만 사용 (EXTRAS_DUAL=True 면 2종 블렌드)
   · EXTRAS_TIMEOUT 하드 타임아웃, 초과 시 원본을 그대로 사용
   · 느리거나 실패가 반복되면 세션 내 자동 비활성화
2. finalize() 에서 LANCZOS 축소 직후 UnsharpMask 를 적용해 라인 선예도를 확보.
   (512x768 최종본에서는 2차 ESRGAN 과 육안 차이가 사실상 없다)
3. extras 구간은 진행률 API 가 직전 값(100%)을 그대로 반환하므로
   ProgressWatcher 대신 Heartbeat 워커를 사용한다. "100%에서 멈춤" 오탐 제거.
4. ProgressWatcher 출력 조건 로직 정리.

기존 API 는 그대로 유지된다.
    txt2img / refine / make / finalize / health / status / self_test
"""

import io
import os
import re
import sys
import json
import time
import base64
import threading
import subprocess

import requests
from PIL import Image, ImageFilter

sys.path.insert(0, "/kaggle/working/BLUESUMMER")

import bs_config as C
import bs_log as L
import bs_state as ST
import bs_forge as FG


# =====================================================================
# 상수 / 세션
# =====================================================================

API = FG.API

S = requests.Session()      # 생성 요청 전용 (블로킹)
WS = requests.Session()     # 진행률 폴링 전용 (별도 스레드)

_CKPT_TITLE = None
_UPS = {}

LAST_GENERATION_MODE = None
LAST_GENERATION_ERROR = None
LAST_PROGRESS = {}

EXTRAS_DISABLED = False
EXTRAS_STATS = {"calls": 0, "ok": 0, "fail": 0, "slow": 0, "sec": 0.0}

GEN_STATS = {
    "ok": 0,
    "fail": 0,
    "skip": 0,
    "by_mode": {},
    "last_label": "",
    "last_note": "",
    "started_at": None,
}

_TAIL_LOCK = threading.Lock()


def _cfg(name, default):
    """bs_config 에 항목이 없어도 안전하게 기본값으로 동작."""
    return getattr(C, name, default)


# =====================================================================
# 포맷 도우미
# =====================================================================

def _fmt_sec(sec):
    try:
        sec = float(sec)
    except Exception:
        return "?"
    if sec < 0:
        return "?"
    if sec < 60:
        return "%.0f초" % sec
    return "%d분%02d초" % (int(sec // 60), int(sec % 60))


_VRAM_CACHE = {"t": 0.0, "s": ""}


def _vram():
    if not _cfg("VRAM_LOG", True):
        return ""
    now = time.time()
    if now - _VRAM_CACHE["t"] < 15 and _VRAM_CACHE["s"]:
        return _VRAM_CACHE["s"]
    text = ""
    try:
        p = subprocess.run(
            "nvidia-smi --query-gpu=memory.used,memory.total "
            "--format=csv,noheader,nounits",
            shell=True, capture_output=True, text=True, timeout=8)
        rows = [x.strip() for x in (p.stdout or "").splitlines() if x.strip()]
        parts = []
        for i, row in enumerate(rows):
            cols = [c.strip() for c in row.split(",")]
            used = float(cols[0]) / 1024.0
            total = float(cols[1]) / 1024.0
            parts.append("GPU%d %.1f/%.1fG" % (i, used, total))
        text = " · ".join(parts)
    except Exception:
        text = ""
    _VRAM_CACHE["t"] = now
    _VRAM_CACHE["s"] = text
    return text


# =====================================================================
# Forge 로그 실시간 tail
# =====================================================================

_ERR_KEYS = ("error", "traceback", "exception", "out of memory",
             "cuda error", "killed", "aborted", "runtimeerror")


class ForgeLogTail(threading.Thread):
    """forge.log 에 새로 붙는 내용을 실시간으로 노트북에 출력한다."""

    def __init__(self, path=None, interval=None, max_lines=None):
        threading.Thread.__init__(self, daemon=True)
        self.path = path or getattr(FG, "LOGFILE", "/kaggle/temp/forge.log")
        self.interval = float(interval or _cfg("FORGE_LOG_TAIL_SEC", 4.0))
        self.max_lines = int(max_lines or _cfg("FORGE_LOG_TAIL_MAX", 3))
        self._stop = threading.Event()
        self.pos = 0
        self.last_shown = ""
        try:
            if os.path.isfile(self.path):
                self.pos = os.path.getsize(self.path)
        except Exception:
            self.pos = 0

    def stop(self):
        self._stop.set()

    def _read_new(self):
        try:
            if not os.path.isfile(self.path):
                return ""
            size = os.path.getsize(self.path)
            if size < self.pos:
                self.pos = 0
            if size == self.pos:
                return ""
            with open(self.path, "rb") as f:
                f.seek(self.pos)
                raw = f.read(size - self.pos)
                self.pos = size
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return ""

    def run(self):
        while not self._stop.wait(self.interval):
            chunk = self._read_new()
            if not chunk:
                continue
            parts = [p.strip() for p in re.split(r"[\r\n]+", chunk) if p.strip()]
            if not parts:
                continue
            for p in parts:
                low = p.lower()
                if any(k in low for k in _ERR_KEYS):
                    L.warn("[forge] " + p[:220])
            for p in parts[-self.max_lines:]:
                if p == self.last_shown:
                    continue
                low = p.lower()
                if any(k in low for k in _ERR_KEYS):
                    continue
                if "GET /sdapi/v1/progress" in p:
                    continue
                self.last_shown = p
                L.log("[forge] " + p[:220])


def _start_tail():
    if not _cfg("FORGE_LOG_TAIL", True):
        return None
    if not _TAIL_LOCK.acquire(blocking=False):
        return None
    try:
        t = ForgeLogTail()
        t.start()
        return t
    except Exception:
        _TAIL_LOCK.release()
        return None


def _stop_tail(t):
    if t is None:
        return
    try:
        t.stop()
    finally:
        try:
            _TAIL_LOCK.release()
        except Exception:
            pass


# =====================================================================
# 진행률 감시 스레드 (txt2img 전용)
# =====================================================================

class ProgressWatcher(threading.Thread):
    """생성 진행률 / 스텝 / ETA / VRAM 을 실시간 출력한다."""

    def __init__(self, label):
        threading.Thread.__init__(self, daemon=True)
        self.label = label
        self._stop = threading.Event()
        self.t0 = time.time()
        self.max_progress = 0.0
        self.last_change = time.time()
        self.last_print = 0.0
        self.polls = 0
        self.ok_polls = 0
        self.stall_warned = False
        self.interrupted = False

    def stop(self):
        self._stop.set()

    def elapsed(self):
        return time.time() - self.t0

    def _poll(self):
        try:
            r = WS.get(API + "/sdapi/v1/progress?skip_current_image=true",
                       timeout=8)
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            return None

    def _line(self, data):
        prog = float(data.get("progress") or 0.0)
        eta = data.get("eta_relative")
        st = data.get("state") or {}
        step = st.get("sampling_step") or 0
        steps = st.get("sampling_steps") or 0
        job = str(st.get("job") or "").strip()
        job_no = st.get("job_no")
        job_cnt = st.get("job_count")

        bits = ["%s %3d%%" % (self.label, int(prog * 100))]
        if steps:
            bits.append("step %d/%d" % (step, steps))
        if job or job_cnt:
            j = job or "job"
            if job_cnt and int(job_cnt) > 0:
                j += " %s/%s" % (int(job_no or 0) + 1, job_cnt)
            bits.append(j)
        if eta:
            try:
                if float(eta) > 0.5:
                    bits.append("남은 " + _fmt_sec(float(eta)))
            except Exception:
                pass
        bits.append("경과 " + _fmt_sec(self.elapsed()))
        v = _vram()
        if v:
            bits.append(v)
        return "[watch] " + " | ".join(bits)

    def run(self):
        interval = float(_cfg("PROGRESS_POLL_SEC", 5.0))
        heartbeat = float(_cfg("HEARTBEAT_SEC", 30.0))
        stall = float(_cfg("STALL_WARN_SEC", 180.0))

        while not self._stop.wait(interval):
            self.polls += 1
            data = self._poll()
            now = time.time()

            if not isinstance(data, dict):
                if now - self.last_print >= heartbeat:
                    self.last_print = now
                    L.log("[watch] %s 대기중 (진행률 API 무응답) | 경과 %s %s"
                          % (self.label, _fmt_sec(self.elapsed()), _vram()))
                continue

            self.ok_polls += 1
            LAST_PROGRESS.clear()
            LAST_PROGRESS.update(data)

            st = data.get("state") or {}
            if st.get("interrupted") or st.get("skipped"):
                self.interrupted = True
                L.warn("[watch] %s : Forge 가 작업을 중단/스킵했습니다" % self.label)

            prog = float(data.get("progress") or 0.0)
            if prog > self.max_progress + 0.001:
                self.max_progress = prog
                self.last_change = now
                self.stall_warned = False

            due = (now - self.last_print) >= max(interval, 8.0) and prog > 0.0
            if (now - self.last_print) >= heartbeat:
                due = True
            if due:
                self.last_print = now
                L.log(self._line(data))

            if (not self.stall_warned) and (now - self.last_change) > stall:
                self.stall_warned = True
                L.warn("[watch] %s : %s 동안 진행률이 %d%% 에서 멈춰 있습니다"
                       % (self.label, _fmt_sec(now - self.last_change),
                          int(self.max_progress * 100)))
                _dump_forge_log(15)

    def summary(self):
        if self.polls and self.ok_polls == 0:
            L.warn("[watch] 진행률 API 가 한 번도 응답하지 않았습니다")
        return {"polls": self.polls, "ok": self.ok_polls,
                "max_progress": self.max_progress,
                "elapsed": self.elapsed()}


def _watch(label):
    try:
        w = ProgressWatcher(label)
        w.start()
        return w
    except Exception:
        return None


def _unwatch(w):
    if w is None:
        return
    try:
        w.stop()
        w.summary()
    except Exception:
        pass


# =====================================================================
# 하트비트 (extras 등 진행률이 보고되지 않는 구간용)
# =====================================================================

class Heartbeat(threading.Thread):
    """진행률을 알 수 없는 작업이 '살아있음'만 알려주는 워커."""

    def __init__(self, label, interval=None, soft_warn=None):
        threading.Thread.__init__(self, daemon=True)
        self.label = label
        self.interval = float(interval or 15.0)
        self.soft = float(soft_warn or 0.0)
        self._stop = threading.Event()
        self.t0 = time.time()
        self.warned = False

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.wait(self.interval):
            el = time.time() - self.t0
            L.log("[watch] %s 처리중 (진행률 미보고 구간) | 경과 %s | %s"
                  % (self.label, _fmt_sec(el), _vram()))
            if self.soft and el > self.soft and not self.warned:
                self.warned = True
                L.warn("[watch] %s : %s 초과 - 비정상적으로 느립니다"
                       % (self.label, _fmt_sec(self.soft)))
                _dump_forge_log(10)


def _beat(label, soft_warn=None):
    try:
        h = Heartbeat(label, soft_warn=soft_warn)
        h.start()
        return h
    except Exception:
        return None


def _unbeat(h):
    if h is None:
        return
    try:
        h.stop()
    except Exception:
        pass


# =====================================================================
# Checkpoint / Upscaler
# =====================================================================

def resolved_ckpt():
    global _CKPT_TITLE
    if _CKPT_TITLE is None:
        try:
            _CKPT_TITLE = FG.resolve_checkpoint()
        except Exception:
            _CKPT_TITLE = None
        if not _CKPT_TITLE:
            _CKPT_TITLE = C.CKPT_NAME
    return _CKPT_TITLE


def _norm(s):
    return str(s).lower().replace("-", "").replace("_", "").replace(" ", "")


def resolved_upscaler(name):
    if not name:
        return name
    if name in _UPS:
        return _UPS[name]
    val = name
    try:
        for u in FG.upscalers():
            if _norm(u) == _norm(name):
                val = u
                break
    except Exception:
        pass
    _UPS[name] = val
    return val


# =====================================================================
# 이미지 변환
# =====================================================================

def b64_to_img(b):
    if not b:
        raise ValueError("empty image response")
    if "," in b:
        b = b.split(",", 1)[-1]
    return Image.open(io.BytesIO(base64.b64decode(b))).convert("RGB")


def img_to_b64(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


# =====================================================================
# ADetailer
# =====================================================================

def adetailer_args(hand=True):
    units = [
        True, False,
        {"ad_model": C.AD_FACE,
         "ad_prompt": C.AD_PROMPT,
         "ad_negative_prompt": C.AD_NEG,
         "ad_confidence": C.AD_CONF,
         "ad_denoising_strength": C.AD_DENOISE,
         "ad_mask_blur": C.AD_BLUR,
         "ad_inpaint_only_masked": True,
         "ad_inpaint_only_masked_padding": 32,
         "ad_use_steps": True, "ad_steps": 20,
         "ad_use_cfg_scale": True, "ad_cfg_scale": C.CFG},
    ]
    if hand:
        units.append(
            {"ad_model": C.AD_HAND,
             "ad_prompt": C.AD_HAND_PROMPT,
             "ad_negative_prompt": C.AD_NEG,
             "ad_confidence": 0.35,
             "ad_denoising_strength": C.AD_HAND_DENOISE,
             "ad_mask_blur": C.AD_BLUR,
             "ad_inpaint_only_masked": True,
             "ad_inpaint_only_masked_padding": 24,
             "ad_use_steps": True, "ad_steps": 16})
    return {"ADetailer": {"args": units}}


# =====================================================================
# 에러 파싱 / 로그
# =====================================================================

def _short_error(text):
    if text is None:
        return "unknown"
    text = str(text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            if "errors" in data:
                return str(data["errors"])[:500]
            if "error" in data:
                err = data["error"]
                if isinstance(err, dict):
                    return "%s | %s" % (err.get("type", "unknown"),
                                        err.get("message", ""))
                return str(err)[:500]
    except Exception:
        pass
    return text.replace("\n", " ")[:500]


def _is_none_type_error(text):
    s = str(text).lower()
    return "nonetype" in s or "none type" in s


def _forge_log_tail(n=30):
    for path in ("/kaggle/temp/forge.log",
                 getattr(FG, "LOGFILE", "/kaggle/temp/forge.log")):
        try:
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = [x for x in f.read().splitlines()
                         if "GET /sdapi/v1/progress" not in x]
            if lines:
                return "\n".join(lines[-n:])
        except Exception:
            pass
    return ""


def _dump_forge_log(n=12):
    tail = _forge_log_tail(n)
    if not tail:
        L.warn("[engine] forge.log 를 읽지 못했습니다")
        return
    L.warn("[engine] --- forge.log 끝 %d줄 ---" % n)
    for line in tail.splitlines():
        line = line.strip()
        if line:
            L.warn("[engine]   " + line[:220])
    L.warn("[engine] --- forge.log 끝 ---")


def _log_forge_error(label, response_text):
    short = _short_error(response_text)
    L.warn("[engine] %s 실패 : %s" % (label, short))
    if _is_none_type_error(response_text):
        L.warn("[engine] Forge NoneType 오류 - bs_forge._patch_processing_py 확인")
    _dump_forge_log(12)
    return short


# =====================================================================
# Forge 상태
# =====================================================================

def _ensure_alive():
    try:
        if FG.alive(5):
            return True
    except Exception:
        pass
    L.warn("[engine] Forge API 응답 없음 -> 기동 시도")
    try:
        return bool(FG.launch())
    except Exception as e:
        L.err("[engine] Forge 기동 실패: %s" % e)
        return False


# =====================================================================
# HTTP POST
# =====================================================================

def _post_once(endpoint, payload, timeout=None):
    timeout = timeout or _cfg("GEN_TIMEOUT", 1800)
    try:
        r = S.post(API + endpoint, json=payload, timeout=timeout)
    except requests.exceptions.ReadTimeout:
        raise RuntimeError("TIMEOUT %ss - Forge 가 응답하지 않습니다" % timeout)
    except Exception as e:
        raise RuntimeError("connection error: %s" % e)
    if r.status_code != 200:
        raise RuntimeError("HTTP %s | %s" % (r.status_code, _short_error(r.text)))
    try:
        return r.json()
    except Exception as e:
        raise RuntimeError("invalid JSON response: %s" % e)


# =====================================================================
# Payload
# =====================================================================

def _override_settings():
    return {"sd_model_checkpoint": resolved_ckpt(),
            "sd_vae": C.VAE_NAME,
            "CLIP_stop_at_last_layers": C.CLIP_SKIP}


def _base_payload(prompt, negative, seed=-1, steps=None, cfg=None,
                  width=None, height=None):
    return {
        "prompt": prompt,
        "negative_prompt": negative,
        "sampler_name": C.SAMPLER,
        "steps": steps if steps is not None else C.STEPS,
        "cfg_scale": cfg if cfg is not None else C.CFG,
        "width": width if width is not None else C.WIDTH,
        "height": height if height is not None else C.HEIGHT,
        "seed": seed,
        "batch_size": 1,
        "n_iter": 1,
        "save_images": False,
        "send_images": True,
    }


def _hr_block(hr_scale, hr_steps, hr_denoise, hr_cfg=None):
    d = {"enable_hr": True,
         "hr_scale": hr_scale if hr_scale is not None else C.HR_SCALE,
         "hr_upscaler": resolved_upscaler(C.UPSCALER_HIRES),
         "hr_second_pass_steps": hr_steps if hr_steps is not None else C.HR_STEPS,
         "denoising_strength": hr_denoise if hr_denoise is not None else C.HR_DENOISE,
         "hr_sampler_name": C.SAMPLER}
    if hr_cfg is not None:
        d["hr_cfg"] = hr_cfg
    return d


def _full_payload(prompt, negative, seed, steps, cfg, width, height, hr,
                  hr_steps, hr_denoise, hr_cfg, hr_scale, adetailer, hands):
    p = _base_payload(prompt, negative, seed, steps, cfg, width, height)
    p["scheduler"] = C.SCHEDULER
    p["override_settings"] = _override_settings()
    p["override_settings_restore_afterwards"] = False
    if hr:
        p.update(_hr_block(hr_scale, hr_steps, hr_denoise,
                           hr_cfg if hr_cfg is not None else C.HR_CFG))
    if adetailer and _cfg("AD_ENABLE", False):
        p["alwayson_scripts"] = adetailer_args(hand=hands)
    return p


def _no_ad_payload(prompt, negative, seed, steps, cfg, width, height, hr,
                   hr_steps, hr_denoise, hr_cfg, hr_scale):
    p = _base_payload(prompt, negative, seed, steps, cfg, width, height)
    p["scheduler"] = C.SCHEDULER
    p["override_settings"] = _override_settings()
    p["override_settings_restore_afterwards"] = False
    if hr:
        p.update(_hr_block(hr_scale, hr_steps, hr_denoise,
                           hr_cfg if hr_cfg is not None else C.HR_CFG))
    return p


def _safe_hr_payload(prompt, negative, seed, steps, cfg, width, height,
                     hr_scale, hr_steps, hr_denoise):
    p = _base_payload(prompt, negative, seed, steps, cfg, width, height)
    p["override_settings"] = _override_settings()
    p["override_settings_restore_afterwards"] = False
    p.update(_hr_block(
        hr_scale if hr_scale is not None else min(float(_cfg("HR_SCALE", 1.5)), 1.5),
        hr_steps if hr_steps is not None else min(int(_cfg("HR_STEPS", 12)), 12),
        hr_denoise if hr_denoise is not None else min(float(_cfg("HR_DENOISE", 0.35)), 0.35)))
    return p


def _minimal_payload(prompt, negative, seed, steps, cfg, width, height):
    return _base_payload(prompt, negative, seed, steps, cfg, width, height)


def _payload_brief(p):
    keys = []
    for k in ("steps", "cfg_scale", "width", "height", "seed", "scheduler",
              "enable_hr", "hr_scale", "hr_second_pass_steps",
              "denoising_strength", "hr_upscaler"):
        if k in p:
            keys.append("%s=%s" % (k, p[k]))
    if "alwayson_scripts" in p:
        n = len([x for x in p["alwayson_scripts"]["ADetailer"]["args"]
                 if isinstance(x, dict)])
        keys.append("adetailer=%dunit" % n)
    if "override_settings" in p:
        keys.append("override=on")
    try:
        keys.append("payload=%.1fKB" % (len(json.dumps(p)) / 1024.0))
    except Exception:
        pass
    return " ".join(keys)


# =====================================================================
# 응답 파싱
# =====================================================================

def _extract_image(response):
    if not isinstance(response, dict):
        raise RuntimeError("Forge response is not a dict")
    images = response.get("images")
    if not images:
        raise RuntimeError("Forge response contains no images")
    return b64_to_img(images[0])


def _extract_seed(response, fallback):
    try:
        info = response.get("info", "{}")
        if isinstance(info, str):
            info = json.loads(info)
        if isinstance(info, dict) and info.get("seed") is not None:
            return info["seed"]
    except Exception:
        pass
    return fallback


# =====================================================================
# 단일 시도
# =====================================================================

def _attempt(mode, payload, number, total, timeout=None):
    L.log("[engine] 시도 %d/%d : %s | %s"
          % (number, total, mode, _payload_brief(payload)))
    v = _vram()
    if v:
        L.log("[engine] 요청 전 VRAM : %s" % v)

    watcher = _watch(mode)
    t0 = time.time()
    try:
        response = _post_once("/sdapi/v1/txt2img", payload, timeout=timeout)
        image = _extract_image(response)
        used_seed = _extract_seed(response, payload.get("seed", -1))
        dt = time.time() - t0
        L.ok("[engine] %s 성공 | %s | %dx%d | seed=%s"
             % (mode, _fmt_sec(dt), image.size[0], image.size[1], used_seed))
        return image, used_seed, None
    except Exception as e:
        dt = time.time() - t0
        msg = str(e)
        L.warn("[engine] %s 실패 (%s)" % (mode, _fmt_sec(dt)))
        if "HTTP 500" in msg or "HTTP 4" in msg or "TIMEOUT" in msg:
            _log_forge_error(mode, msg)
        else:
            L.warn("[engine] %s : %s" % (mode, msg[:500]))
        return None, None, msg
    finally:
        _unwatch(watcher)


# =====================================================================
# 4단계 txt2img
# =====================================================================

def txt2img(prompt, negative, seed=-1, steps=None, cfg=None, width=None,
            height=None, hr=True, hr_steps=None, hr_denoise=None, hr_cfg=None,
            adetailer=True, hr_scale=None, hands=True):
    """FULL -> NO-AD -> SAFE-HR -> MINIMAL 순서로 폴백하며 생성."""
    global LAST_GENERATION_MODE, LAST_GENERATION_ERROR
    LAST_GENERATION_MODE = None
    LAST_GENERATION_ERROR = None

    if not _ensure_alive():
        raise RuntimeError("Forge API is not alive")

    L.log("[engine] txt2img 시작 | %sx%s steps=%s cfg=%s hr=%s ad=%s"
          % (width or C.WIDTH, height or C.HEIGHT, steps or C.STEPS,
             cfg or C.CFG, hr, adetailer))
    if _cfg("VERBOSE_GEN", True):
        L.log("[engine] prompt : " + str(prompt)[:180] + " ...")

    tail = _start_tail()
    t_all = time.time()
    try:
        stages = [
            ("FULL", lambda: _full_payload(prompt, negative, seed, steps, cfg,
                                           width, height, hr, hr_steps,
                                           hr_denoise, hr_cfg, hr_scale,
                                           adetailer, hands)),
            ("NO-AD", lambda: _no_ad_payload(prompt, negative, seed, steps, cfg,
                                             width, height, hr, hr_steps,
                                             hr_denoise, hr_cfg, hr_scale)),
            ("SAFE-HR", lambda: _safe_hr_payload(prompt, negative, seed, steps,
                                                 cfg, width, height, hr_scale,
                                                 hr_steps, hr_denoise)),
            ("MINIMAL", lambda: _minimal_payload(prompt, negative, seed, steps,
                                                 cfg, width, height)),
        ]
        error = None
        for i, (mode, builder) in enumerate(stages, 1):
            image, used_seed, error = _attempt(mode, builder(), i, len(stages))
            if image is not None:
                LAST_GENERATION_MODE = mode
                GEN_STATS["by_mode"][mode] = GEN_STATS["by_mode"].get(mode, 0) + 1
                L.log("[engine] txt2img 완료 (%s, 총 %s)"
                      % (mode, _fmt_sec(time.time() - t_all)))
                return image, used_seed
            LAST_GENERATION_ERROR = error
            if i < len(stages):
                L.warn("[engine] 폴백 -> %s" % stages[i][0])

        L.err("[engine] 4단계 폴백 모두 실패 (총 %s)" % _fmt_sec(time.time() - t_all))
        raise RuntimeError("/sdapi/v1/txt2img: " + str(error))
    finally:
        _stop_tail(tail)


# =====================================================================
# extras (2차 업스케일 정제) - 기본 비활성화
# =====================================================================

def extras_available(force=False):
    """extras 를 지금 사용할 수 있는가."""
    if force:
        return not EXTRAS_DISABLED
    return bool(_cfg("EXTRAS_ENABLE", False)) and not EXTRAS_DISABLED


def _extras_penalty(reason):
    """느림/실패 누적 시 세션 내 자동 비활성화."""
    global EXTRAS_DISABLED
    limit = int(_cfg("EXTRAS_SLOW_LIMIT", 2))
    bad = EXTRAS_STATS["fail"] + EXTRAS_STATS["slow"]
    if bad >= limit and not EXTRAS_DISABLED:
        EXTRAS_DISABLED = True
        L.warn("[engine] extras 자동 비활성화 (%s / 누적 %d회). "
               "이후에는 LANCZOS + 언샵 마스크만 사용합니다." % (reason, bad))


def _shrink_for_extras(im):
    """ESRGAN 입력 픽셀 수를 상한으로 제한한다."""
    max_px = float(_cfg("EXTRAS_MAX_INPUT_PX", 1200000))
    w, h = im.size
    px = float(w * h)
    if px <= max_px:
        return im
    r = (max_px / px) ** 0.5
    nw = max(64, int(w * r) // 8 * 8)
    nh = max(64, int(h * r) // 8 * 8)
    L.log("[engine] extras 입력 축소 %dx%d -> %dx%d (상한 %.1fMpx)"
          % (w, h, nw, nh, max_px / 1e6))
    return im.resize((nw, nh), Image.LANCZOS)


def _post_extras(payload, timeout=None):
    timeout = timeout or _cfg("EXTRAS_TIMEOUT", 300)
    soft = float(_cfg("EXTRAS_SLOW_SEC", 150))
    beat = _beat("EXTRAS", soft_warn=soft)
    t0 = time.time()
    try:
        r = S.post(API + "/sdapi/v1/extra-single-image",
                   json=payload, timeout=timeout)
        dt = time.time() - t0
        if r.status_code != 200:
            EXTRAS_STATS["fail"] += 1
            _extras_penalty("HTTP %s" % r.status_code)
            raise RuntimeError("extras HTTP %s : %s"
                               % (r.status_code, _short_error(r.text)))
        EXTRAS_STATS["ok"] += 1
        EXTRAS_STATS["sec"] += dt
        if dt > soft:
            EXTRAS_STATS["slow"] += 1
            _extras_penalty("%s 소요" % _fmt_sec(dt))
        L.log("[engine] extras 성공 (%s)" % _fmt_sec(dt))
        return r.json()
    except requests.exceptions.ReadTimeout:
        EXTRAS_STATS["fail"] += 1
        _extras_penalty("타임아웃 %ss" % timeout)
        raise RuntimeError("extras TIMEOUT %ss" % timeout)
    finally:
        EXTRAS_STATS["calls"] += 1
        _unbeat(beat)


def refine(im, scale=None, blend=None, force=False, timeout=None):
    """2차 업스케일 정제.

    기본(C.EXTRAS_ENABLE=False)에서는 아무 것도 하지 않고 원본을 돌려준다.
    라인 선예도는 finalize() 의 UnsharpMask 가 담당한다.
    force=True 로 호출하면 설정과 무관하게 시도한다(LoRA 데이터셋 용).
    실패·타임아웃 시에도 예외를 던지지 않고 원본을 반환한다.
    """
    if not extras_available(force):
        if _cfg("VERBOSE_GEN", True):
            L.log("[engine] extras 생략 (EXTRAS_ENABLE=%s / disabled=%s)"
                  % (_cfg("EXTRAS_ENABLE", False), EXTRAS_DISABLED))
        return im

    src = _shrink_for_extras(im)
    sc = float(scale if scale is not None else _cfg("EXTRAS_SCALE", 1.35))
    dual = bool(_cfg("EXTRAS_DUAL", False))
    bl = float(_cfg("EXTRAS_BLEND", 0.55) if blend is None else blend)

    if dual:
        up1 = resolved_upscaler(C.UPSCALER_HIRES)
        up2 = resolved_upscaler(C.UPSCALER_LINE)
        vis = bl
    else:
        up1 = resolved_upscaler(C.UPSCALER_LINE)   # 라인아트 중심 1종만
        up2 = "None"
        vis = 0.0

    payload = {
        "resize_mode": 0,
        "upscaling_resize": sc,
        "upscaler_1": up1,
        "upscaler_2": up2,
        "extras_upscaler_2_visibility": vis,
        "upscale_first": False,
        "gfpgan_visibility": 0,
        "codeformer_visibility": 0,
        "image": img_to_b64(src),
    }
    L.log("[engine] refine 요청 | %dx%d -> x%.2f | %s%s"
          % (src.size[0], src.size[1], sc, up1,
             (" + %s(%.2f)" % (up2, vis)) if dual else " (단일)"))
    try:
        r = _post_extras(payload, timeout=timeout)
        return b64_to_img(r["image"])
    except Exception as e:
        L.warn("[engine] refine 실패 - 원본 사용 : %s" % e)
        return im


# =====================================================================
# 최종 저장 (LANCZOS 축소 + 언샵 마스크)
# =====================================================================

def sharpen(im):
    if not _cfg("LOCAL_SHARPEN", True):
        return im
    try:
        return im.filter(ImageFilter.UnsharpMask(
            radius=float(_cfg("SHARPEN_RADIUS", 1.0)),
            percent=int(_cfg("SHARPEN_PERCENT", 55)),
            threshold=int(_cfg("SHARPEN_THRESHOLD", 3))))
    except Exception as e:
        L.warn("[engine] 샤프닝 생략: %s" % e)
        return im


def finalize(im, path, w=None, h=None, do_sharpen=None):
    w = w if w is not None else C.OUT_W
    h = h if h is not None else C.OUT_H
    tw, th = im.size
    target = float(w) / float(h)
    current = float(tw) / float(th)

    if current > target:
        nw = int(th * target)
        left = (tw - nw) // 2
        im = im.crop((left, 0, left + nw, th))
    elif current < target:
        nh = int(tw / target)
        top = (th - nh) // 2
        im = im.crop((0, top, tw, top + nh))

    im = im.resize((w, h), Image.LANCZOS)

    if do_sharpen is None:
        do_sharpen = _cfg("LOCAL_SHARPEN", True)
    if do_sharpen:
        im = sharpen(im)

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    im.save(tmp, "WEBP", quality=C.WEBP_QUALITY, method=C.WEBP_METHOD)
    os.replace(tmp, path)
    return path


# =====================================================================
# 원샷 생성
# =====================================================================

def make(prompt, negative, path, seed=-1, bg=False, adetailer=True,
         do_refine=None, overwrite=False):
    """반환 : (path, used_seed, note)  note = skip / fail / "83초 / FULL" """
    label = os.path.basename(path)
    GEN_STATS["last_label"] = label
    GEN_STATS["started_at"] = time.time()

    if do_refine is None:
        do_refine = bool(_cfg("EXTRAS_ENABLE", False))

    if (not overwrite) and os.path.exists(path) and os.path.getsize(path) > 8000:
        GEN_STATS["skip"] += 1
        L.log("[engine] %s : 이미 존재 - 건너뜀" % label)
        return path, None, "skip"

    L.log("[engine] ===== %s 생성 시작 (%s) ====="
          % (label, "배경" if bg else "인물/UI"))
    t0 = time.time()
    used = None

    try:
        if bg:
            im, used = txt2img(prompt, negative, seed=seed, steps=C.BG_STEPS,
                               cfg=C.BG_CFG, hr=True, hr_steps=C.BG_HR_STEPS,
                               hr_denoise=C.BG_HR_DENOISE, adetailer=False)
        else:
            im, used = txt2img(prompt, negative, seed=seed, adetailer=adetailer)
    except Exception as e:
        GEN_STATS["fail"] += 1
        L.err("[engine] 생성 실패 %s : %s" % (label, e))
        if _cfg("DEBUG", True):
            try:
                L.exc()
            except Exception:
                pass
        _dump_forge_log(20)
        return path, None, "fail"

    t_gen = time.time() - t0

    t1 = time.time()
    if do_refine:
        im = refine(im)
    t_ref = time.time() - t1

    t2 = time.time()
    try:
        finalize(im, path)
    except Exception as e:
        GEN_STATS["fail"] += 1
        L.err("[engine] 저장 실패 %s : %s" % (label, e))
        return path, used, "fail"
    t_save = time.time() - t2

    dt = time.time() - t0
    try:
        ST.timing_add("bg" if bg else "char", dt)
    except Exception:
        pass

    mode = LAST_GENERATION_MODE or "UNKNOWN"
    note = "%.0fs / %s" % (dt, mode)
    GEN_STATS["ok"] += 1
    GEN_STATS["last_note"] = note

    L.ok("[engine] %s 완료 | 총 %s (생성 %s · 정제 %s · 저장 %s) | %s | %.0fKB"
         % (label, _fmt_sec(dt), _fmt_sec(t_gen), _fmt_sec(t_ref),
            _fmt_sec(t_save), mode, os.path.getsize(path) / 1024.0))
    return path, used, note


# =====================================================================
# 상태 조회 / 헬스체크
# =====================================================================

def progress_snapshot(show=True):
    try:
        r = WS.get(API + "/sdapi/v1/progress?skip_current_image=true", timeout=10)
        data = r.json()
    except Exception as e:
        if show:
            L.warn("[engine] 진행률 조회 실패: %s" % e)
        return {}
    if show:
        st = data.get("state") or {}
        L.log("[engine] 진행률 %d%% | step %s/%s | job %s | 남은 %s | %s"
              % (int(float(data.get("progress") or 0) * 100),
                 st.get("sampling_step"), st.get("sampling_steps"),
                 st.get("job") or "-",
                 _fmt_sec(data.get("eta_relative") or 0), _vram()))
    return data


def interrupt():
    try:
        S.post(API + "/sdapi/v1/interrupt", timeout=30)
        L.warn("[engine] interrupt 요청 전송")
        return True
    except Exception as e:
        L.warn("[engine] interrupt 실패: %s" % e)
        return False


def health(verbose=True):
    try:
        ms = [m.get("model_name", "") for m in FG.models()]
        us = FG.upscalers()
    except Exception as e:
        L.err("Forge 조회 실패: %s" % e)
        return False
    ok_ck = any("v190" in str(m).lower() for m in ms)
    ok_up = all(any(_norm(n) == _norm(u) for u in us)
                for n in (C.UPSCALER_HIRES, C.UPSCALER_LINE))
    if verbose:
        L.log("체크포인트 v19 : %s / 업스케일러 2종 : %s"
              % ("OK" if ok_ck else "NG", "OK" if ok_up else "NG"))
    return ok_ck and ok_up


def status():
    return {"api": API,
            "alive": bool(FG.alive(3)),
            "checkpoint": resolved_ckpt(),
            "last_generation_mode": LAST_GENERATION_MODE,
            "last_generation_error": LAST_GENERATION_ERROR,
            "extras_enabled": bool(_cfg("EXTRAS_ENABLE", False)),
            "extras_disabled_runtime": EXTRAS_DISABLED,
            "extras_stats": EXTRAS_STATS,
            "stats": GEN_STATS,
            "vram": _vram()}


def self_test():
    L.log("[engine] bs_engine v10 loaded")
    L.log("[engine] API = %s" % API)
    L.log("[engine] extras = %s (dual=%s, scale=%s, timeout=%ss) / 로컬샤프닝 = %s"
          % (_cfg("EXTRAS_ENABLE", False), _cfg("EXTRAS_DUAL", False),
             _cfg("EXTRAS_SCALE", 1.35), _cfg("EXTRAS_TIMEOUT", 300),
             _cfg("LOCAL_SHARPEN", True)))
    L.log("[engine] 폴링 %ss / 하트비트 %ss / 정체경고 %ss / forge tail %s"
          % (_cfg("PROGRESS_POLL_SEC", 5), _cfg("HEARTBEAT_SEC", 30),
             _cfg("STALL_WARN_SEC", 180), _cfg("FORGE_LOG_TAIL", True)))
    try:
        alive = FG.alive(3)
        L.log("[engine] Forge API = %s" % ("OK" if alive else "NG"))
        return alive
    except Exception as e:
        L.warn("[engine] self-test 실패: %s" % e)
        return False
