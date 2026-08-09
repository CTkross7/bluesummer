# -*- coding: utf-8 -*-
"""세션 시간 예산 관리 + 만료 전 자동 플러시 워치독.
   Kaggle GPU 세션은 9시간이므로 기본 470분 사용 후 18분을 마무리용으로 남긴다."""
import os, sys, time, threading
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_log as L

START      = time.time()
BUDGET_MIN = int(os.environ.get("BS_BUDGET_MIN", "470"))
RESERVE_MIN = int(os.environ.get("BS_RESERVE_MIN", "18"))

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
    return "경과 %.0f분 / 예산 %d분 / 가용 %.0f분%s" % (
        elapsed_min(), BUDGET_MIN, max(0.0, usable_min()),
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
