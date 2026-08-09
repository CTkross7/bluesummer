# -*- coding: utf-8 -*-
"""N장 단위 GitHub 푸시 래퍼. bs_git.sync 를 재사용하므로 자동저장과 직렬화된다."""
import sys, time
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST, bs_git as G, bs_log as L, bs_config as C

_last = {"t": 0.0, "n": -1}
MIN_INTERVAL = 90


def count():
    c = ST.rescan()["counts"]
    return c["char"] + c["bg"] + c["ui"]


def push(message="assets", force=False):
    now = time.time()
    if (not force) and now - _last["t"] < MIN_INTERVAL:
        return {"skipped": True}
    try:
        r = G.sync(message="v3 " + message, include_src=True)
        _last["t"] = time.time()
        L.ok("   [push] +%d장 commit=%s push=%s"
             % (r["copied"], r["head"][:7], "OK" if r["pushed"] else "FAIL"))
        return r
    except Exception as e:
        L.warn("   [push] 보류: %s" % e)
        return {"error": str(e)}


def maybe_push(every=None, message="assets"):
    every = every or C.PUSH_EVERY
    n = count()
    prev = _last["n"]
    _last["n"] = n
    if prev < 0:
        return None
    if n // every > prev // every:
        return push("%s %d" % (message, n))
    return None
