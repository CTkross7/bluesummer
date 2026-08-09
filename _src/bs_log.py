# -*- coding: utf-8 -*-
"""BLUE SUMMER 통합 로거. 표준출력과 파일로 동시에 남긴다."""
import os, sys, time, threading, subprocess, traceback

BASE   = "/kaggle/working/BLUESUMMER"
LOGDIR = os.path.join(BASE, "logs")
os.makedirs(LOGDIR, exist_ok=True)

SESSION = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
LOGFILE = os.path.join(LOGDIR, "run_" + SESSION + ".log")
_LOCK   = threading.RLock()
_T0     = time.time()


def _ts():
    el = time.time() - _T0
    return "%s +%02d:%02d" % (time.strftime("%H:%M:%S", time.gmtime()),
                              int(el // 3600) * 60 + int(el % 3600 // 60), int(el % 60))


def write(text):
    with _LOCK:
        try:
            with open(LOGFILE, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass


def log(msg="", tag="INFO"):
    line = "[%s][%-5s] %s" % (_ts(), tag, msg)
    print(line, flush=True)
    write(line)
    return line


def ok(msg):
    return log(msg, "OK")


def warn(msg):
    return log(msg, "WARN")


def err(msg):
    return log(msg, "ERROR")


def exc():
    t = traceback.format_exc()
    print(t, flush=True)
    write(t)
    return t


def banner(title):
    bar = "=" * 68
    print("", flush=True)
    write("")
    log(bar, "----")
    log(str(title), "STEP")
    log(bar, "----")


def shell(cmd, cwd=None, timeout=None, quiet=False, title=None, tail=12, env=None):
    """쉘 실행. 표준출력 전문은 로그파일, 화면에는 마지막 몇 줄만."""
    if title:
        log(title, "SH")
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                           text=True, timeout=timeout, env=env)
        out = (p.stdout or "") + (p.stderr or "")
        rc = p.returncode
    except subprocess.TimeoutExpired as e:
        out = "TIMEOUT after %ss : %s" % (timeout, e)
        rc = 124
    except Exception as e:
        out = "EXC %s" % e
        rc = 1
    write("$ " + cmd + "\n" + out)
    if (not quiet) and out.strip():
        for l in out.strip().splitlines()[-tail:]:
            print("   " + l[:220], flush=True)
    return rc, out


def tail_file(path, n=40, title=None):
    if title:
        log(title, "LOG")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        for l in lines[-n:]:
            print("   " + l[:220], flush=True)
        return "\n".join(lines[-n:])
    except Exception as e:
        warn("로그 읽기 실패 %s : %s" % (path, e))
        return ""


class Progress:
    """N개 작업의 진행률·ETA 출력기."""

    def __init__(self, total, title="작업"):
        self.total = max(1, int(total))
        self.title = title
        self.n = 0
        self.t0 = time.time()

    def step(self, note=""):
        self.n += 1
        el = time.time() - self.t0
        per = el / max(1, self.n)
        eta = per * (self.total - self.n)
        log("[%s %d/%d] %s | 평균 %.0fs · 경과 %.1f분 · 남은예상 %.1f분"
            % (self.title, self.n, self.total, note, per, el / 60, eta / 60), "PROG")

    def done(self):
        log("[%s] 완료 %d건 / %.1f분" % (self.title, self.n, (time.time() - self.t0) / 60), "PROG")


log("로그 파일 : " + LOGFILE)
