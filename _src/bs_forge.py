# -*- coding: utf-8 -*-
"""Forge 설치 / 호환성 복구(doctor) / 기동 / 종료 통합 모듈 (v3).

   기동 실패의 실제 원인이었던
     - mediapipe 1.0.0 -> numpy 2.x 승격 -> skimage(np.float_) 붕괴
     - torch 2.10 환경의 xformers 0.0.28 불일치
   를 자동 감지·복구한 뒤에야 서버를 띄운다."""
import os, sys, time, signal, subprocess, requests

sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_log as L

FORGE      = "/kaggle/temp/forge"
STORE      = "/kaggle/temp/models"
LOGFILE    = "/kaggle/temp/forge.log"
MARKER     = "/kaggle/temp/.forge_env_ready"
PORT       = 7860
API        = "http://127.0.0.1:%d" % PORT
CONSTRAINT = "/kaggle/temp/pip-constraints.txt"

EXT_REPOS = [("adetailer", "https://github.com/Bing-su/adetailer")]

BASE_ARGS = [
    "--api", "--api-log", "--nowebui", "--listen", "--port %d" % PORT,
    "--skip-torch-cuda-test", "--skip-python-version-check", "--skip-version-check",
    "--no-half-vae", "--disable-nan-check", "--opt-channelslast",
    "--cuda-malloc", "--no-hashing", "--device-id 0",
    "--ckpt-dir %s/Stable-diffusion" % STORE,
    "--vae-dir %s/VAE" % STORE,
    "--esrgan-models-path %s/ESRGAN" % STORE,
    "--lora-dir %s/Lora" % STORE,
]


def args_str():
    return " ".join(BASE_ARGS)


def _env():
    e = os.environ.copy()
    e["PIP_CONSTRAINT"] = CONSTRAINT
    e["PIP_PREFER_BINARY"] = "1"
    e["PIP_ROOT_USER_ACTION"] = "ignore"
    e["PYTHONUNBUFFERED"] = "1"
    return e


# ---------------------------------------------------------------- 설치
def clone():
    os.makedirs("/kaggle/temp", exist_ok=True)
    if not os.path.isdir(os.path.join(FORGE, ".git")):
        L.log("Forge clone ...")
        L.shell("git clone --depth 1 "
                "https://github.com/lllyasviel/stable-diffusion-webui-forge %s" % FORGE)
    else:
        L.log("Forge 이미 존재")
    ext = os.path.join(FORGE, "extensions")
    os.makedirs(ext, exist_ok=True)
    for name, url in EXT_REPOS:
        d = os.path.join(ext, name)
        if not os.path.isdir(d):
            L.shell("git clone --depth 1 %s %s" % (url, d), title="확장 설치 " + name)
        else:
            L.log("확장 존재 : " + name)
    for d in ["models/Stable-diffusion", "models/VAE", "models/ESRGAN",
              "models/Lora", "models/adetailer", "outputs"]:
        os.makedirs(os.path.join(FORGE, d), exist_ok=True)


def pre_pin():
    """Forge 가 requirements 를 건드리기 전에 위험 패키지를 먼저 못박는다."""
    L.log("호환 버전 선점 설치 (mediapipe<1.0 등)")
    L.shell('pip install -q "mediapipe<1.0"', quiet=True, title="mediapipe<1.0")
    L.shell('pip install -q "ultralytics>=8.2,<9" "py-cpuinfo" "protobuf<5"',
            quiet=True, title="ADetailer 런타임 의존성")


def doctor(verbose=True):
    """numpy / scikit-image / xformers 3대 파손 지점 자동 복구."""
    fixed = []

    rc, out = L.shell('python -c "import numpy;print(\'NPV\'+numpy.__version__)"',
                      quiet=True)
    ver = ""
    for line in out.splitlines():
        if line.startswith("NPV"):
            ver = line[3:].strip()
    if ver.startswith("2."):
        L.warn("numpy %s 감지 -> 1.26.4 로 복구 (skimage/Forge 호환)" % ver)
        L.shell('pip install -q --force-reinstall "numpy==1.26.4"', title="numpy 복구")
        fixed.append("numpy")
    elif verbose:
        L.log("numpy %s : 정상" % (ver or "?"))

    rc, out = L.shell('python -c "from skimage import exposure;print(\'SKOK\')"',
                      quiet=True)
    if "SKOK" not in out:
        L.warn("scikit-image 임포트 실패 -> 0.24.0 재설치 (np.float_ 미사용 버전)")
        L.shell('pip install -q "scikit-image==0.24.0"', title="scikit-image 복구")
        rc, out = L.shell('python -c "from skimage import exposure;print(\'SKOK\')"',
                          quiet=True)
        fixed.append("scikit-image")
    if "SKOK" in out and verbose:
        L.log("scikit-image : 정상")

    rc, out = L.shell('python -c "import xformers,xformers.ops;print(\'XOK\')"',
                      quiet=True)
    if "XOK" not in out:
        rc2, o2 = L.shell("pip show xformers", quiet=True)
        if "Name: xformers" in o2:
            L.warn("torch 버전과 맞지 않는 xformers 발견 -> 제거 (SDPA 로 대체)")
            L.shell("pip uninstall -q -y xformers", title="xformers 제거")
            fixed.append("xformers")
    elif verbose:
        L.log("xformers : 정상(사용하지 않지만 무해)")

    rc, out = L.shell('python -c "import cv2;print(\'CVOK\')"', quiet=True)
    if "CVOK" not in out:
        L.shell('pip install -q opencv-python-headless', title="opencv 복구")
        fixed.append("opencv")

    if fixed:
        L.ok("doctor 복구 항목 : %s" % ", ".join(fixed))
    else:
        L.ok("doctor : 복구할 항목 없음")
    return fixed


def _killpg(proc):
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


def install_env(force=False, timeout=2700):
    """launch.py --exit 로 의존성만 먼저 설치한다. (기동과 분리)"""
    if os.path.exists(MARKER) and not force:
        L.log("Forge 의존성 준비 완료 표식 발견 - 설치 단계 생략")
        doctor()
        return True
    clone()
    pre_pin()
    L.banner("Forge 의존성 설치 (launch.py --exit)")
    cmd = ("cd %s && python launch.py --exit --skip-torch-cuda-test "
           "--skip-python-version-check --skip-version-check --no-hashing" % FORGE)
    f = open(LOGFILE, "a", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(cmd, shell=True, stdout=f, stderr=subprocess.STDOUT,
                            env=_env(), preexec_fn=os.setsid)
    t0 = time.time()
    while True:
        if proc.poll() is not None:
            L.ok("의존성 설치 프로세스 종료 (rc=%s, %.1f분)"
                 % (proc.returncode, (time.time() - t0) / 60))
            break
        if alive(2):
            L.warn("--exit 미지원 빌드 - 임시 기동 감지, 종료 후 진행")
            _killpg(proc)
            time.sleep(5)
            break
        if time.time() - t0 > timeout:
            L.err("의존성 설치 타임아웃")
            _killpg(proc)
            break
        time.sleep(15)
    f.close()
    L.tail_file(LOGFILE, 25, title="forge.log 끝부분")
    doctor()
    with open(MARKER, "w") as g:
        g.write(time.strftime("%Y-%m-%d %H:%M:%S"))
    return True


# ---------------------------------------------------------------- 기동
def alive(timeout=5):
    try:
        return requests.get(API + "/sdapi/v1/sd-models", timeout=timeout).status_code == 200
    except Exception:
        return False


def launch(wait=900, attempts=2):
    if alive():
        L.ok("Forge 이미 기동 중")
        return True
    install_env()
    for attempt in range(1, attempts + 1):
        L.banner("Forge API 기동 시도 %d/%d" % (attempt, attempts))
        f = open(LOGFILE, "a", encoding="utf-8", errors="replace")
        cmd = "cd %s && python launch.py %s" % (FORGE, args_str())
        L.log("$ " + cmd)
        proc = subprocess.Popen(cmd, shell=True, stdout=f, stderr=subprocess.STDOUT,
                                env=_env(), preexec_fn=os.setsid)
        t0, last = time.time(), 0
        while time.time() - t0 < wait:
            if alive(5):
                L.ok("API 응답 (%.0f초)" % (time.time() - t0))
                f.close()
                return True
            if proc.poll() is not None:
                L.err("기동 프로세스가 죽었습니다 (rc=%s)" % proc.returncode)
                break
            if time.time() - last > 60:
                last = time.time()
                L.log("   기동 대기 %.0f초 ..." % (time.time() - t0))
            time.sleep(6)
        f.close()
        txt = L.tail_file(LOGFILE, 40, title="forge.log 끝부분")
        low = txt.lower()
        if "np.float_" in txt or "numpy" in low or "skimage" in low or "xformers" in low:
            L.warn("의존성 문제로 판단 -> doctor 재실행 후 재시도")
            doctor()
        else:
            L.warn("원인 불명 -> doctor 후 재시도")
            doctor(verbose=False)
        subprocess.run("pkill -f 'launch.py' > /dev/null 2>&1", shell=True)
        time.sleep(8)
    L.err("Forge 기동 실패 - /kaggle/temp/forge.log 를 확인하세요")
    return False


def models():
    try:
        return requests.get(API + "/sdapi/v1/sd-models", timeout=60).json()
    except Exception:
        return []


def upscalers():
    try:
        return [u["name"] for u in requests.get(API + "/sdapi/v1/upscalers",
                                                timeout=60).json()]
    except Exception:
        return []


def resolve_checkpoint(want="novaanimexl_ilv190"):
    for m in models():
        for key in ("model_name", "title", "filename"):
            v = str(m.get(key, ""))
            if want.lower() in v.lower().replace(" ", ""):
                return m.get("title") or m.get("model_name")
    return None


def apply_options(ckpt_title, vae="sdxl_vae.safetensors", clip_skip=2):
    opts = {
        "sd_model_checkpoint": ckpt_title,
        "sd_vae": vae,
        "CLIP_stop_at_last_layers": clip_skip,
        "samples_save": False,
        "grid_save": False,
        "live_previews_enable": False,
        "show_progress_every_n_steps": 0,
        "upscaler_for_img2img": "4x-UltraSharp",
    }
    try:
        r = requests.post(API + "/sdapi/v1/options", json=opts, timeout=600)
        L.log("옵션 적용 HTTP %s (체크포인트 로딩까지 수 분 소요 가능)" % r.status_code)
        return r.status_code == 200
    except Exception as e:
        L.warn("옵션 적용 실패: %s" % e)
        return False


def verify(need_upscalers=("4x-UltraSharp", "4x-AnimeSharp")):
    ms = [m.get("model_name", "") for m in models()]
    us = upscalers()
    L.log("체크포인트 : %s" % ms)
    L.log("업스케일러 : %s" % us)
    ok_ck = any("v190" in m.lower() for m in ms)
    miss = [n for n in need_upscalers if not any(n.lower() == u.lower() for u in us)]
    if not ok_ck:
        L.err("novaAnimeXL_ilV190 미인식 - 다운로드 셀을 다시 실행하세요")
    if miss:
        L.err("업스케일러 미인식 : %s" % miss)
    return ok_ck and not miss


def ensure(clip_skip=2):
    """어떤 상태에서 호출해도 '사용 가능한 Forge' 를 보장한다."""
    if not alive():
        if not launch():
            return False
    if not verify():
        return False
    title = resolve_checkpoint()
    if title:
        apply_options(title, clip_skip=clip_skip)
    return True


def stop(wait=90):
    L.log("Forge 종료 요청")
    try:
        requests.post(API + "/sdapi/v1/unload-checkpoint", timeout=60)
    except Exception:
        pass
    subprocess.run("pkill -f 'launch.py' > /dev/null 2>&1", shell=True)
    subprocess.run("pkill -f 'webui.py' > /dev/null 2>&1", shell=True)
    t0 = time.time()
    while time.time() - t0 < wait:
        if not alive(3):
            break
        time.sleep(3)
    time.sleep(6)
    L.shell("nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader",
            quiet=False, title="종료 후 VRAM")
    L.ok("Forge 종료 완료")
