# -*- coding: utf-8 -*-
"""세션 시간 예산 관리 + 만료 전 자동 플러시 워치독.

   Kaggle GPU 세션과 CPU 세션은 최대 실행 시간이 다르므로
   디바이스에 따라 기본 예산을 자동으로 바꾼다.
     GPU : 470분 사용 + 18분 마무리
     CPU : 690분 사용 + 25분 마무리
   BS_BUDGET_MIN / BS_RESERVE_MIN 으로 언제든 덮어쓸 수 있다."""
import os, sys, time, threading
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_log as L

try:
    import bs_device as _D
    DEVICE = _D.detect()
except Exception:
    DEVICE = "cpu"
    try:
        import torch
        if torch.cuda.is_available() and torch.cuda.device_count() > 0:
            DEVICE = "cuda"
    except Exception:
        DEVICE = "cpu"

_DEF_BUDGET = "690" if DEVICE == "cpu" else "470"
_DEF_RESERVE = "25" if DEVICE == "cpu" else "18"

START      = time.time()
BUDGET_MIN = int(os.environ.get("BS_BUDGET_MIN", _DEF_BUDGET))
RESERVE_MIN = int(os.environ.get("BS_RESERVE_MIN", _DEF_RESERVE))

_stopped = False
_reason  = ""
_thr     = None
_evt     = threading.Event()


def elapsed_min():
    return (time.time() - START) / 60.0


def remain_min():
    return BUDGET_MIN - elapsed_min()


def usable_min():
    return remain_min() - RESERVE_MIN


def exhausted():
    return _stopped or usable_min() <= 0


def can(est_min):
    """est_min 분짜리 작업을 지금 시작해도 되는가."""
    return (not _stopped) and usable_min() >= float(est_min)


def force_stop(reason="manual"):
    global _stopped, _reason
    _stopped = True
    _reason = reason
    L.warn("예산 소진 선언 : %s" % reason)


def status():
    return "[%s] 경과 %.0f분 / 예산 %d분 / 가용 %.0f분%s" % (
        DEVICE.upper(), elapsed_min(), BUDGET_MIN, max(0.0, usable_min()),
        " (STOP:%s)" % _reason if _stopped else "")


def _loop(flush_fn, interval):
    while not _evt.wait(interval):
        if _stopped:
            continue
        if usable_min() <= 0:
            L.warn("세션 만료 임박 - 워치독이 최종 플러시를 수행합니다")
            try:
                flush_fn("watchdog final flush")
            except Exception as e:
                L.err("워치독 플러시 실패: %s" % e)
            force_stop("watchdog")
        elif int(elapsed_min()) % 30 == 0:
            L.log(status(), "TIME")


def start_watchdog(flush_fn, interval_sec=60):
    global _thr
    if _thr and _thr.is_alive():
        return _thr
    _evt.clear()
    _thr = threading.Thread(target=_loop, args=(flush_fn, interval_sec), daemon=True)
    _thr.start()
    L.ok("시간 워치독 시작 (%s)" % status())
    return _thr


def stop_watchdog():
    _evt.set()
