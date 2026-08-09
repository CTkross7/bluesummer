
# -*- coding: utf-8 -*-
"""BLUE SUMMER 진행 원장."""
import json, os, time, glob, tempfile, threading

BASE     = "/kaggle/working/BLUESUMMER"
DIST     = os.path.join(BASE, "dist")
LORA_OUT = os.path.join(BASE, "lora_out")
PATH     = os.path.join(BASE, "bs_state.json")
_LOCK    = threading.RLock()

CHARS  = ["HRM","SRA","MJO","HTI","KYS","LCH","BRW","CSM",
          "JHO","YDH","PSA","OMR"]
OUTFIT = ["W","C","B","N","F","R"]
EMO    = ["01","02","03","04","05","06","07","08","09","10"]

BG_CODES = """BCH1 BCH2 BCH3 BCH4 BCH3R PIE1 PIE3 PIE4 PIE4R
CMP1 CMP3 CMP4 CMP4R MKT3 MKT4 MKT4R CAF1 CAF2 CAF3 CAF2R
GST1 GST2 GST3 GST4 LGH2 LGH3 LGH4 LGH4R VLY1 VLY2 VLY3
POL2 POL3 POL4 PLZ2 PLZ3 PLZ4 PLZ3R CVS1 CVS3 CVS4 CVS3R
FOR1 FOR2 FOR3 FOR2R OBS2 OBS3 OBS4 OBS3R STA2 STA3 STA4 STA2R
HRB1 HRB2 HRB3 HRB4 DIV1 DIV2 DIV3 TWN2 TWN3 TWN4
ROM1 ROM3 ROM4 ROM4R""".split()

UI_CODES = ["status","album","talk","town","map","card","sns","radio"]

WANT_CHAR = [f"{c}{o}{e}" for c in CHARS for o in OUTFIT for e in EMO]  # 720
WANT_BG   = list(BG_CODES)                                             # 68
WANT_UI   = list(UI_CODES)                                             # 8

_DEFAULT = {"schema": 3, "created": None, "updated": None,
            "steps": {}, "counts": {}, "inventory": {},
            "commits": [], "last_commit": None, "log": []}

def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + " UTC"

def load():
    with _LOCK:
        if os.path.exists(PATH):
            try:
                with open(PATH, encoding="utf-8") as f:
                    st = json.load(f)
                for k, v in _DEFAULT.items():
                    if isinstance(v, (dict, list)):
                        st.setdefault(k, type(v)())
                    else:
                        st.setdefault(k, v)
                return st
            except Exception:
                pass
        st = json.loads(json.dumps(_DEFAULT))
        st["created"] = _now()
        return st

def save(st):
    with _LOCK:
        os.makedirs(BASE, exist_ok=True)
        st["updated"] = _now()
        fd, tmp = tempfile.mkstemp(dir=BASE, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(st, f, ensure_ascii=False, indent=1)
            os.replace(tmp, PATH)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        return st

def mark(step, status="done", note=""):
    st = load()
    st["steps"][step] = {"status": status, "ts": _now(), "note": str(note)[:400]}
    st["log"] = (st["log"] + [f"{_now()} | {step} | {status} | {str(note)[:120]}"])[-300:]
    return save(st)

def status_of(step):
    return load()["steps"].get(step, {}).get("status")

def is_done(step):
    return status_of(step) == "done"

def _have(sub):
    d = os.path.join(DIST, sub)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(d, "*.webp")))

def rescan():
    """실제 산출물을 세어 원장을 갱신한다. 언제 호출해도 안전."""
    st = load()
    c, bg, ui = _have("c"), _have("bg"), _have("ui")
    lora = sorted(os.path.basename(p)
                  for p in glob.glob(os.path.join(LORA_OUT, "*.safetensors")))
    st["inventory"] = {"char": c, "bg": bg, "ui": ui, "lora": lora}
    st["counts"] = {"char": len(c), "bg": len(bg), "ui": len(ui), "lora": len(lora),
                    "char_want": len(WANT_CHAR), "bg_want": len(WANT_BG),
                    "ui_want": len(WANT_UI)}
    return save(st)

def missing():
    st = rescan()
    inv = st["inventory"]
    hc, hb, hu = set(inv["char"]), set(inv["bg"]), set(inv["ui"])
    return ([x for x in WANT_CHAR if x not in hc],
            [x for x in WANT_BG   if x not in hb],
            [x for x in WANT_UI   if x not in hu])

def by_char():
    st = rescan()
    hc = set(st["inventory"]["char"])
    return {c: sum(1 for o in OUTFIT for e in EMO if f"{c}{o}{e}" in hc) for c in CHARS}

def lora_done():
    st = rescan()
    have = set(st["inventory"]["lora"])
    return [c for c in CHARS if f"bs_{c.lower()}.safetensors" in have]

def report():
    st = rescan()
    cnt = st["counts"]
    mc, mb, mu = missing()
    print("═" * 58)
    print(f"BLUE SUMMER 진행 원장   (갱신 {st['updated']})")
    print("═" * 58)
    print(f"인물 {cnt['char']:>3}/720   배경 {cnt['bg']:>2}/68   "
          f"UI {cnt['ui']}/8   LoRA {cnt['lora']}/12")
    print(f"누락  인물 {len(mc)} · 배경 {len(mb)} · UI {len(mu)}")
    print(f"마지막 커밋 : {st.get('last_commit') or '-'}")
    print("- 캐릭터별 -")
    for c, n in by_char().items():
        print(f"   {c} {n:>2}/60 {'✅' if n == 60 else ''}")
    if st["steps"]:
        print("- 완료 단계 -")
        for k, v in st["steps"].items():
            print(f"   [{v['status']:>7}] {k}  ({v['ts']})")
    print("═" * 58)
    return st
