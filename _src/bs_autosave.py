
# -*- coding: utf-8 -*-
import sys, time, threading, traceback
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST, bs_git as G

_thr, _stop = None, threading.Event()

def _loop(interval):
    while not _stop.wait(interval):
        try:
            r = G.sync(message="autosave", include_src=True)
            if r.get("skipped"):
                continue
            print(f"[autosave {time.strftime('%H:%M:%S')}] +{r['copied']}장 "
                  f"commit={r['head'][:7]} push={'OK' if r['pushed'] else 'FAIL'}",
                  flush=True)
            ST.mark("autosave_last", "done", r["head"])
        except Exception as e:
            print("[autosave] 실패:", e, flush=True)
            traceback.print_exc()

def start(interval_min=20):
    global _thr
    if _thr and _thr.is_alive():
        print("[autosave] 이미 동작 중")
        return _thr
    _stop.clear()
    _thr = threading.Thread(target=_loop, args=(interval_min * 60,), daemon=True)
    _thr.start()
    print(f"[autosave] {interval_min}분 간격으로 시작")
    return _thr

def stop():
    _stop.set()
    print("[autosave] 중지 요청")

def flush(message="manual flush"):
    r = G.sync(message=message, include_src=True)
    if r.get("skipped"):
        print("[flush] GitHub 시크릿 없음 — 건너뜀")
        return r
    print(f"[flush] +{r['copied']}장 commit={r['head'][:7]} "
          f"push={'OK' if r['pushed'] else 'FAIL'} 저장소파일 {r['files_in_repo']}개")
    return r
