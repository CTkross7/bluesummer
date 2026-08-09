
# -*- coding: utf-8 -*-

"""
BLUE SUMMER 통합 로거.

- 표준출력 + 파일 동시 기록
- subprocess 실행 결과 기록
- Forge 로그 tail 출력
- 진행률 / ETA 지원
"""

import os
import sys
import time
import threading
import subprocess
import traceback


# =====================================================================
# 경로
# =====================================================================

BASE = "/kaggle/working/BLUESUMMER"
LOGDIR = os.path.join(BASE, "logs")

os.makedirs(LOGDIR, exist_ok=True)


# =====================================================================
# 세션 로그
# =====================================================================

SESSION = time.strftime(
    "%Y%m%d_%H%M%S",
    time.gmtime()
)

LOGFILE = os.path.join(
    LOGDIR,
    "run_" + SESSION + ".log"
)

_LOCK = threading.RLock()
_T0 = time.time()


# =====================================================================
# 시간
# =====================================================================

def _ts():
    """
    실행 시작 후 경과 시간을 함께 표시한다.
    """

    elapsed = time.time() - _T0

    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    return "%s +%02d:%02d" % (
        time.strftime(
            "%H:%M:%S",
            time.gmtime()
        ),
        minutes,
        seconds
    )


# =====================================================================
# 파일 기록
# =====================================================================

def write(text):
    """
    로그 파일에 직접 기록한다.
    """

    with _LOCK:

        try:

            with open(
                LOGFILE,
                "a",
                encoding="utf-8"
            ) as f:

                f.write(
                    str(text) + "\n"
                )

        except Exception:
            pass


# =====================================================================
# 기본 로그
# =====================================================================

def log(msg="", tag="INFO"):
    """
    화면 + 파일에 동시에 로그를 남긴다.
    """

    line = "[%s][%-5s] %s" % (
        _ts(),
        tag,
        str(msg)
    )

    print(
        line,
        flush=True
    )

    write(line)

    return line


def ok(msg):
    return log(msg, "OK")


def warn(msg):
    return log(msg, "WARN")


def err(msg):
    return log(msg, "ERROR")


# =====================================================================
# 예외 로그
# =====================================================================

def exc():
    """
    현재 예외 traceback을 출력하고 기록한다.
    """

    text = traceback.format_exc()

    print(
        text,
        flush=True
    )

    write(text)

    return text


# =====================================================================
# 배너
# =====================================================================

def banner(title):
    """
    셀/단계 시작용 배너.
    """

    bar = "=" * 68

    print(
        "",
        flush=True
    )

    write("")

    log(
        bar,
        "----"
    )

    log(
        str(title),
        "STEP"
    )

    log(
        bar,
        "----"
    )


# =====================================================================
# Shell 실행
# =====================================================================

def shell(
    cmd,
    cwd=None,
    timeout=None,
    quiet=False,
    title=None,
    tail=12,
    env=None
):
    """
    쉘 명령 실행.

    전체 출력은 로그 파일에 저장하고,
    화면에는 마지막 tail줄만 표시한다.

    반환:
        (return_code, combined_output)
    """

    if title:
        log(
            title,
            "SH"
        )

    try:

        p = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )

        out = (
            (p.stdout or "")
            + (p.stderr or "")
        )

        rc = p.returncode

    except subprocess.TimeoutExpired as e:

        out = (
            "TIMEOUT after %ss : %s"
            % (timeout, e)
        )

        rc = 124

    except Exception as e:

        out = (
            "EXC %s"
            % e
        )

        rc = 1

    # -------------------------------------------------------------
    # 전체 출력은 파일에 기록
    # -------------------------------------------------------------

    write(
        "$ " + cmd
        + "\n"
        + out
    )

    # -------------------------------------------------------------
    # 화면 출력
    # -------------------------------------------------------------

    if not quiet and out.strip():

        for line in out.strip().splitlines()[-tail:]:

            print(
                "   " + line[:220],
                flush=True
            )

    return rc, out


# =====================================================================
# 파일 tail
# =====================================================================

def tail_file(
    path,
    n=40,
    title=None
):
    """
    파일 마지막 n줄을 출력하고 문자열로 반환한다.
    """

    if title:

        log(
            title,
            "LOG"
        )

    try:

        with open(
            path,
            encoding="utf-8",
            errors="replace"
        ) as f:

            lines = f.read().splitlines()

        selected = lines[-n:]

        for line in selected:

            print(
                "   " + line[:220],
                flush=True
            )

        return "\n".join(selected)

    except Exception as e:

        warn(
            "로그 읽기 실패 %s : %s"
            % (path, e)
        )

        return ""


# =====================================================================
# 진행률
# =====================================================================

class Progress:
    """
    N개 작업의 진행률 / ETA 출력기.
    """

    def __init__(
        self,
        total,
        title="작업"
    ):

        self.total = max(
            1,
            int(total)
        )

        self.title = title
        self.n = 0
        self.t0 = time.time()

    def step(self, note=""):

        self.n += 1

        elapsed = (
            time.time()
            - self.t0
        )

        per = (
            elapsed
            / max(1, self.n)
        )

        remaining = max(
            0,
            self.total - self.n
        )

        eta = (
            per
            * remaining
        )

        log(
            "[%s %d/%d] %s | 평균 %.0fs · "
            "경과 %.1f분 · 남은예상 %.1f분"
            % (
                self.title,
                self.n,
                self.total,
                note,
                per,
                elapsed / 60,
                eta / 60
            ),
            "PROG"
        )

    def done(self):

        elapsed = (
            time.time()
            - self.t0
        )

        log(
            "[%s] 완료 %d건 / %.1f분"
            % (
                self.title,
                self.n,
                elapsed / 60
            ),
            "PROG"
        )


# =====================================================================
# 시작 로그
# =====================================================================

log(
    "로그 파일 : " + LOGFILE
)
