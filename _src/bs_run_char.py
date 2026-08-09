# -*- coding: utf-8 -*-
"""인물 60장/인 생성. run(code) / redo(code, ["W03","B07"])"""
import os, sys, time
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_config as C, bs_common as K, bs_engine as E, bs_state as ST
import bs_upload as U, bs_log as L

DEST = os.path.join(ST.DIST, "c")


def _gen(code, combos, use_lora=None, overwrite=False, budget=None):
    os.makedirs(DEST, exist_ok=True)
    if use_lora is None:
        use_lora = K.lora_ready(code)
    pr = L.Progress(len(combos), "인물 " + code)
    L.log("[%s] %d장 / LoRA=%s" % (code, len(combos), "ON" if use_lora else "OFF"))
    fails = []
    for (o, e) in combos:
        if budget is not None and not budget.can(ST.timing_avg("char",
                                                               C.EST_CHAR_MIN * 60) / 60):
            L.warn("[%s] 시간 예산 부족 - 중단" % code)
            break
        name = "%s%s%s" % (code, o, e)
        path = os.path.join(DEST, name + ".webp")
        salt = ST.retry_of(name)
        p = K.build_prompt(code, o, e, use_lora=use_lora)
        _, _, note = E.make(p, C.NEG_CHAR, path, seed=K.seed_of(code, o, e, salt),
                            overwrite=overwrite)
        if note == "fail":
            fails.append(name)
            ST.bump_retry(name)
        pr.step("%s.webp %s" % (name, note))
        if pr.n % C.PUSH_EVERY == 0:
            U.push("char %s %d" % (code, pr.n), force=True)
    pr.done()
    ST.rescan()
    U.push("char %s done" % code, force=True)
    if fails:
        L.warn("[%s] 실패 %d건 : %s" % (code, len(fails), fails[:10]))
    return fails


def run(code, use_lora=None, overwrite=False, budget=None):
    code = code.upper()
    return _gen(code, [(o, e) for o in K.OUTFIT_ORDER for e in K.EMO_ORDER],
                use_lora, overwrite, budget)


def redo(code, combos, use_lora=None, budget=None):
    code = code.upper()
    return _gen(code, [(c[0], c[1:]) for c in combos], use_lora, True, budget)


def run_group(codes, **kw):
    for c in codes:
        run(c, **kw)


if __name__ == "__main__":
    run(sys.argv[1])
