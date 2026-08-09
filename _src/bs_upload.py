
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST, bs_git as G

_n = 0
EVERY = 20

def tick(note="", force=False):
    """이미지 1장 만들 때마다 호출. 20장마다 실제 푸시."""
    global _n
    _n += 1
    if force or _n % EVERY == 0:
        try:
            r = G.sync(message=f"assets {note}", include_src=False)
            if not r.get("skipped"):
                print(f"   [push] +{r['copied']}장 → {r['head'][:7]} "
                      f"{'OK' if r['pushed'] else 'FAIL'}")
        except Exception as e:
            print("   [push] 실패(다음 주기에 재시도):", e)

def flush(note="flush"):
    tick(note, force=True)
