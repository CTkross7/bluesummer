# -*- coding: utf-8 -*-
"""자동저장 워커(기본 20분) + 수동 플러시."""
import sys, time, threading
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST, bs_git as G, bs_log as L

_thr, _stop = None, threading.Event()


def _loop(interval):
    while not _stop.wait(interval):
        try:
            r = G.sync(message="autosave", include_src=True)
            L.ok("[autosave] +%d장 commit=%s push=%s"
                 % (r["copied"], r["head"][:7], "OK" if r["pushed"] else "FAIL"))
            ST.mark("autosave_last", "done", r["head"])
        except Exception as e:
            L.err("[autosave] 실패: %s" % e)
            L.exc()


def start(interval_min=20):
    global _thr
    if _thr and _thr.is_alive():
        L.log("[autosave] 이미 동작 중")
        return _thr
    _stop.clear()
    _thr = threading.Thread(target=_loop, args=(interval_min * 60,), daemon=True)
    _thr.start()
    L.ok("[autosave] %d분 간격 시작" % interval_min)
    return _thr


def stop():
    _stop.set()
    L.log("[autosave] 중지 요청")


def flush(message="manual flush"):
    try:
        r = G.sync(message=message, include_src=True)
        L.ok("[flush] +%d장 commit=%s push=%s 저장소파일 %d개"
             % (r["copied"], r["head"][:7], "OK" if r["pushed"] else "FAIL",
                r["files_in_repo"]))
        return r
    except Exception as e:
        L.err("[flush] 실패: %s" % e)
        return {"copied": 0, "head": "", "pushed": False, "files_in_repo": 0}
