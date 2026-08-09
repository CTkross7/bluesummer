
# -*- coding: utf-8 -*-

"""
BLUE SUMMER - Forge 통합 관리 모듈 v6

Kaggle Python 3.12 + T4 환경용.

v6 주요 변경사항
------------------------------------------------------------
1. protobuf 전역 downgrade 완전 제거
   - protobuf==3.20.0 사용 금지
   - Kaggle의 TensorFlow / google-cloud / transformers 환경 보호
   - google.protobuf.runtime_version import 가능 여부 검사

2. NumPy 고정
   - numpy==1.26.4
   - Forge의 numpy==1.26.2 pin도 1.26.4로 보정

3. setuptools
   - setuptools==69.5.1
   - 오래된 CLIP setup.py / pkg_resources 호환성 확보

4. OpenAI CLIP
   - Forge launcher가 GitHub의 오래된 CLIP setup.py를
     직접 설치하지 않도록 패치
   - open-clip-torch 경로 사용

5. wandb
   - wandb==0.17.9 유지 가능
   - protobuf를 낮추는 방식으로 복구하지 않음
   - import 실패 시 --no-deps 재설치

6. xformers
   - 현재 torch와 호환되지 않으면 제거
   - Forge의 SDPA 사용

7. dependency marker
   - v5 marker를 신뢰하지 않음
   - v6 전용 marker 사용
   - launch.py --exit가 성공한 경우에만 marker 생성

8. API
   - Forge API 기동
   - checkpoint / upscaler 확인
   - 기본 옵션 적용
   - 종료 기능 제공

------------------------------------------------------------
"""

import os
import sys
import time
import signal
import subprocess
import re

import requests


# =====================================================================
# BLUE SUMMER 경로
# =====================================================================

BASE = "/kaggle/working/BLUESUMMER"

sys.path.insert(0, BASE)

import bs_log as L


# =====================================================================
# 경로 / 상수
# =====================================================================

FORGE = "/kaggle/temp/forge"
STORE = "/kaggle/temp/models"

LOGFILE = "/kaggle/temp/forge.log"

# v5와 다른 marker를 사용한다.
MARKER = "/kaggle/temp/.forge_env_ready_v6"

CONSTRAINT = "/kaggle/temp/pip-constraints-v6.txt"

PORT = 7860

API = "http://127.0.0.1:%d" % PORT

FORGE_VERSION_MARKER = "BLUE_SUMMER_FORGE_V6"


# =====================================================================
# 외부 Extension
# =====================================================================

EXT_REPOS = [
    (
        "adetailer",
        "https://github.com/Bing-su/adetailer",
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
# 기본 유틸리티
# =====================================================================

def args_str():
    return " ".join(BASE_ARGS)


def _env():
    """
    Forge / pip 실행 환경.

    중요:
    PIP_CONSTRAINT에는 NumPy만 고정한다.
    protobuf는 절대로 여기서 downgrade하지 않는다.
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
            signal.SIGTERM,
        )
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


def _safe_remove(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# =====================================================================
# pip constraint
# =====================================================================

def _write_constraint():
    """
    v6 pip constraint.

    protobuf는 절대로 고정하지 않는다.
    """

    os.makedirs(
        os.path.dirname(CONSTRAINT),
        exist_ok=True,
    )

    with open(
        CONSTRAINT,
        "w",
        encoding="utf-8",
    ) as f:

        f.write(
            "numpy==1.26.4\n"
        )

    L.ok(
        "pip constraint : numpy==1.26.4 "
        "(protobuf 전역 고정 없음)"
    )


# =====================================================================
# Forge requirements 수정
# =====================================================================

def _patch_forge_requirements():
    """
    Forge requirements_versions.txt의 오래된 NumPy pin을 수정한다.

    numpy==1.26.2
        ->
    numpy==1.26.4
    """

    req = os.path.join(
        FORGE,
        "requirements_versions.txt",
    )

    if not os.path.isfile(req):

        L.warn(
            "Forge requirements_versions.txt 없음 : %s"
            % req
        )

        return False

    try:

        with open(
            req,
            "r",
            encoding="utf-8",
        ) as f:

            text = f.read()

        old = "numpy==1.26.2"
        new = "numpy==1.26.4"

        if old in text:

            text = text.replace(
                old,
                new,
            )

            with open(
                req,
                "w",
                encoding="utf-8",
            ) as f:

                f.write(text)

            L.ok(
                "Forge requirements: "
                "numpy 1.26.2 -> 1.26.4"
            )

        else:

            L.log(
                "Forge requirements 패치 : 변경 없음",
                "INFO",
            )

        numpy_lines = []

        for line in text.splitlines():

            stripped = line.strip()

            if stripped.lower().startswith("numpy"):

                numpy_lines.append(
                    stripped
                )

        if numpy_lines:

            L.log(
                "Forge NumPy 요구사항 : %s"
                % ", ".join(numpy_lines),
                "INFO",
            )

        setuptools_lines = []

        for line in text.splitlines():

            stripped = line.strip()

            if stripped.lower().startswith(
                "setuptools"
            ):

                setuptools_lines.append(
                    stripped
                )

        if setuptools_lines:

            L.log(
                "Forge setuptools 요구사항 : %s"
                % ", ".join(setuptools_lines),
                "INFO",
            )

        return True

    except Exception as e:

        L.err(
            "Forge requirements 패치 실패 : %s"
            % e
        )

        return False


# =====================================================================
# Forge launcher CLIP 패치
# =====================================================================

def _patch_clip_launcher():
    """
    Forge launcher가 오래된 OpenAI CLIP GitHub ZIP을
    직접 설치하지 않도록 패치한다.

    기존:
        https://github.com/openai/CLIP/archive/....

    변경:
        open-clip-torch

    주의:
    이미 패치된 경우 다시 변경하지 않는다.
    """

    path = os.path.join(
        FORGE,
        "modules",
        "launch_utils.py",
    )

    if not os.path.isfile(path):

        L.warn(
            "Forge launch_utils.py 없음 : %s"
            % path
        )

        return False

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as f:

            text = f.read()

        original = text

        # ---------------------------------------------------------
        # 1. clip_package 문자열을 open-clip-torch로 변경
        # ---------------------------------------------------------

        replacements = [
            (
                'clip_package = "https://github.com/openai/CLIP/archive/'
                ,
                'clip_package = "open-clip-torch"'
            ),
        ]

        changed = False

        for old, new in replacements:

            if old in text:

                text = text.replace(
                    old,
                    new,
                )

                changed = True

        # ---------------------------------------------------------
        # 2. URL이 변수에 들어가는 다른 형태 대응
        # ---------------------------------------------------------

        if "github.com/openai/CLIP/archive" in text:

            # clip_package = "...CLIP/archive/..."
            pattern = (
                r'(^\s*clip_package\s*=\s*)'
                r'["\']https://github\.com/openai/CLIP/archive/[^"\']+'
                r'["\']'
            )

            text2, count = re.subn(
                pattern,
                r'\1"open-clip-torch"',
                text,
                flags=re.MULTILINE,
            )

            if count > 0:

                text = text2
                changed = True

        # ---------------------------------------------------------
        # 3. 실제 변경 저장
        # ---------------------------------------------------------

        if text != original:

            with open(
                path,
                "w",
                encoding="utf-8",
            ) as f:

                f.write(text)

            L.ok(
                "Forge CLIP launcher 패치 완료 "
                "-> open-clip-torch 사용"
            )

            return True

        # 이미 open-clip-torch가 존재하는 경우
        if "open-clip-torch" in text:

            L.log(
                "Forge CLIP launcher : 이미 패치됨",
                "INFO",
            )

            return True

        L.warn(
            "Forge CLIP launcher 패치 대상을 찾지 못했습니다."
        )

        return False

    except Exception as e:

        L.err(
            "Forge CLIP launcher 패치 실패 : %s"
            % e
        )

        return False


# =====================================================================
# Forge clone
# =====================================================================

def clone():
    """
    Forge 및 ADetailer clone.

    모든 임시 파일은 /kaggle/temp에 둔다.
    """

    os.makedirs(
        "/kaggle/temp",
        exist_ok=True,
    )

    # -------------------------------------------------------------
    # Forge
    # -------------------------------------------------------------

    if not os.path.isdir(
        os.path.join(
            FORGE,
            ".git",
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

    # -------------------------------------------------------------
    # Extensions
    # -------------------------------------------------------------

    ext = os.path.join(
        FORGE,
        "extensions",
    )

    os.makedirs(
        ext,
        exist_ok=True,
    )

    for name, url in EXT_REPOS:

        d = os.path.join(
            ext,
            name,
        )

        if not os.path.isdir(d):

            L.shell(
                "git clone --depth 1 %s %s"
                % (
                    url,
                    d,
                ),
                title="확장 설치 " + name,
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
            os.path.join(
                FORGE,
                d,
            ),
            exist_ok=True,
        )

    return True


# =====================================================================
# 사전 호환성 설치
# =====================================================================

def pre_pin():
    """
    Forge requirements 설치 전에 최소 호환성을 확보한다.

    중요:
    protobuf는 설치하지 않는다.

    Kaggle의 TensorFlow / google-cloud / transformers 등이
    사용하는 protobuf를 건드리지 않는 것이 v6의 핵심이다.
    """

    L.log(
        "호환 버전 선점 설치 "
        "(setuptools / numpy / mediapipe / CLIP)"
    )

    # -------------------------------------------------------------
    # constraint
    # -------------------------------------------------------------

    _write_constraint()

    # -------------------------------------------------------------
    # Forge requirements
    # -------------------------------------------------------------

    _patch_forge_requirements()

    # -------------------------------------------------------------
    # CLIP launcher 패치
    # -------------------------------------------------------------

    if not _patch_clip_launcher():

        L.warn(
            "CLIP launcher 패치가 확인되지 않았습니다."
        )

    # -------------------------------------------------------------
    # setuptools
    # -------------------------------------------------------------

    L.log(
        "CLIP 호환용 setuptools 69.5.1 준비"
    )

    rc, out = L.shell(
        'pip install -q '
        '"setuptools==69.5.1"',
        quiet=True,
        title="setuptools 69.5.1",
        env=_env(),
    )

    if rc != 0:

        L.err(
            "setuptools 설치 실패"
        )

        return False

    # -------------------------------------------------------------
    # NumPy / MediaPipe
    # -------------------------------------------------------------

    rc, out = L.shell(
        'pip install -q '
        '"numpy==1.26.4" '
        '"mediapipe<1.0"',
        quiet=True,
        title="numpy / mediapipe",
        env=_env(),
    )

    if rc != 0:

        L.err(
            "numpy / mediapipe 설치 실패"
        )

        return False

    # -------------------------------------------------------------
    # ADetailer runtime
    #
    # protobuf는 여기에도 넣지 않는다.
    # -------------------------------------------------------------

    rc, out = L.shell(
        'pip install -q '
        '"ultralytics>=8.2,<9" '
        '"py-cpuinfo"',
        quiet=True,
        title="ADetailer 런타임 의존성",
        env=_env(),
    )

    if rc != 0:

        L.warn(
            "ADetailer 런타임 의존성 설치 일부 실패"
        )

    return True


# =====================================================================
# protobuf 검사
# =====================================================================

def _check_protobuf(verbose=True):
    """
    protobuf가 Kaggle 환경에서 정상적으로 동작하는지 확인한다.

    v6에서는 protobuf 버전을 강제로 낮추지 않는다.

    특히:
        from google.protobuf import runtime_version

    가 성공해야 TensorFlow protobuf generated module과
    transformers 계열 import가 정상적으로 동작할 가능성이 높다.
    """

    cmd = (
        'python -c "'
        'import google.protobuf as p; '
        'print(\'PBV=\'+p.__version__); '
        'from google.protobuf import runtime_version; '
        'print(\'PBRT=OK\')"'
    )

    rc, out = L.shell(
        cmd,
        quiet=True,
    )

    if "PBRT=OK" in out:

        if verbose:

            version = "?"

            for line in out.splitlines():

                if line.startswith("PBV="):

                    version = line[4:].strip()
                    break

            L.log(
                "protobuf : %s / runtime_version 정상"
                % version
            )

        return True

    L.err(
        "protobuf runtime_version import 실패"
    )

    return False


# =====================================================================
# wandb 검사
# =====================================================================

def _check_wandb(verbose=True):
    """
    wandb import 확인.

    실패하더라도 protobuf를 downgrade하지 않는다.

    wandb 0.17.9를 --no-deps로 재설치하여
    Kaggle의 protobuf / google-cloud 의존성을 건드리지 않는다.
    """

    rc, out = L.shell(
        'python -c '
        '"import wandb;print(\'WBOK=\'+wandb.__version__)"',
        quiet=True,
    )

    if "WBOK=" in out:

        if verbose:

            version = "?"

            for line in out.splitlines():

                if line.startswith("WBOK="):

                    version = line[5:].strip()
                    break

            L.log(
                "wandb : 정상 %s" % version
            )

        return True

    L.warn(
        "wandb import 실패 -> 0.17.9 --no-deps 재설치"
    )

    rc, out = L.shell(
        'pip install -q --force-reinstall --no-deps '
        '"wandb==0.17.9"',
        title="wandb 복구",
        env=_env(),
    )

    if rc != 0:

        L.warn(
            "wandb 재설치 실패"
        )

        return False

    rc, out = L.shell(
        'python -c '
        '"import wandb;print(\'WBOK=\'+wandb.__version__)"',
        quiet=True,
    )

    if "WBOK=" in out:

        if verbose:

            version = "?"

            for line in out.splitlines():

                if line.startswith("WBOK="):

                    version = line[5:].strip()
                    break

            L.ok(
                "wandb : 복구 완료 %s" % version
            )

        return True

    L.warn(
        "wandb : 재설치 후에도 import 실패"
    )

    return False


# =====================================================================
# Doctor
# =====================================================================

def doctor(verbose=True):
    """
    Forge / Kaggle 핵심 Python 의존성을 검사한다.

    검사:
        NumPy
        scikit-image
        protobuf runtime_version
        setuptools / pkg_resources
        wandb
        pytorch_lightning
        xformers
        OpenCV
        OpenAI CLIP
    """

    fixed = []

    # =============================================================
    # NumPy
    # =============================================================

    rc, out = L.shell(
        'python -c '
        '"import numpy;print(\'NPV=\'+numpy.__version__)"',
        quiet=True,
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

        rc, out = L.shell(
            'pip install -q --force-reinstall '
            '"numpy==1.26.4"',
            title="numpy 복구",
            env=_env(),
        )

        if rc == 0:

            fixed.append(
                "numpy"
            )

        else:

            L.err(
                "numpy 복구 실패"
            )

    elif verbose:

        L.log(
            "numpy %s : 정상"
            % ver
        )

    # =============================================================
    # scikit-image
    # =============================================================

    rc, out = L.shell(
        'python -c '
        '"from skimage import exposure;print(\'SKOK\')"',
        quiet=True,
    )

    if "SKOK" not in out:

        L.warn(
            "scikit-image import 실패 -> 0.24.0 재설치"
        )

        rc, out = L.shell(
            'pip install -q '
            '"scikit-image==0.24.0"',
            title="scikit-image 복구",
            env=_env(),
        )

        if rc == 0:

            fixed.append(
                "scikit-image"
            )

    elif verbose:

        L.log(
            "scikit-image : 정상"
        )

    # =============================================================
    # protobuf
    # =============================================================

    if not _check_protobuf(
        verbose=verbose
    ):

        L.err(
            "protobuf는 자동 downgrade하지 않습니다. "
            "현재 Kaggle 환경을 유지합니다."
        )

    # =============================================================
    # setuptools / pkg_resources
    # =============================================================

    rc, out = L.shell(
        'python -c '
        '"import setuptools;'
        'import pkg_resources;'
        'print(\'SETOK=\'+setuptools.__version__)"',
        quiet=True,
    )

    if "SETOK=" not in out:

        L.warn(
            "setuptools/pkg_resources import 실패 "
            "-> 69.5.1 재설치"
        )

        rc, out = L.shell(
            'pip install -q --force-reinstall '
            '"setuptools==69.5.1"',
            title="setuptools 복구",
            env=_env(),
        )

        if rc == 0:

            fixed.append(
                "setuptools"
            )

    elif verbose:

        version = "?"

        for line in out.splitlines():

            if line.startswith("SETOK="):

                version = line[6:].strip()
                break

        L.log(
            "setuptools %s / pkg_resources : 정상"
            % version
        )

    # =============================================================
    # wandb
    # =============================================================

    if not _check_wandb(
        verbose=verbose
    ):

        L.warn(
            "wandb : 현재 환경에서 import 불가"
        )

    # =============================================================
    # pytorch_lightning
    # =============================================================

    rc, out = L.shell(
        'python -c '
        '"import pytorch_lightning as p;'
        'print(\'PLOK=\'+p.__version__)"',
        quiet=True,
    )

    if "PLOK=" in out:

        if verbose:

            version = "?"

            for line in out.splitlines():

                if line.startswith("PLOK="):

                    version = line[5:].strip()
                    break

            L.log(
                "pytorch_lightning : 정상 %s"
                % version
            )

    else:

        L.warn(
            "pytorch_lightning import 실패"
        )

    # =============================================================
    # xformers
    # =============================================================

    rc, out = L.shell(
        'python -c '
        '"import xformers,xformers.ops;'
        'print(\'XOK\')"',
        quiet=True,
    )

    if "XOK" in out:

        if verbose:

            L.log(
                "xformers : 정상"
            )

    else:

        rc2, o2 = L.shell(
            "pip show xformers",
            quiet=True,
        )

        if "Name: xformers" in o2:

            L.warn(
                "xformers import 실패 -> 제거 "
                "(Forge SDPA 사용)"
            )

            rc3, o3 = L.shell(
                "pip uninstall -q -y xformers",
                title="xformers 제거",
                env=_env(),
            )

            if rc3 == 0:

                fixed.append(
                    "xformers"
                )

        elif verbose:

            L.log(
                "xformers : 미설치 (SDPA 사용)"
            )

    # =============================================================
    # OpenCV
    # =============================================================

    rc, out = L.shell(
        'python -c '
        '"import cv2;print(\'CVOK\')"',
        quiet=True,
    )

    if "CVOK" not in out:

        L.warn(
            "OpenCV import 실패 -> 복구"
        )

        rc, out = L.shell(
            "pip install -q opencv-python-headless",
            title="opencv 복구",
            env=_env(),
        )

        if rc == 0:

            fixed.append(
                "opencv"
            )

    elif verbose:

        L.log(
            "opencv : 정상"
        )

    # =============================================================
    # OpenAI CLIP
    # =============================================================

    rc, out = L.shell(
        'python -c '
        '"import clip;print(\'CLIPOK\')"',
        quiet=True,
    )

    if "CLIPOK" in out:

        if verbose:

            L.log(
                "OpenAI CLIP : 정상"
            )

    else:

        if verbose:

            L.log(
                "OpenAI CLIP : 미설치 "
                "(Forge는 open-clip-torch 경로 사용)"
            )

    # =============================================================
    # open_clip
    # =============================================================

    rc, out = L.shell(
        'python -c '
        '"import open_clip;print(\'OPENCLIPOK\')"',
        quiet=True,
    )

    if "OPENCLIPOK" in out:

        if verbose:

            L.log(
                "open-clip-torch : 정상"
            )

    else:

        L.warn(
            "open-clip-torch : 미설치"
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
# v6 환경 marker
# =====================================================================

def _marker_valid():
    """
    기존 marker가 v6 marker인지 확인한다.
    """

    if not os.path.isfile(MARKER):

        return False

    try:

        with open(
            MARKER,
            "r",
            encoding="utf-8",
        ) as f:

            text = f.read()

        return (
            FORGE_VERSION_MARKER
            in text
        )

    except Exception:

        return False


def _write_marker():
    """
    dependency 설치 성공 후에만 marker 생성.
    """

    with open(
        MARKER,
        "w",
        encoding="utf-8",
    ) as f:

        f.write(
            FORGE_VERSION_MARKER
            + "\n"
        )

        f.write(
            time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )


# =====================================================================
# Forge 의존성 설치
# =====================================================================

def install_env(
    force=False,
    timeout=2700,
):
    """
    Forge 의존성을 설치한다.

    launch.py --exit가 성공해야 marker를 생성한다.
    """

    # -------------------------------------------------------------
    # 기존 v6 marker
    # -------------------------------------------------------------

    if (
        _marker_valid()
        and not force
    ):

        L.log(
            "Forge v6 의존성 준비 완료 표식 발견 "
            "- 설치 단계 생략"
        )

        _write_constraint()

        _patch_forge_requirements()

        _patch_clip_launcher()

        doctor()

        return True

    # -------------------------------------------------------------
    # 이전 marker 제거
    # -------------------------------------------------------------

    _safe_remove(
        MARKER
    )

    # -------------------------------------------------------------
    # Clone
    # -------------------------------------------------------------

    if not clone():

        L.err(
            "Forge clone 실패"
        )

        return False

    # -------------------------------------------------------------
    # 사전 호환성
    # -------------------------------------------------------------

    if not pre_pin():

        L.err(
            "Forge 사전 호환성 준비 실패"
        )

        return False

    # -------------------------------------------------------------
    # 최종 CLIP launcher 확인
    # -------------------------------------------------------------

    _patch_clip_launcher()

    # -------------------------------------------------------------
    # dependency 설치
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
        errors="replace",
    )

    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdout=f,
        stderr=subprocess.STDOUT,
        env=_env(),
        preexec_fn=os.setsid,
    )

    t0 = time.time()

    rc = None

    while True:

        rc = proc.poll()

        # ---------------------------------------------------------
        # 종료
        # ---------------------------------------------------------

        if rc is not None:

            elapsed = (
                (time.time() - t0)
                / 60
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
                    % (
                        rc,
                        elapsed,
                    )
                )

            break

        # ---------------------------------------------------------
        # timeout
        # ---------------------------------------------------------

        if (
            time.time()
            - t0
            > timeout
        ):

            L.err(
                "의존성 설치 타임아웃"
            )

            _killpg(
                proc
            )

            rc = 124

            break

        # ---------------------------------------------------------
        # 화면 진행 표시
        # ---------------------------------------------------------

        elapsed = (
            time.time()
            - t0
        )

        if int(elapsed) % 60 < 5:

            # 매분 한 번 정도만 표시
            L.log(
                "   Forge dependency 설치 중 "
                "(%.1f분 경과)"
                % (
                    elapsed / 60
                )
            )

        time.sleep(5)

    f.close()

    # -------------------------------------------------------------
    # 로그
    # -------------------------------------------------------------

    L.tail_file(
        LOGFILE,
        60,
        title="forge.log 끝부분",
    )

    # -------------------------------------------------------------
    # 실패
    # -------------------------------------------------------------

    if rc != 0:

        L.err(
            "Forge 의존성 설치 실패."
        )

        L.err(
            "READY marker를 생성하지 않습니다."
        )

        doctor()

        return False

    # -------------------------------------------------------------
    # 최종 doctor
    # -------------------------------------------------------------

    doctor()

    # -------------------------------------------------------------
    # NumPy 최종 검사
    # -------------------------------------------------------------

    rc_np, out_np = L.shell(
        'python -c '
        '"import numpy;'
        'print(\'FINALNP=\'+numpy.__version__)"',
        quiet=True,
    )

    final_np = ""

    for line in out_np.splitlines():

        if line.startswith(
            "FINALNP="
        ):

            final_np = line.split(
                "=",
                1,
            )[1].strip()

            break

    if final_np != "1.26.4":

        L.err(
            "NumPy 최종 검증 실패 : %s"
            % (
                final_np
                or "?"
            )
        )

        return False

    L.ok(
        "NumPy 최종 검증 : 1.26.4"
    )

    # -------------------------------------------------------------
    # protobuf runtime_version 최종 검사
    # -------------------------------------------------------------

    if not _check_protobuf(
        verbose=True
    ):

        L.err(
            "protobuf runtime_version 최종 검증 실패"
        )

        return False

    # -------------------------------------------------------------
    # CLIP launcher 최종 검사
    # -------------------------------------------------------------

    if not _patch_clip_launcher():

        L.err(
            "CLIP launcher 패치 최종 확인 실패"
        )

        return False

    # -------------------------------------------------------------
    # marker 생성
    # -------------------------------------------------------------

    _write_marker()

    L.ok(
        "Forge v6 의존성 준비 완료 표식 생성"
    )

    return True


# =====================================================================
# Forge API 상태
# =====================================================================

def alive(timeout=5):
    """
    Forge API가 실제 응답하는지 확인한다.
    """

    try:

        r = requests.get(
            API
            + "/sdapi/v1/sd-models",
            timeout=timeout,
        )

        return (
            r.status_code == 200
        )

    except Exception:

        return False


# =====================================================================
# Forge API 기동
# =====================================================================

def launch(
    wait=900,
    attempts=2,
):
    """
    Forge API 기동.
    """

    # -------------------------------------------------------------
    # 이미 실행 중
    # -------------------------------------------------------------

    if alive():

        L.ok(
            "Forge 이미 기동 중"
        )

        return True

    # -------------------------------------------------------------
    # dependency
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
        attempts + 1,
    ):

        L.banner(
            "Forge API 기동 시도 %d/%d"
            % (
                attempt,
                attempts,
            )
        )

        f = open(
            LOGFILE,
            "a",
            encoding="utf-8",
            errors="replace",
        )

        cmd = (
            "cd %s && "
            "python launch.py %s"
            % (
                FORGE,
                args_str(),
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
            preexec_fn=os.setsid,
        )

        t0 = time.time()
        last_report = -60

        while (
            time.time()
            - t0
            < wait
        ):

            # -----------------------------------------------------
            # API 응답
            # -----------------------------------------------------

            if alive(5):

                L.ok(
                    "API 응답 (%.0f초)"
                    % (
                        time.time()
                        - t0
                    )
                )

                f.close()

                return True

            # -----------------------------------------------------
            # 프로세스 종료
            # -----------------------------------------------------

            if (
                proc.poll()
                is not None
            ):

                L.err(
                    "기동 프로세스가 죽었습니다 "
                    "(rc=%s)"
                    % proc.returncode
                )

                break

            # -----------------------------------------------------
            # 진행상황
            # -----------------------------------------------------

            elapsed = (
                time.time()
                - t0
            )

            if (
                elapsed
                - last_report
                >= 60
            ):

                last_report = elapsed

                L.log(
                    "   기동 대기 %.0f초 ..."
                    % elapsed
                )

            time.sleep(6)

        f.close()

        # ---------------------------------------------------------
        # 실패 로그
        # ---------------------------------------------------------

        txt = L.tail_file(
            LOGFILE,
            80,
            title="forge.log 끝부분",
        )

        low = txt.lower()

        # ---------------------------------------------------------
        # 오류 진단
        # ---------------------------------------------------------

        if (
            "runtime_version"
            in low
        ):

            L.err(
                "protobuf runtime_version 오류 감지"
            )

            L.err(
                "protobuf를 downgrade하지 마세요. "
                "Kaggle TensorFlow와 충돌합니다."
            )

        elif (
            "couldn't install clip"
            in low
            or "openai/clip"
            in low
            or "setup.py egg_info"
            in low
        ):

            L.err(
                "구형 OpenAI CLIP 설치 오류 감지"
            )

            L.warn(
                "CLIP launcher 패치를 다시 적용합니다."
            )

            _patch_clip_launcher()

        elif (
            "wandb"
            in low
            and (
                "importerror"
                in low
                or "cannot import"
                in low
            )
        ):

            L.warn(
                "wandb import 오류 감지 -> doctor"
            )

            _check_wandb(
                verbose=True
            )

        elif (
            "xformers"
            in low
        ):

            L.warn(
                "xformers 오류 감지 -> doctor"
            )

        elif (
            "numpy"
            in low
            or "scikit-image"
            in low
            or "skimage"
            in low
        ):

            L.warn(
                "NumPy/scikit-image 오류 감지 -> doctor"
            )

        else:

            L.warn(
                "Forge 기동 원인 불명 -> doctor"
            )

        doctor(
            verbose=False
        )

        # ---------------------------------------------------------
        # 프로세스 정리
        # ---------------------------------------------------------

        _killpg(
            proc
        )

        time.sleep(5)

    L.err(
        "Forge 기동 실패 - %s 확인"
        % LOGFILE
    )

    return False


# =====================================================================
# 모델 API
# =====================================================================

def models():
    try:

        r = requests.get(
            API
            + "/sdapi/v1/sd-models",
            timeout=60,
        )

        return r.json()

    except Exception:

        return []


def upscalers():
    try:

        r = requests.get(
            API
            + "/sdapi/v1/upscalers",
            timeout=60,
        )

        return [
            u.get(
                "name",
                "",
            )
            for u in r.json()
        ]

    except Exception:

        return []


# =====================================================================
# Checkpoint 검색
# =====================================================================

def resolve_checkpoint(
    want="novaanimexl_ilv190",
):
    """
    원하는 체크포인트를 Forge API에서 찾는다.
    """

    target = (
        want.lower()
        .replace(
            " ",
            "",
        )
    )

    for m in models():

        for key in (
            "model_name",
            "title",
            "filename",
        ):

            v = str(
                m.get(
                    key,
                    "",
                )
            )

            normalized = (
                v.lower()
                .replace(
                    " ",
                    "",
                )
            )

            if target in normalized:

                return (
                    m.get(
                        "title"
                    )
                    or m.get(
                        "model_name"
                    )
                )

    return None


# =====================================================================
# Forge 옵션
# =====================================================================

def apply_options(
    ckpt_title,
    vae="sdxl_vae.safetensors",
    clip_skip=2,
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
            API
            + "/sdapi/v1/options",
            json=opts,
            timeout=600,
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
            "옵션 적용 실패 : %s"
            % e
        )

        return False


# =====================================================================
# Forge 인식 검증
# =====================================================================

def verify(
    need_upscalers=(
        "4x-UltraSharp",
        "4x-AnimeSharp",
    ),
):
    """
    체크포인트 및 업스케일러 인식 여부 확인.
    """

    ms = [
        m.get(
            "model_name",
            "",
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
        "v190"
        in m.lower()
        for m in ms
    )

    miss = [
        n
        for n in need_upscalers
        if not any(
            n.lower()
            == u.lower()
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
    clip_skip=2,
):
    """
    어떤 상태에서 호출해도
    사용 가능한 Forge를 보장한다.
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
            clip_skip=clip_skip,
        )

    else:

        L.warn(
            "novaAnimeXL_ilV190 체크포인트를 "
            "자동 검색하지 못했습니다."
        )

    return True


# =====================================================================
# Forge 종료
# =====================================================================

def stop(
    wait=90,
):
    """
    Forge API 종료.
    """

    L.log(
        "Forge 종료 요청"
    )

    # -------------------------------------------------------------
    # checkpoint unload
    # -------------------------------------------------------------

    try:

        requests.post(
            API
            + "/sdapi/v1/unload-checkpoint",
            timeout=60,
        )

    except Exception:

        pass

    # -------------------------------------------------------------
    # launch.py 종료
    # -------------------------------------------------------------

    subprocess.run(
        "pkill -f 'launch.py' "
        "> /dev/null 2>&1",
        shell=True,
    )

    subprocess.run(
        "pkill -f 'webui.py' "
        "> /dev/null 2>&1",
        shell=True,
    )

    # -------------------------------------------------------------
    # API 종료 확인
    # -------------------------------------------------------------

    t0 = time.time()

    while (
        time.time()
        - t0
        < wait
    ):

        if not alive(3):

            break

        time.sleep(3)

    time.sleep(6)

    # -------------------------------------------------------------
    # VRAM
    # -------------------------------------------------------------

    L.shell(
        "nvidia-smi "
        "--query-gpu=index,memory.used,memory.total "
        "--format=csv,noheader",
        quiet=False,
        title="종료 후 VRAM",
    )

    L.ok(
        "Forge 종료 완료"
    )
