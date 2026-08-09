
# -*- coding: utf-8 -*-

"""
Forge 설치 / 호환성 복구(doctor) / 기동 / 종료 통합 모듈 (v4).

주요 호환성 처리
- mediapipe < 1.0
- numpy 1.26.4 고정
- Forge requirements_versions.txt의 numpy 1.26.2 pin을 1.26.4로 보정
- scikit-image 호환성 확인
- torch/xformers 불일치 감지
- OpenCV import 확인
- dependency 설치 실패 시 READY marker 생성 금지
- Forge API 기동 및 모델/업스케일러 검증
"""

import os
import sys
import time
import signal
import subprocess
import requests


sys.path.insert(0, "/kaggle/working/BLUESUMMER")

import bs_log as L


# =====================================================================
# 경로 / 상수
# =====================================================================

FORGE = "/kaggle/temp/forge"
STORE = "/kaggle/temp/models"

LOGFILE = "/kaggle/temp/forge.log"
MARKER = "/kaggle/temp/.forge_env_ready"

PORT = 7860
API = "http://127.0.0.1:%d" % PORT

CONSTRAINT = "/kaggle/temp/pip-constraints.txt"

EXT_REPOS = [
    (
        "adetailer",
        "https://github.com/Bing-su/adetailer"
    ),
]


# =====================================================================
# Forge 실행 인자
# =====================================================================

BASE_ARGS = [
    "--api",
    "--api-log",
    "--nowebui",
    "--listen",
    "--port %d" % PORT,

    "--skip-torch-cuda-test",
    "--skip-python-version-check",
    "--skip-version-check",

    "--no-half-vae",
    "--disable-nan-check",

    "--opt-channelslast",
    "--cuda-malloc",
    "--no-hashing",

    "--device-id 0",

    "--ckpt-dir %s/Stable-diffusion" % STORE,
    "--vae-dir %s/VAE" % STORE,
    "--esrgan-models-path %s/ESRGAN" % STORE,
    "--lora-dir %s/Lora" % STORE,
]


# =====================================================================
# 유틸리티
# =====================================================================

def args_str():
    return " ".join(BASE_ARGS)


def _env():
    """
    Forge / pip 실행 환경.

    PIP_CONSTRAINT를 통해 NumPy 1.26.4를 강제한다.
    """

    e = os.environ.copy()

    e["PIP_CONSTRAINT"] = CONSTRAINT
    e["PIP_PREFER_BINARY"] = "1"
    e["PIP_ROOT_USER_ACTION"] = "ignore"
    e["PYTHONUNBUFFERED"] = "1"

    return e


def _killpg(proc):
    """프로세스 그룹 전체 종료."""

    try:
        os.killpg(
            os.getpgid(proc.pid),
            signal.SIGTERM
        )
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


def _write_constraint():
    """
    BLUE SUMMER용 pip constraint 생성.

    NumPy 1.26.4를 유지하고 protobuf는 5 미만으로 제한한다.
    """

    os.makedirs(
        os.path.dirname(CONSTRAINT),
        exist_ok=True
    )

    with open(
        CONSTRAINT,
        "w",
        encoding="utf-8"
    ) as f:
        f.write("numpy==1.26.4\n")
        f.write("protobuf<5\n")

    L.log(
        "pip constraint : numpy==1.26.4 / protobuf<5",
        "OK"
    )


def _patch_forge_requirements():
    """
    Forge requirements_versions.txt의 오래된 NumPy pin을 수정한다.

    기존:
        numpy==1.26.2

    변경:
        numpy==1.26.4

    원본에 NumPy 1.26.2가 없으면 아무것도 하지 않는다.
    """

    req = os.path.join(
        FORGE,
        "requirements_versions.txt"
    )

    if not os.path.isfile(req):
        L.warn(
            "Forge requirements_versions.txt 없음: %s" % req
        )
        return False

    try:
        with open(
            req,
            "r",
            encoding="utf-8"
        ) as f:
            text = f.read()

        old = "numpy==1.26.2"
        new = "numpy==1.26.4"

        if old in text:
            text = text.replace(old, new)

            with open(
                req,
                "w",
                encoding="utf-8"
            ) as f:
                f.write(text)

            L.log(
                "Forge requirements: numpy 1.26.2 -> 1.26.4",
                "OK"
            )

        else:
            L.log(
                "Forge requirements에 numpy==1.26.2 없음",
                "INFO"
            )

        # 실제 NumPy 요구사항 출력
        numpy_lines = []

        for line in text.splitlines():
            stripped = line.strip()

            if stripped.lower().startswith("numpy"):
                numpy_lines.append(stripped)

        if numpy_lines:
            L.log(
                "Forge NumPy 요구사항 : %s"
                % ", ".join(numpy_lines),
                "INFO"
            )

        return True

    except Exception as e:
        L.err(
            "Forge requirements 패치 실패: %s" % e
        )
        return False


# =====================================================================
# Forge 설치
# =====================================================================

def clone():
    """
    Forge 및 ADetailer clone.

    모든 임시 파일은 /kaggle/temp에 둔다.
    """

    os.makedirs(
        "/kaggle/temp",
        exist_ok=True
    )

    # -------------------------------------------------------------
    # Forge
    # -------------------------------------------------------------

    if not os.path.isdir(
        os.path.join(FORGE, ".git")
    ):
        L.log("Forge clone ...")

        rc, out = L.shell(
            "git clone --depth 1 "
            "https://github.com/lllyasviel/stable-diffusion-webui-forge "
            "%s" % FORGE
        )

        if rc != 0:
            L.err("Forge clone 실패")
            return False

    else:
        L.log("Forge 이미 존재")

    # -------------------------------------------------------------
    # Extensions
    # -------------------------------------------------------------

    ext = os.path.join(
        FORGE,
        "extensions"
    )

    os.makedirs(
        ext,
        exist_ok=True
    )

    for name, url in EXT_REPOS:

        d = os.path.join(
            ext,
            name
        )

        if not os.path.isdir(d):

            rc, out = L.shell(
                "git clone --depth 1 %s %s"
                % (url, d),
                title="확장 설치 " + name
            )

            if rc != 0:
                L.warn(
                    "확장 clone 실패 : %s" % name
                )

        else:
            L.log(
                "확장 존재 : " + name
            )

    # -------------------------------------------------------------
    # Forge 내부 모델 디렉터리
    # -------------------------------------------------------------

    for d in [
        "models/Stable-diffusion",
        "models/VAE",
        "models/ESRGAN",
        "models/Lora",
        "models/adetailer",
        "outputs",
    ]:

        os.makedirs(
            os.path.join(FORGE, d),
            exist_ok=True
        )

    return True


def pre_pin():
    """
    Forge requirements 설치 전에 호환 버전을 선점한다.

    핵심:
    - NumPy 1.26.4 유지
    - mediapipe < 1.0
    - protobuf < 5
    - ADetailer 런타임 의존성
    - Forge requirements의 NumPy pin 보정
    """

    L.log(
        "호환 버전 선점 설치 "
        "(numpy 1.26.4 / mediapipe<1.0 등)"
    )

    # -------------------------------------------------------------
    # pip constraint 생성
    # -------------------------------------------------------------

    _write_constraint()

    # -------------------------------------------------------------
    # NumPy + MediaPipe
    # -------------------------------------------------------------

    L.shell(
        'pip install -q '
        '"numpy==1.26.4" '
        '"mediapipe<1.0" '
        '"protobuf<5"',
        quiet=True,
        title="numpy 1.26.4 + mediapipe<1.0"
    )

    # -------------------------------------------------------------
    # ADetailer 런타임 의존성
    # -------------------------------------------------------------

    L.shell(
        'pip install -q '
        '"ultralytics>=8.2,<9" '
        '"py-cpuinfo" '
        '"protobuf<5"',
        quiet=True,
        title="ADetailer 런타임 의존성"
    )

    # -------------------------------------------------------------
    # Forge requirements 수정
    # -------------------------------------------------------------

    _patch_forge_requirements()


# =====================================================================
# Doctor
# =====================================================================

def doctor(verbose=True):
    """
    주요 Python/AI 의존성을 검사하고 필요한 경우 복구한다.

    검사:
    - numpy
    - scikit-image
    - xformers
    - OpenCV
    """

    fixed = []

    # =============================================================
    # NumPy
    # =============================================================

    rc, out = L.shell(
        'python -c '
        '"import numpy;print(\'NPV\'+numpy.__version__)"',
        quiet=True
    )

    ver = ""

    for line in out.splitlines():

        if line.startswith("NPV"):
            ver = line[3:].strip()
            break

    if ver.startswith("2."):

        L.warn(
            "numpy %s 감지 -> 1.26.4 로 복구"
            % ver
        )

        L.shell(
            'pip install -q --force-reinstall '
            '"numpy==1.26.4"',
            title="numpy 복구"
        )

        fixed.append("numpy")

    elif ver != "1.26.4":

        L.warn(
            "numpy %s 감지 -> 1.26.4로 고정"
            % (ver or "?")
        )

        L.shell(
            'pip install -q '
            '"numpy==1.26.4"',
            title="numpy 1.26.4 고정"
        )

        fixed.append("numpy")

    elif verbose:

        L.log(
            "numpy %s : 정상" % ver
        )

    # =============================================================
    # scikit-image
    # =============================================================

    rc, out = L.shell(
        'python -c '
        '"from skimage import exposure;print(\'SKOK\')"',
        quiet=True
    )

    if "SKOK" not in out:

        L.warn(
            "scikit-image 임포트 실패 "
            "-> 0.24.0 재설치"
        )

        L.shell(
            'pip install -q "scikit-image==0.24.0"',
            title="scikit-image 복구"
        )

        rc, out = L.shell(
            'python -c '
            '"from skimage import exposure;print(\'SKOK\')"',
            quiet=True
        )

        fixed.append("scikit-image")

    if "SKOK" in out and verbose:

        L.log(
            "scikit-image : 정상"
        )

    # =============================================================
    # xformers
    # =============================================================

    rc, out = L.shell(
        'python -c '
        '"import xformers,xformers.ops;print(\'XOK\')"',
        quiet=True
    )

    if "XOK" not in out:

        rc2, o2 = L.shell(
            "pip show xformers",
            quiet=True
        )

        if "Name: xformers" in o2:

            L.warn(
                "torch 버전과 맞지 않는 xformers 발견 "
                "-> 제거 (SDPA 사용)"
            )

            L.shell(
                "pip uninstall -q -y xformers",
                title="xformers 제거"
            )

            fixed.append("xformers")

    elif verbose:

        L.log(
            "xformers : 정상(사용하지 않지만 무해)"
        )

    # =============================================================
    # OpenCV
    # =============================================================

    rc, out = L.shell(
        'python -c '
        '"import cv2;print(\'CVOK\')"',
        quiet=True
    )

    if "CVOK" not in out:

        L.warn(
            "OpenCV 임포트 실패 -> 복구"
        )

        L.shell(
            "pip install -q opencv-python-headless",
            title="opencv 복구"
        )

        fixed.append("opencv")

    elif verbose:

        L.log(
            "opencv : 정상"
        )

    # =============================================================
    # 결과
    # =============================================================

    if fixed:

        L.ok(
            "doctor 복구 항목 : %s"
            % ", ".join(fixed)
        )

    else:

        L.ok(
            "doctor : 복구할 항목 없음"
        )

    return fixed


# =====================================================================
# Forge 의존성 설치
# =====================================================================

def install_env(force=False, timeout=2700):
    """
    Forge 의존성을 설치한다.

    매우 중요:
    launch.py --exit가 실패하면 READY marker를 절대로 생성하지 않는다.
    """

    # -------------------------------------------------------------
    # 기존 marker
    # -------------------------------------------------------------

    if os.path.exists(MARKER) and not force:

        L.log(
            "Forge 의존성 준비 완료 표식 발견 - 설치 단계 생략"
        )

        # marker가 있어도 최소 검증은 수행
        _write_constraint()
        _patch_forge_requirements()

        doctor()

        return True

    # -------------------------------------------------------------
    # 준비
    # -------------------------------------------------------------

    if not clone():

        L.err(
            "Forge clone 실패"
        )

        return False

    pre_pin()

    # -------------------------------------------------------------
    # 기존 잘못된 marker 제거
    # -------------------------------------------------------------

    if os.path.exists(MARKER):

        try:
            os.remove(MARKER)
        except Exception:
            pass

    # -------------------------------------------------------------
    # Forge dependency 설치
    # -------------------------------------------------------------

    L.banner(
        "Forge 의존성 설치 (launch.py --exit)"
    )

    cmd = (
        "cd %s && "
        "python launch.py --exit "
        "--skip-torch-cuda-test "
        "--skip-python-version-check "
        "--skip-version-check "
        "--no-hashing"
    ) % FORGE

    f = open(
        LOGFILE,
        "a",
        encoding="utf-8",
        errors="replace"
    )

    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdout=f,
        stderr=subprocess.STDOUT,
        env=_env(),
        preexec_fn=os.setsid
    )

    t0 = time.time()
    rc = None

    while True:

        rc = proc.poll()

        # ---------------------------------------------------------
        # 프로세스 종료
        # ---------------------------------------------------------

        if rc is not None:

            elapsed = (
                (time.time() - t0) / 60
            )

            if rc == 0:

                L.ok(
                    "의존성 설치 성공 "
                    "(rc=0, %.1f분)"
                    % elapsed
                )

            else:

                L.err(
                    "의존성 설치 실패 "
                    "(rc=%s, %.1f분)"
                    % (rc, elapsed)
                )

            break

        # ---------------------------------------------------------
        # timeout
        # ---------------------------------------------------------

        if time.time() - t0 > timeout:

            L.err(
                "의존성 설치 타임아웃"
            )

            _killpg(proc)

            rc = 124

            break

        time.sleep(5)

    f.close()

    # -------------------------------------------------------------
    # 로그 출력
    # -------------------------------------------------------------

    L.tail_file(
        LOGFILE,
        40,
        title="forge.log 끝부분"
    )

    # =============================================================
    # 실패 처리
    # =============================================================

    if rc != 0:

        L.err(
            "Forge 의존성 설치가 실패했으므로 "
            "READY marker를 생성하지 않습니다."
        )

        doctor()

        return False

    # =============================================================
    # 최종 doctor
    # =============================================================

    doctor()

    # =============================================================
    # NumPy 최종 검증
    # =============================================================

    rc_np, out_np = L.shell(
        'python -c '
        '"import numpy;print(\'FINALNP=\'+numpy.__version__)"',
        quiet=True
    )

    final_np = ""

    for line in out_np.splitlines():

        if line.startswith("FINALNP="):

            final_np = line.split(
                "=",
                1
            )[1].strip()

            break

    if final_np != "1.26.4":

        L.err(
            "NumPy 최종 검증 실패 : %s"
            % (final_np or "?")
        )

        return False

    L.ok(
        "NumPy 최종 검증 : 1.26.4"
    )

    # =============================================================
    # Forge requirements 최종 검증
    # =============================================================

    req = os.path.join(
        FORGE,
        "requirements_versions.txt"
    )

    if os.path.isfile(req):

        with open(
            req,
            "r",
            encoding="utf-8"
        ) as f_req:

            req_text = f_req.read()

        if "numpy==1.26.2" in req_text:

            L.err(
                "Forge requirements에 "
                "numpy==1.26.2가 아직 남아 있습니다."
            )

            return False

    # =============================================================
    # 성공 marker
    # =============================================================

    with open(
        MARKER,
        "w",
        encoding="utf-8"
    ) as g:

        g.write(
            time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

    L.ok(
        "Forge 의존성 준비 완료 표식 생성"
    )

    return True


# =====================================================================
# API 상태
# =====================================================================

def alive(timeout=5):
    """
    Forge API가 실제 응답하는지 확인한다.
    """

    try:

        r = requests.get(
            API + "/sdapi/v1/sd-models",
            timeout=timeout
        )

        return r.status_code == 200

    except Exception:

        return False


# =====================================================================
# Forge API 기동
# =====================================================================

def launch(wait=900, attempts=2):
    """
    Forge API를 기동한다.
    """

    # -------------------------------------------------------------
    # 이미 기동 중
    # -------------------------------------------------------------

    if alive():

        L.ok(
            "Forge 이미 기동 중"
        )

        return True

    # -------------------------------------------------------------
    # dependency 준비
    # -------------------------------------------------------------

    if not install_env():

        L.err(
            "Forge 의존성 설치 실패"
        )

        return False

    # -------------------------------------------------------------
    # API 실행
    # -------------------------------------------------------------

    for attempt in range(
        1,
        attempts + 1
    ):

        L.banner(
            "Forge API 기동 시도 %d/%d"
            % (attempt, attempts)
        )

        f = open(
            LOGFILE,
            "a",
            encoding="utf-8",
            errors="replace"
        )

        cmd = (
            "cd %s && python launch.py %s"
            % (
                FORGE,
                args_str()
            )
        )

        L.log(
            "$ " + cmd
        )

        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=f,
            stderr=subprocess.STDOUT,
            env=_env(),
            preexec_fn=os.setsid
        )

        t0 = time.time()
        last = 0

        while time.time() - t0 < wait:

            # -----------------------------------------------------
            # API 응답
            # -----------------------------------------------------

            if alive(5):

                L.ok(
                    "API 응답 (%.0f초)"
                    % (time.time() - t0)
                )

                f.close()

                return True

            # -----------------------------------------------------
            # 프로세스 종료
            # -----------------------------------------------------

            if proc.poll() is not None:

                L.err(
                    "기동 프로세스가 죽었습니다 "
                    "(rc=%s)"
                    % proc.returncode
                )

                break

            # -----------------------------------------------------
            # 진행상황
            # -----------------------------------------------------

            if time.time() - last > 60:

                last = time.time()

                L.log(
                    "   기동 대기 %.0f초 ..."
                    % (time.time() - t0)
                )

            time.sleep(6)

        f.close()

        # ---------------------------------------------------------
        # 실패 로그
        # ---------------------------------------------------------

        txt = L.tail_file(
            LOGFILE,
            50,
            title="forge.log 끝부분"
        )

        low = txt.lower()

        # ---------------------------------------------------------
        # dependency 관련 실패
        # ---------------------------------------------------------

        if (
            "resolutionimpossible" in low
            or "numpy" in low
            or "skimage" in low
            or "scikit-image" in low
            or "xformers" in low
            or "dependency" in low
        ):

            L.warn(
                "의존성 문제로 판단 -> "
                "doctor 재실행 후 재시도"
            )

            doctor()

        else:

            L.warn(
                "원인 불명 -> doctor 후 재시도"
            )

            doctor(
                verbose=False
            )

        # ---------------------------------------------------------
        # 프로세스 정리
        # ---------------------------------------------------------

        _killpg(proc)

        time.sleep(5)

    # -------------------------------------------------------------
    # 최종 실패
    # -------------------------------------------------------------

    L.err(
        "Forge 기동 실패 - %s 를 확인하세요."
        % LOGFILE
    )

    return False


# =====================================================================
# API 모델
# =====================================================================

def models():
    try:

        r = requests.get(
            API + "/sdapi/v1/sd-models",
            timeout=60
        )

        return r.json()

    except Exception:

        return []


def upscalers():
    try:

        r = requests.get(
            API + "/sdapi/v1/upscalers",
            timeout=60
        )

        return [
            u["name"]
            for u in r.json()
        ]

    except Exception:

        return []


# =====================================================================
# 체크포인트 검색
# =====================================================================

def resolve_checkpoint(
    want="novaanimexl_ilv190"
):
    """
    원하는 체크포인트를 Forge API에서 찾는다.
    """

    for m in models():

        for key in (
            "model_name",
            "title",
            "filename"
        ):

            v = str(
                m.get(
                    key,
                    ""
                )
            )

            normalized = (
                v.lower()
                .replace(" ", "")
            )

            if want.lower() in normalized:

                return (
                    m.get("title")
                    or m.get("model_name")
                )

    return None


# =====================================================================
# Forge 옵션
# =====================================================================

def apply_options(
    ckpt_title,
    vae="sdxl_vae.safetensors",
    clip_skip=2
):
    """
    Forge API 기본 옵션 적용.
    """

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

        r = requests.post(
            API + "/sdapi/v1/options",
            json=opts,
            timeout=600
        )

        L.log(
            "옵션 적용 HTTP %s "
            "(체크포인트 로딩까지 "
            "수 분 소요 가능)"
            % r.status_code
        )

        return r.status_code == 200

    except Exception as e:

        L.warn(
            "옵션 적용 실패: %s" % e
        )

        return False


# =====================================================================
# 인식 검증
# =====================================================================

def verify(
    need_upscalers=(
        "4x-UltraSharp",
        "4x-AnimeSharp",
    )
):
    """
    체크포인트 및 업스케일러 인식 여부 확인.
    """

    ms = [
        m.get(
            "model_name",
            ""
        )
        for m in models()
    ]

    us = upscalers()

    L.log(
        "체크포인트 : %s" % ms
    )

    L.log(
        "업스케일러 : %s" % us
    )

    ok_ck = any(
        "v190" in m.lower()
        for m in ms
    )

    miss = [
        n
        for n in need_upscalers
        if not any(
            n.lower() == u.lower()
            for u in us
        )
    ]

    if not ok_ck:

        L.err(
            "novaAnimeXL_ilV190 미인식 - "
            "다운로드 셀을 다시 실행하세요"
        )

    if miss:

        L.err(
            "업스케일러 미인식 : %s"
            % miss
        )

    return (
        ok_ck
        and not miss
    )


# =====================================================================
# Forge 최종 보장
# =====================================================================

def ensure(clip_skip=2):
    """
    어떤 상태에서 호출해도
    '사용 가능한 Forge'를 보장한다.
    """

    if not alive():

        if not launch():

            return False

    if not verify():

        return False

    title = resolve_checkpoint()

    if title:

        apply_options(
            title,
            clip_skip=clip_skip
        )

    return True


# =====================================================================
# Forge 종료
# =====================================================================

def stop(wait=90):
    """
    Forge API 종료.
    """

    L.log(
        "Forge 종료 요청"
    )

    try:

        requests.post(
            API + "/sdapi/v1/unload-checkpoint",
            timeout=60
        )

    except Exception:
        pass

    subprocess.run(
        "pkill -f 'launch.py' > /dev/null 2>&1",
        shell=True
    )

    subprocess.run(
        "pkill -f 'webui.py' > /dev/null 2>&1",
        shell=True
    )

    t0 = time.time()

    while time.time() - t0 < wait:

        if not alive(3):

            break

        time.sleep(3)

    time.sleep(6)

    L.shell(
        "nvidia-smi "
        "--query-gpu=index,memory.used,memory.total "
        "--format=csv,noheader",
        quiet=False,
        title="종료 후 VRAM"
    )

    L.ok(
        "Forge 종료 완료"
    )
