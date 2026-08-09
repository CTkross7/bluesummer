
# -*- coding: utf-8 -*-
import os, sys, json, time, signal, subprocess, requests

ENV = json.load(open("/kaggle/temp/bs_env.json", encoding="utf-8"))
C   = ENV["cfg"]
PY   = C["VENV_FORGE"] + "/bin/python"
DIR  = C["FORGE_DIR"]
MD   = C["MODEL_DIR"]
PORT = C.get("PORT", 7860)
LOG  = "/kaggle/temp/forge.log"
PIDF = "/kaggle/temp/forge.pid"
API  = f"http://127.0.0.1:{PORT}"

ARGS = (f"--nowebui --api --api-server-stop --listen --port {PORT} "
        f"--skip-install --skip-torch-cuda-test --skip-python-version-check "
        f"--skip-version-check --no-download-sd-model --disable-nan-check "
        f"--no-half-vae --enable-insecure-extension-access "
        f"{C.get('ATTENTION','--attention-pytorch')} "
        f"--ckpt-dir {MD}/Stable-diffusion --vae-dir {MD}/VAE --lora-dir {MD}/Lora ")
        

def alive(timeout=8):
    try:
        return requests.get(f"{API}/sdapi/v1/sd-models", timeout=timeout).ok
    except Exception:
        return False
def _patch_processing():
    """hr_additional_modules가 None일 때 터지는 Forge 버그 패치. 매 기동시 자동 적용."""
    p = os.path.join(DIR, "modules", "processing.py")
    try:
        s = open(p, encoding="utf-8").read()
        old = "and 'Use same choices' not in self.hr_additional_modules:"
        new = "and self.hr_additional_modules and 'Use same choices' not in self.hr_additional_modules:"
        if old in s and "self.hr_additional_modules and 'Use same choices'" not in s:
            s = s.replace(old, new)
            open(p, "w", encoding="utf-8").write(s)
            print("[forge] processing.py 패치 적용")
    except Exception as e:
        print("[forge] 패치 실패(무시하고 진행):", e)

        
def start(wait=900):
    if alive():
        print("[forge] 이미 기동 중")
        _patch_processing()
        return True
    env = dict(os.environ)
    env.update({"PYTHONUNBUFFERED": "1", "PYTHONNOUSERSITE": "1",
                "PIP_NO_INPUT": "1", "SD_WEBUI_RESTART": "0",
                "COMMANDLINE_ARGS": "","MPLBACKEND": "Agg"})
    f = open(LOG, "ab")
    p = subprocess.Popen(f"{PY} launch.py {ARGS}", shell=True, cwd=DIR,
                         stdout=f, stderr=f, env=env, preexec_fn=os.setsid)
    open(PIDF, "w").write(str(p.pid))
    t0 = time.time()
    while time.time() - t0 < wait:
        if alive(5):
            _patch_processing()
            print(f"[forge] 기동 완료 ({int(time.time()-t0)}초)")
            return True
        if p.poll() is not None:
            print("[forge] 프로세스가 죽었습니다. 로그 마지막 40줄:")
            print("".join(open(LOG, errors="ignore").readlines()[-40:]))
            return False
        time.sleep(10)
    print("[forge] 타임아웃. 로그 마지막 40줄:")
    print("".join(open(LOG, errors="ignore").readlines()[-40:]))
    return False

def stop():
    try:
        requests.post(f"{API}/sdapi/v1/server-stop", timeout=10)
    except Exception:
        pass
    time.sleep(5)
    try:
        pid = int(open(PIDF).read().strip())
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception:
        pass
    time.sleep(5)
    subprocess.run("pkill -f 'launch.py' || true", shell=True)
    time.sleep(5)
    print("[forge] 종료 (VRAM 반환)")

def ensure():
    return True if alive() else start()

def has_adetailer():
    try:
        j = requests.get(f"{API}/sdapi/v1/scripts", timeout=20).json()
        names = [s.lower() for s in j.get("txt2img", [])]
        return any("adetailer" in n for n in names)
    except Exception:
        return False

def select_model(name_part="bs_base"):
    try:
        ms = requests.get(f"{API}/sdapi/v1/sd-models", timeout=60).json()
        tgt = next((m for m in ms if name_part in m["title"]), None) or ms[0]
        requests.post(f"{API}/sdapi/v1/options", timeout=600, json={
            "sd_model_checkpoint": tgt["title"],
            "sd_vae": "sdxl_vae_fp16fix.safetensors",
            "CLIP_stop_at_last_layers": 2,
            "samples_format": "png",
        })
        print("[forge] 모델:", tgt["title"])
        return True
    except Exception as e:
        print("[forge] 모델 선택 실패:", e)
        return False
