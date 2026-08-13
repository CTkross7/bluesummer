# -*- coding: utf-8 -*-
"""
BLUE SUMMER - 디바이스 판별 & CPU 폴백 어댑터 v1.0

GPU 주간 한도가 소진되어 세션에 GPU 가 붙지 않아도,
같은 체크포인트 / 같은 샘플러 / 같은 steps·CFG / 같은 해상도 /
같은 Hires fix / 같은 ADetailer / 같은 프롬프트로
'화질 규격을 하나도 바꾸지 않고' CPU 에서 계속 생성하기 위한 모듈.

하는 일
 1. 실제 사용 가능한 디바이스 판별 (torch.cuda 실제 할당까지 확인)
 2. CPU 모드일 때 스레드 / 환경변수 튜닝
 3. bs_forge 기동 인자를 CPU 용으로 교체
    - Forge 소스를 직접 grep 해서 '실제로 존재하는 플래그'만 넣는다.
      (미지원 인자를 넣으면 argparse 가 즉시 죽어 기동 자체가 실패한다)
 4. bs_forge 의 기동 대기 / 옵션 적용 타임아웃을 CPU 규모로 확장
 5. 엔진 로그의 VRAM 표기를 RAM 표기로 교체 (선택)

건드리지 않는 것
 - steps / cfg / width / height / sampler / scheduler / hr_* / ad_* /
   프롬프트 / 네거티브 / WebP 품질 등 화질에 영향을 주는 모든 값

환경변수
 BS_FORCE_DEVICE      = cpu | cuda   강제 지정
 BS_CPU_THREADS       = 4            스레드 수 강제
 BS_CPU_LAUNCH_WAIT   = 2400         Forge 기동 대기(초)
 BS_CPU_OPTIONS_TIMEOUT = 3600       체크포인트 로딩 대기(초)
 BS_CPU_TRAIN         = 1            CPU 에서도 LoRA 학습 시도(비권장)
"""

import os
import sys
import glob
import time

sys.path.insert(0, "/kaggle/working/BLUESUMMER")

import bs_log as L


# =====================================================================
# 상수
# =====================================================================

FORGE_DIR = "/kaggle/temp/forge"

LAUNCH_WAIT = int(os.environ.get("BS_CPU_LAUNCH_WAIT", "2400"))
OPTIONS_TIMEOUT = int(os.environ.get("BS_CPU_OPTIONS_TIMEOUT", "3600"))

_S = {
    "device": None,
    "gpus": 0,
    "env": False,
    "forge": False,
    "engine": False,
    "src": None,
}

IS_CPU = False


# =====================================================================
# 디바이스 판별
# =====================================================================

def detect(refresh=False):
    """실제로 쓸 수 있는 디바이스를 판별한다.

    torch.cuda.is_available() 만 믿지 않고 실제 할당까지 시도한다.
    Kaggle 은 한도 초과 시 Accelerator 설정이 GPU 여도 CPU 런타임을
    내려주는 경우가 있기 때문이다.
    """
    global IS_CPU

    if _S["device"] and not refresh:
        return _S["device"]

    force = os.environ.get("BS_FORCE_DEVICE", "").strip().lower()

    dev = "cpu"
    gpus = 0

    if force == "cpu":
        L.warn("[device] BS_FORCE_DEVICE=cpu - CPU 모드 강제")
    else:
        try:
            import torch

            if torch.cuda.is_available() and torch.cuda.device_count() > 0:
                try:
                    t = torch.zeros(8, device="cuda")
                    del t
                    torch.cuda.empty_cache()
                    dev = "cuda"
                    gpus = torch.cuda.device_count()
                except Exception as e:
                    L.warn("[device] CUDA 초기화 실패 -> CPU 폴백 : %s" % e)
            else:
                if force == "cuda":
                    L.warn("[device] BS_FORCE_DEVICE=cuda 지만 "
                           "CUDA 를 쓸 수 없습니다 - CPU 로 진행")
        except Exception as e:
            L.warn("[device] torch 확인 실패 -> CPU 폴백 : %s" % e)

    _S["device"] = dev
    _S["gpus"] = gpus
    IS_CPU = (dev == "cpu")

    return dev


def is_cpu():
    return detect() == "cpu"


def gpu_count():
    detect()
    return _S["gpus"]


# =====================================================================
# 자원 정보
# =====================================================================

def threads():
    """사용할 CPU 스레드 수."""
    v = os.environ.get("BS_CPU_THREADS", "").strip()
    if v.isdigit() and int(v) > 0:
        return int(v)
    try:
        n = len(os.sched_getaffinity(0))
    except Exception:
        n = os.cpu_count() or 4
    return max(1, int(n))


def _meminfo():
    tot = 0.0
    avail = 0.0
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    tot = float(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail = float(line.split()[1])
    except Exception:
        pass
    return tot, avail


def ram_gb():
    tot, _ = _meminfo()
    return tot / 1024.0 / 1024.0


def mem_text():
    """엔진 로그용 - GPU 대신 시스템 RAM 사용량을 보여준다."""
    tot, avail = _meminfo()
    if tot <= 0:
        return ""
    used = (tot - avail) / 1024.0 / 1024.0
    return "RAM %.1f/%.1fG" % (used, tot / 1024.0 / 1024.0)


# =====================================================================
# 환경 튜닝
# =====================================================================

def apply_env(force=False):
    """CPU 모드용 스레드 / 환경변수 설정.

    여기서 os.environ 에 심어두면 bs_forge._env() 가 그대로 복사해
    Forge 서브프로세스에도 동일하게 적용된다.
    """
    if detect() != "cpu":
        _S["env"] = True
        return False

    if _S["env"] and not force:
        return True

    n = threads()

    # 잔여 CUDA 초기화 시도를 원천 차단 (ADetailer / ultralytics 포함)
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

    for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
              "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ[k] = str(n)

    os.environ.setdefault("KMP_BLOCKTIME", "1")
    os.environ.setdefault("MALLOC_ARENA_MAX", "2")
    os.environ["PYTORCH_NO_CUDA_MEMORY_CACHING"] = "1"

    try:
        import torch
        torch.set_num_threads(n)
        try:
            torch.set_num_interop_threads(max(1, n // 2))
        except Exception:
            pass
    except Exception:
        pass

    _S["env"] = True
    L.ok("[device] CPU 환경 설정 완료 : 스레드 %d / RAM %.1fGB"
         % (n, ram_gb()))
    return True


# =====================================================================
# Forge 플래그 지원 여부 확인
# =====================================================================

_FLAG_SRC = (
    "modules/cmd_args.py",
    "modules/shared_cmd_options.py",
    "backend/args.py",
    "modules_forge/forge_args.py",
    "modules_forge/main_entry.py",
)


def _source_text(refresh=False):
    """Forge 인자 정의 소스를 모아 문자열로 반환."""
    if _S["src"] is not None and not refresh:
        return _S["src"]

    buf = []
    paths = [os.path.join(FORGE_DIR, rel) for rel in _FLAG_SRC]
    paths += sorted(glob.glob(os.path.join(FORGE_DIR, "modules_forge", "*.py")))

    seen = set()
    for p in paths:
        if p in seen or not os.path.isfile(p):
            continue
        seen.add(p)
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                buf.append(f.read())
        except Exception:
            pass

    _S["src"] = "\n".join(buf)
    return _S["src"]


def flag_ok(flag):
    """해당 커맨드라인 플래그가 Forge 에 실제로 정의돼 있는가.

    True  = 있음 / False = 없음 / None = 소스를 못 읽어 판정 불가
    """
    text = _source_text()
    if not text:
        return None
    return ('"%s"' % flag) in text or ("'%s'" % flag) in text


# =====================================================================
# CPU 기동 인자
# =====================================================================

def forge_args_cpu():
    """CPU 전용 Forge 기동 인자 목록을 만든다."""
    import bs_forge as FG

    store = FG.STORE

    base = [
        "--api",
        "--api-log",
        "--nowebui",
        "--listen",
        "--port %d" % FG.PORT,

        "--skip-torch-cuda-test",
        "--skip-python-version-check",
        "--skip-version-check",

        "--no-hashing",
        "--disable-nan-check",
    ]

    # CPU 강제 계열. 존재하는 것만 넣는다.
    #   --always-cpu   : Forge backend(memory_management) 를 CPU 로 고정
    #   --use-cpu all  : A1111 계열 모듈(ESRGAN 업스케일러 등)도 CPU 로
    #   --all-in-fp32  : CPU 는 fp16 연산이 사실상 없으므로 전부 fp32
    #   --precision full / --no-half / --no-half-vae : 동일 목적의 이중 안전장치
    want = [
        ("--always-cpu", ""),
        ("--use-cpu", "all"),
        ("--all-in-fp32", ""),
        ("--precision", "full"),
        ("--no-half", ""),
        ("--no-half-vae", ""),
    ]

    picked = []
    skipped = []

    for flag, val in want:
        ok = flag_ok(flag)
        if ok is False:
            skipped.append(flag)
            continue
        picked.append(flag if not val else "%s %s" % (flag, val))

    args = base + picked + [
        "--ckpt-dir %s/Stable-diffusion" % store,
        "--vae-dir %s/VAE" % store,
        "--esrgan-models-path %s/ESRGAN" % store,
        "--lora-dir %s/Lora" % store,
    ]

    if skipped:
        L.log("[device] 이 Forge 버전이 지원하지 않아 제외한 인자 : %s"
              % ", ".join(skipped))

    return args


# =====================================================================
# Forge 옵션 적용 (CPU 용 - 타임아웃 확장)
# =====================================================================

def _apply_options_cpu(ckpt_title, vae="sdxl_vae.safetensors", clip_skip=2):
    """bs_forge.apply_options 의 CPU 판.

    CPU 는 6.5GB 체크포인트를 fp32 로 올리는 데 5~15분이 걸리므로
    원본의 timeout=600 으로는 무조건 실패한다.
    """
    import requests
    import bs_forge as FG

    core = {
        "sd_model_checkpoint": ckpt_title,
        "sd_vae": vae,
        "CLIP_stop_at_last_layers": clip_skip,
        "samples_save": False,
        "grid_save": False,
        "live_previews_enable": False,
        "show_progress_every_n_steps": 0,
        "upscaler_for_img2img": "4x-UltraSharp",
    }

    # CPU 에서 ESRGAN 을 작은 타일로 나눠 처리해 RAM 폭주를 막는다.
    # (출력 화질에는 영향이 없고 속도/메모리만 달라진다)
    extra = dict(core)
    extra["ESRGAN_tile"] = 192
    extra["ESRGAN_tile_overlap"] = 8

    L.log("[device] CPU 모드 : 체크포인트 로딩에 5~15분이 걸릴 수 있습니다 "
          "(타임아웃 %d초)" % OPTIONS_TIMEOUT)

    for payload, tag in ((extra, "확장"), (core, "기본")):
        try:
            r = requests.post(FG.API + "/sdapi/v1/options",
                              json=payload, timeout=OPTIONS_TIMEOUT)
            L.log("옵션 적용(%s) HTTP %s" % (tag, r.status_code))
            if r.status_code == 200:
                return True
        except Exception as e:
            L.warn("옵션 적용(%s) 실패: %s" % (tag, e))

    return False


# =====================================================================
# bs_forge 패치
# =====================================================================

def apply_forge(force=False):
    """bs_forge 를 CPU 용으로 교체한다. 여러 번 불러도 안전하다."""
    if detect() != "cpu":
        return False

    if _S["forge"] and not force:
        return True

    apply_env()

    import bs_forge as FG

    # 플래그 판정을 위해 소스가 반드시 있어야 한다
    if not os.path.isfile(os.path.join(FORGE_DIR, "modules", "cmd_args.py")):
        try:
            FG.clone()
        except Exception as e:
            L.warn("[device] Forge clone 확인 실패: %s" % e)

    _source_text(refresh=True)

    args = forge_args_cpu()

    # 리스트 객체 자체를 유지한 채 내용만 교체 (다른 모듈이 참조 중이어도 반영)
    FG.BASE_ARGS[:] = args

    L.ok("[device] Forge 기동 인자를 CPU 용으로 교체했습니다")
    for a in args:
        L.log("    " + a)

    if not getattr(FG, "_BS_CPU_PATCHED", False):
        _orig_launch = FG.launch

        def _launch_cpu(wait=None, attempts=2, _o=_orig_launch):
            return _o(wait=int(wait or LAUNCH_WAIT), attempts=attempts)

        FG.launch = _launch_cpu
        FG.apply_options = _apply_options_cpu
        FG._BS_CPU_PATCHED = True

        L.ok("[device] Forge 기동 대기 %d초 / 옵션 적용 %d초로 확장"
             % (LAUNCH_WAIT, OPTIONS_TIMEOUT))

    _S["forge"] = True
    return True


# =====================================================================
# bs_engine 패치 (선택)
# =====================================================================

def patch_engine(force=False):
    """엔진 로그의 VRAM 표기를 RAM 표기로 바꾼다.

    bs_engine 이 완전히 로드된 뒤에만 호출해야 한다.
    """
    if detect() != "cpu":
        return False

    if _S["engine"] and not force:
        return True

    try:
        import bs_engine as E
        if not hasattr(E, "self_test"):
            return False
        E._vram = mem_text
        _S["engine"] = True
        L.log("[device] 엔진 메모리 로그를 RAM 표기로 전환")
        return True
    except Exception as e:
        L.warn("[device] 엔진 패치 생략: %s" % e)
        return False


# =====================================================================
# 요약 출력
# =====================================================================

def report():
    dev = detect()

    if dev == "cuda":
        L.ok("[device] GPU 모드 (%d장) - 기존 설정 그대로 동작합니다"
             % _S["gpus"])
        return dev

    L.warn("[device] 사용 가능한 GPU 가 없습니다 -> CPU 모드로 동작합니다")
    L.log("[device] 스레드 %d / RAM %.1fGB" % (threads(), ram_gb()))
    L.log("[device] 화질 규격(체크포인트·샘플러·steps·CFG·해상도·"
          "Hires·ADetailer·프롬프트)은 GPU 때와 완전히 동일합니다.")
    L.log("[device] 달라지는 것은 속도뿐입니다.")
    L.log("[device] 예상 소요(4코어 기준) : 인물 1장 30~60분 / "
          "배경 1장 25~50분 / UI 1장 8~15분")
    L.log("[device] LoRA 학습은 CPU 에서 현실적으로 불가능하므로 "
          "자동으로 건너뜁니다.")
    L.log("[device]   (이미 학습된 LoRA 가 있으면 CPU 생성에도 "
          "그대로 적용됩니다)")
    return dev


def apply_all():
    """환경 + Forge 를 한 번에 적용."""
    dev = detect()
    apply_env()
    if dev == "cpu":
        try:
            apply_forge()
        except Exception as e:
            L.warn("[device] Forge 패치 지연(아직 미설치일 수 있음): %s" % e)
    return dev


# =====================================================================
# import 시 자동 판별
# =====================================================================

detect()
