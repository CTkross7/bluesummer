
# -*- coding: utf-8 -*-

"""
BLUE SUMMER — Forge 통합 관리 모듈 v5.1

Kaggle Python 3.12 / T4 환경 대응.

주요 처리:

1. Forge를 /kaggle/temp/forge 에 설치
2. 모델 저장소는 /kaggle/temp/models 사용
3. NumPy 1.26.4 고정
4. protobuf 3.20.0 고정
5. setuptools 69.5.1 고정
6. scikit-image 호환성 검사
7. OpenCV 검사
8. xformers 불일치 검사
9. wandb / protobuf telemetry 충돌 복구
10. pytorch_lightning 검사
11. OpenAI CLIP의 오래된 setup.py 문제 우회
12. Forge requirements_versions.txt 의 NumPy pin 수정
13. launch.py --exit 의존성 설치
14. READY marker는 모든 검증 성공 후에만 생성
15. Forge API 기동
16. 모델 / 업스케일러 검증
17. 종료 및 VRAM 확인

중요:

OpenAI CLIP의 오래된 GitHub archive 패키지는
최근 setuptools / pip build isolation 환경에서
pkg_resources 문제를 일으킬 수 있다.

따라서 CLIP URL을 직접 선설치하지 않는다.

Forge가 요구하는 open-clip-torch는 requirements를 통해
정상적으로 설치하도록 둔다.

또한 Forge의 launch.py가 오래된 OpenAI CLIP URL을
강제로 설치하려는 경우를 대비해 launch_utils.py의
clip_package 설정을 안전하게 패치한다.
"""

import os
import sys
import time
import signal
import subprocess
import requests


# =====================================================================
# BLUE SUMMER 모듈 경로
# =====================================================================

sys.path.insert(
    0,
    "/kaggle/working/BLUESUMMER"
)

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


# =====================================================================
# 외부 Extension
# =====================================================================

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
    """

    e = os.environ.copy()

    e["PIP_CONSTRAINT"] = CONSTRAINT
    e["PIP_PREFER_BINARY"] = "1"
    e["PIP_ROOT_USER_ACTION"] = "ignore"
    e["PYTHONUNBUFFERED"] = "1"

    return e


def _killpg(proc):
    """
    프로세스 그룹 전체 종료.
    """

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
    BLUE SUMMER 전용 pip constraint.
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
        f.write("protobuf==3.20.0\n")
        f.write("setuptools==69.5.1\n")

    L.ok(
        "pip constraint : "
        "numpy==1.26.4 / protobuf==3.20.0 / setuptools==69.5.1"
    )


# =====================================================================
# Forge requirements 패치
# =====================================================================

def _patch_forge_requirements():
    """
    Forge requirements_versions.txt 호환성 수정.

    기본 Forge에는 현재 다음과 같은 pin이 존재한다.

        setuptools==69.5.1
        numpy==1.26.2
        protobuf==3.20.0

    NumPy만 1.26.4로 맞춘다.
    """

    req = os.path.join(
        FORGE,
        "requirements_versions.txt"
    )

    if not os.path.isfile(req):

        L.warn(
            "Forge requirements_versions.txt 없음"
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

            text = text.replace(
                old,
                new
            )

            with open(
                req,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(text)

            L.ok(
                "Forge requirements: "
                "numpy 1.26.2 -> 1.26.4"
            )

        else:

            L.log(
                "Forge requirements 패치 : 변경 없음"
            )

        numpy_lines = []
        setuptools_lines = []

        for line in text.splitlines():

            stripped = line.strip()

            if stripped.lower().startswith("numpy"):

                numpy_lines.append(
                    stripped
                )

            if stripped.lower().startswith("setuptools"):

                setuptools_lines.append(
                    stripped
                )

        if numpy_lines:

            L.log(
                "Forge NumPy 요구사항 : %s"
                % ", ".join(numpy_lines)
            )

        if setuptools_lines:

            L.log(
                "Forge setuptools 요구사항 : %s"
                % ", ".join(setuptools_lines)
            )

        return True

    except Exception as e:

        L.err(
            "Forge requirements 패치 실패: %s"
            % e
        )

        return False


# =====================================================================
# Forge launch_utils CLIP 패치
# =====================================================================

def _patch_clip_launcher():
    """
    Forge launch_utils.py가 오래된 OpenAI CLIP archive를
    직접 설치하려는 경우를 우회한다.

    문제의 패키지:

    https://github.com/openai/CLIP/archive/
    d50d76daa670286dd6cacf3bcd80b5e4823fc8e1.zip

    이 패키지는 오래된 setup.py를 사용하고,
    최근 pip build isolation에서 pkg_resources 문제가
    발생할 수 있다.

    Forge 자체는 open-clip-torch를 requirements에 사용하므로
    이 오래된 OpenAI CLIP 설치 단계를 건너뛰도록 한다.

    반환:
        True  = 패치 완료 또는 패치 불필요
        False = 패치 실패
    """

    path = os.path.join(
        FORGE,
        "modules",
        "launch_utils.py"
    )

    if not os.path.isfile(path):

        L.warn(
            "launch_utils.py 없음 - CLIP launcher 패치 생략"
        )

        return True

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            text = f.read()

        # -------------------------------------------------------------
        # 이미 패치됨
        # -------------------------------------------------------------

        if "BLUE_SUMMER_CLIP_PATCH" in text:

            L.log(
                "Forge CLIP launcher : 이미 패치됨"
            )

            return True

        # -------------------------------------------------------------
        # clip_package 변수 찾기
        # -------------------------------------------------------------

        if "clip_package =" not in text:

            L.log(
                "Forge에 clip_package 직접 정의 없음 "
                "- 패치 불필요"
            )

            return True

        # -------------------------------------------------------------
        # 실제 clip_package 선언을 찾아 변경
        # -------------------------------------------------------------

        lines = text.splitlines()

        changed = False

        for i, line in enumerate(lines):

            stripped = line.strip()

            if (
                stripped.startswith("clip_package")
                and "=" in stripped
            ):

                # 기존 값 보존 여부와 관계없이
                # Forge에서 오래된 OpenAI CLIP archive를
                # 직접 설치하지 않도록 한다.

                indent = line[
                    :len(line) - len(line.lstrip())
                ]

                lines[i] = (
                    indent
                    + "# BLUE_SUMMER_CLIP_PATCH\n"
                    + indent
                    + "clip_package = \"open-clip-torch==2.20.0\""
                )

                changed = True

                break

        if not changed:

            L.log(
                "clip_package 자동 패치 대상 없음"
            )

            return True

        new_text = "\n".join(lines)

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(new_text)

        L.ok(
            "Forge CLIP launcher 패치 완료 "
            "-> open-clip-torch 사용"
        )

        return True

    except Exception as e:

        L.err(
            "CLIP launcher 패치 실패: %s"
            % e
        )

        return False


# =====================================================================
# Forge clone
# =====================================================================

def clone():
    """
    Forge 및 ADetailer clone.
    """

    os.makedirs(
        "/kaggle/temp",
        exist_ok=True
    )

    # -----------------------------------------------------------------
    # Forge
    # -----------------------------------------------------------------

    if not os.path.isdir(
        os.path.join(
            FORGE,
            ".git"
        )
    ):

        L.log(
            "Forge clone ..."
        )

        rc, out = L.shell(
            "git clone --depth 1 "
            "https://github.com/lllyasviel/"
            "stable-diffusion-webui-forge "
            "%s" % FORGE
        )

        if rc != 0:

            L.err(
                "Forge clone 실패"
            )

            return False

    else:

        L.log(
            "Forge 이미 존재"
        )

    # -----------------------------------------------------------------
    # Extensions
    # -----------------------------------------------------------------

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
                    "확장 clone 실패 : %s"
                    % name
                )

        else:

            L.log(
                "확장 존재 : " + name
            )

    # -----------------------------------------------------------------
    # 모델 디렉터리
    # -----------------------------------------------------------------

    for d in [
        "models/Stable-diffusion",
        "models/VAE",
        "models/ESRGAN",
        "models/Lora",
        "models/adetailer",
        "outputs",
    ]:

        os.makedirs(
            os.path.join(
                FORGE,
                d
            ),
            exist_ok=True
        )

    return True


# =====================================================================
# 사전 pin
# =====================================================================

def pre_pin():
    """
    Forge requirements 설치 전에 핵심 패키지를 고정한다.

    OpenAI CLIP URL은 여기서 설치하지 않는다.
    """

    L.log(
        "호환 버전 선점 설치 "
        "(setuptools / numpy / mediapipe / protobuf / CLIP)"
    )

    # -----------------------------------------------------------------
    # constraint
    # -----------------------------------------------------------------

    _write_constraint()

    # -----------------------------------------------------------------
    # Forge requirements
    # -----------------------------------------------------------------

    _patch_forge_requirements()

    # -----------------------------------------------------------------
    # CLIP launcher
    # -----------------------------------------------------------------

    _patch_clip_launcher()

    # -----------------------------------------------------------------
    # setuptools
    # -----------------------------------------------------------------

    L.log(
        "CLIP 호환용 setuptools 69.5.1 준비"
    )

    rc, out = L.shell(
        'pip install -q '
        '--force-reinstall '
        '"setuptools==69.5.1"',
        quiet=True,
        title="setuptools 69.5.1"
    )

    if rc != 0:

        L.err(
            "setuptools 69.5.1 설치 실패"
        )

        return False

    # -----------------------------------------------------------------
    # 핵심 호환 패키지
    # -----------------------------------------------------------------

    rc, out = L.shell(
        'pip install -q '
        '"numpy==1.26.4" '
        '"mediapipe<1.0" '
        '"protobuf==3.20.0"',
        quiet=True,
        title="numpy / mediapipe / protobuf"
    )

    if rc != 0:

        L.err(
            "핵심 호환 패키지 설치 실패"
        )

        return False

    # -----------------------------------------------------------------
    # ADetailer
    # -----------------------------------------------------------------

    rc, out = L.shell(
        'pip install -q '
        '"ultralytics>=8.2,<9" '
        '"py-cpuinfo" '
        '"protobuf==3.20.0"',
        quiet=True,
        title="ADetailer 런타임 의존성"
    )

    if rc != 0:

        L.warn(
            "ADetailer 런타임 의존성 일부 설치 실패"
        )

    return True


# =====================================================================
# Doctor
# =====================================================================

def doctor(verbose=True):
    """
    주요 의존성 검사 및 복구.
    """

    fixed = []

    # =================================================================
    # NumPy
    # =================================================================

    rc, out = L.shell(
        'python -c '
        '"import numpy;'
        'print(\'NPV=\'+numpy.__version__)"',
        quiet=True
    )

    ver = ""

    for line in out.splitlines():

        if line.startswith("NPV="):

            ver = line[4:].strip()

            break

    if ver != "1.26.4":

        L.warn(
            "numpy %s 감지 -> 1.26.4로 고정"
            % (ver or "?")
        )

        L.shell(
            'pip install -q '
            '--force-reinstall '
            '"numpy==1.26.4"',
            title="numpy 복구"
        )

        fixed.append("numpy")

    elif verbose:

        L.log(
            "numpy 1.26.4 : 정상"
        )

    # =================================================================
    # scikit-image
    # =================================================================

    rc, out = L.shell(
        'python -c '
        '"from skimage import exposure;'
        'print(\'SKOK\')"',
        quiet=True
    )

    if "SKOK" not in out:

        L.warn(
            "scikit-image 임포트 실패 -> "
            "0.24.0 재설치"
        )

        L.shell(
            'pip install -q '
            '"scikit-image==0.24.0"',
            title="scikit-image 복구"
        )

        fixed.append(
            "scikit-image"
        )

    elif verbose:

        L.log(
            "scikit-image : 정상"
        )

    # =================================================================
    # protobuf
    # =================================================================

    rc, out = L.shell(
        'python -c '
        '"import google.protobuf;'
        'print(\'PB=\'+google.protobuf.__version__)"',
        quiet=True
    )

    pbver = ""

    for line in out.splitlines():

        if line.startswith("PB="):

            pbver = line[3:].strip()

            break

    if pbver != "3.20.0":

        L.warn(
            "protobuf %s 감지 -> 3.20.0로 고정"
            % (pbver or "?")
        )

        L.shell(
            'pip install -q '
            '--force-reinstall '
            '"protobuf==3.20.0"',
            title="protobuf 복구"
        )

        fixed.append(
            "protobuf"
        )

    elif verbose:

        L.log(
            "protobuf : 3.20.0"
        )

    # =================================================================
    # setuptools / pkg_resources
    # =================================================================

    rc, out = L.shell(
        'python -c '
        '"import setuptools;'
        'print(\'SETUP=\'+setuptools.__version__);'
        'import pkg_resources;'
        'print(\'PKGRES=OK\')"',
        quiet=True
    )

    if (
        "SETUP=69.5.1" not in out
        or "PKGRES=OK" not in out
    ):

        L.warn(
            "setuptools/pkg_resources 불완전 -> "
            "69.5.1 복구"
        )

        L.shell(
            'pip install -q '
            '--force-reinstall '
            '"setuptools==69.5.1"',
            title="setuptools 복구"
        )

        fixed.append(
            "setuptools"
        )

    elif verbose:

        L.log(
            "setuptools 69.5.1 / pkg_resources : 정상"
        )

    # =================================================================
    # wandb
    # =================================================================

    rc, out = L.shell(
        'python -c '
        '"import wandb;'
        'print(\'WANDB=\'+wandb.__version__)"',
        quiet=True
    )

    if rc != 0:

        L.warn(
            "wandb import 실패 -> 0.17.9 재설치"
        )

        L.shell(
            'pip install -q '
            '--force-reinstall '
            '"wandb==0.17.9"',
            title="wandb 복구"
        )

        fixed.append(
            "wandb"
        )

    else:

        wbver = ""

        for line in out.splitlines():

            if line.startswith("WANDB="):

                wbver = line[6:].strip()

                break

        if wbver != "0.17.9":

            L.warn(
                "wandb %s -> 0.17.9 고정"
                % (wbver or "?")
            )

            L.shell(
                'pip install -q '
                '--force-reinstall '
                '"wandb==0.17.9"',
                title="wandb 고정"
            )

            fixed.append(
                "wandb"
            )

        elif verbose:

            L.log(
                "wandb : 정상 0.17.9"
            )

    # =================================================================
    # pytorch_lightning
    # =================================================================

    rc, out = L.shell(
        'python -c '
        '"import pytorch_lightning as p;'
        'print(\'PL=\'+p.__version__)"',
        quiet=True
    )

    if rc != 0:

        L.warn(
            "pytorch_lightning import 실패"
        )

        L.shell(
            'pip install -q '
            '"pytorch_lightning==1.9.4"',
            title="pytorch_lightning 복구"
        )

        fixed.append(
            "pytorch_lightning"
        )

    elif verbose:

        plver = ""

        for line in out.splitlines():

            if line.startswith("PL="):

                plver = line[3:].strip()

                break

        L.log(
            "pytorch_lightning : 정상 %s"
            % (plver or "?")
        )

    # =================================================================
    # xformers
    # =================================================================

    rc, out = L.shell(
        'python -c '
        '"import xformers,'
        'xformers.ops;'
        'print(\'XOK\')"',
        quiet=True
    )

    if "XOK" not in out:

        rc2, o2 = L.shell(
            "pip show xformers",
            quiet=True
        )

        if "Name: xformers" in o2:

            L.warn(
                "xformers import 실패 -> 제거"
            )

            L.shell(
                "pip uninstall -q -y xformers",
                title="xformers 제거"
            )

            fixed.append(
                "xformers"
            )

        elif verbose:

            L.log(
                "xformers : 미설치 (SDPA 사용)"
            )

    elif verbose:

        L.log(
            "xformers : 정상"
        )

    # =================================================================
    # OpenCV
    # =================================================================

    rc, out = L.shell(
        'python -c '
        '"import cv2;'
        'print(\'CVOK\')"',
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

        fixed.append(
            "opencv"
        )

    elif verbose:

        L.log(
            "opencv : 정상"
        )

    # =================================================================
    # OpenAI CLIP 확인
    # =================================================================

    rc, out = L.shell(
        'python -c '
        '"import clip;'
        'print(\'CLIPOK\')"',
        quiet=True
    )

    if "CLIPOK" in out:

        if verbose:

            L.log(
                "OpenAI CLIP : 설치됨"
            )

    else:

        L.log(
            "OpenAI CLIP : 미설치 "
            "(Forge는 open-clip-torch 경로 사용)"
        )

    # =================================================================
    # 결과
    # =================================================================

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

def install_env(
    force=False,
    timeout=2700
):
    """
    Forge 의존성을 설치한다.

    성공하지 않으면 READY marker를 만들지 않는다.
    """

    # -----------------------------------------------------------------
    # 기존 marker
    # -----------------------------------------------------------------

    if (
        os.path.exists(MARKER)
        and not force
    ):

        L.log(
            "Forge 의존성 준비 완료 표식 발견 "
            "- 설치 단계 생략"
        )

        _write_constraint()
        _patch_forge_requirements()
        _patch_clip_launcher()

        doctor()

        return True

    # -----------------------------------------------------------------
    # Forge 준비
    # -----------------------------------------------------------------

    if not clone():

        return False

    if not pre_pin():

        L.err(
            "Forge 사전 호환성 준비 실패"
        )

        return False

    # -----------------------------------------------------------------
    # marker 제거
    # -----------------------------------------------------------------

    if os.path.exists(MARKER):

        try:
            os.remove(MARKER)
        except Exception:
            pass

    # -----------------------------------------------------------------
    # dependency install
    # -----------------------------------------------------------------

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

        if rc is not None:

            elapsed = (
                time.time() - t0
            ) / 60

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
                    % (
                        rc,
                        elapsed
                    )
                )

            break

        if (
            time.time() - t0
            > timeout
        ):

            L.err(
                "의존성 설치 타임아웃"
            )

            _killpg(proc)

            rc = 124

            break

        time.sleep(5)

    f.close()

    # -----------------------------------------------------------------
    # 로그
    # -----------------------------------------------------------------

    L.tail_file(
        LOGFILE,
        50,
        title="forge.log 끝부분"
    )

    # -----------------------------------------------------------------
    # 실패
    # -----------------------------------------------------------------

    if rc != 0:

        L.err(
            "Forge 의존성 설치 실패."
        )

        L.err(
            "READY marker를 생성하지 않습니다."
        )

        doctor()

        return False

    # -----------------------------------------------------------------
    # doctor
    # -----------------------------------------------------------------

    doctor()

    # -----------------------------------------------------------------
    # NumPy 최종 검증
    # -----------------------------------------------------------------

    rc_np, out_np = L.shell(
        'python -c '
        '"import numpy;'
        'print(\'FINALNP=\'+numpy.__version__)"',
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
            % (
                final_np or "?"
            )
        )

        return False

    # -----------------------------------------------------------------
    # protobuf 최종 검증
    # -----------------------------------------------------------------

    rc_pb, out_pb = L.shell(
        'python -c '
        '"import google.protobuf;'
        'print(\'FINALPB=\'+'
        'google.protobuf.__version__)"',
        quiet=True
    )

    final_pb = ""

    for line in out_pb.splitlines():

        if line.startswith("FINALPB="):

            final_pb = line.split(
                "=",
                1
            )[1].strip()

            break

    if final_pb != "3.20.0":

        L.err(
            "protobuf 최종 검증 실패 : %s"
            % (
                final_pb or "?"
            )
        )

        return False

    # -----------------------------------------------------------------
    # requirements 검증
    # -----------------------------------------------------------------

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
                "numpy==1.26.2가 남아 있습니다."
            )

            return False

    # -----------------------------------------------------------------
    # CLIP launcher 검증
    # -----------------------------------------------------------------

    _patch_clip_launcher()

    # -----------------------------------------------------------------
    # READY marker
    # -----------------------------------------------------------------

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
    Forge API 응답 여부.
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

def launch(
    wait=900,
    attempts=2
):
    """
    Forge API 기동.
    """

    # -----------------------------------------------------------------
    # 이미 기동
    # -----------------------------------------------------------------

    if alive():

        L.ok(
            "Forge 이미 기동 중"
        )

        return True

    # -----------------------------------------------------------------
    # dependency
    # -----------------------------------------------------------------

    if not install_env():

        L.err(
            "Forge 의존성 설치 실패"
        )

        return False

    # -----------------------------------------------------------------
    # launch
    # -----------------------------------------------------------------

    for attempt in range(
        1,
        attempts + 1
    ):

        L.banner(
            "Forge API 기동 시도 %d/%d"
            % (
                attempt,
                attempts
            )
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

        while (
            time.time() - t0
            < wait
        ):

            # ---------------------------------------------------------
            # API
            # ---------------------------------------------------------

            if alive(5):

                L.ok(
                    "API 응답 (%.0f초)"
                    % (
                        time.time() - t0
                    )
                )

                f.close()

                return True

            # ---------------------------------------------------------
            # process death
            # ---------------------------------------------------------

            if proc.poll() is not None:

                L.err(
                    "기동 프로세스가 죽었습니다 "
                    "(rc=%s)"
                    % proc.returncode
                )

                break

            # ---------------------------------------------------------
            # progress
            # ---------------------------------------------------------

            if (
                time.time() - last
                > 60
            ):

                last = time.time()

                L.log(
                    "   기동 대기 %.0f초 ..."
                    % (
                        time.time() - t0
                    )
                )

            time.sleep(6)

        f.close()

        # -------------------------------------------------------------
        # failure log
        # -------------------------------------------------------------

        txt = L.tail_file(
            LOGFILE,
            60,
            title="forge.log 끝부분"
        )

        low = txt.lower()

        # -------------------------------------------------------------
        # dependency detection
        # -------------------------------------------------------------

        if (
            "resolutionimpossible"
            in low
            or "numpy"
            in low
            or "skimage"
            in low
            or "scikit-image"
            in low
            or "xformers"
            in low
            or "wandb"
            in low
            or "protobuf"
            in low
            or "clip"
            in low
            or "pkg_resources"
            in low
        ):

            L.warn(
                "의존성 문제 감지 -> doctor"
            )

            doctor()

        else:

            L.warn(
                "원인 불명 -> doctor"
            )

            doctor(
                verbose=False
            )

        _killpg(proc)

        time.sleep(5)

    L.err(
        "Forge 기동 실패 - %s 확인"
        % LOGFILE
    )

    return False


# =====================================================================
# 모델
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


# =====================================================================
# 업스케일러
# =====================================================================

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
# checkpoint
# =====================================================================

def resolve_checkpoint(
    want="novaanimexl_ilv190"
):
    """
    원하는 체크포인트 검색.
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
                .replace(
                    " ",
                    ""
                )
            )

            if (
                want.lower()
                in normalized
            ):

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
    Forge API 기본 옵션.
    """

    opts = {

        "sd_model_checkpoint":
            ckpt_title,

        "sd_vae":
            vae,

        "CLIP_stop_at_last_layers":
            clip_skip,

        "samples_save":
            False,

        "grid_save":
            False,

        "live_previews_enable":
            False,

        "show_progress_every_n_steps":
            0,

        "upscaler_for_img2img":
            "4x-UltraSharp",
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

        return (
            r.status_code == 200
        )

    except Exception as e:

        L.warn(
            "옵션 적용 실패: %s"
            % e
        )

        return False


# =====================================================================
# 검증
# =====================================================================

def verify(
    need_upscalers=(
        "4x-UltraSharp",
        "4x-AnimeSharp",
    )
):

    ms = [
        m.get(
            "model_name",
            ""
        )
        for m in models()
    ]

    us = upscalers()

    L.log(
        "체크포인트 : %s"
        % ms
    )

    L.log(
        "업스케일러 : %s"
        % us
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

def ensure(
    clip_skip=2
):
    """
    어떤 상태에서 호출해도
    사용 가능한 Forge를 보장.
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
    Forge 종료.
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
        "pkill -f 'launch.py' "
        "> /dev/null 2>&1",
        shell=True
    )

    subprocess.run(
        "pkill -f 'webui.py' "
        "> /dev/null 2>&1",
        shell=True
    )

    t0 = time.time()

    while (
        time.time() - t0
        < wait
    ):

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
