# -*- coding: utf-8 -*-
"""무인 오케스트레이터. 순서 : LoRA 소스 -> 선별 -> 데이터셋 -> 학습 -> 배치
   -> 인물 -> 배경 -> UI -> 검증 -> 재생성 -> 동기화 -> 백업."""
import os, sys, glob, importlib, time
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_config as C, bs_log as L, bs_state as ST, bs_budget as B
import bs_autosave as AS, bs_forge as FG, bs_common as K


def _forge(required=True):
    if FG.alive() and FG.verify():
        return True
    L.warn("Forge 미기동 - 복구 시도")
    ok = FG.ensure(clip_skip=C.CLIP_SKIP)
    if not ok and required:
        L.err("Forge 복구 실패 - 생성 단계를 건너뜁니다")
    return ok


def stage_lora_src():
    if not C.ENABLE_LORA:
        return True
    todo = [c for c in K.CHARS if not ST.is_done("lora_src_" + c)]
    if not todo:
        L.ok("LoRA 소스 : 전원 완료")
        return True
    if not _forge():
        return False
    import bs_lora_src as LS
    importlib.reload(LS)
    for c in todo:
        need = C.LORA_SRC_N * C.EST_LORASRC_MIN
        if not B.can(min(need, 25)):
            L.warn("시간 예산 부족 - LoRA 소스 단계 중단 (%s 부터 다음 세션)" % c)
            return False
        done = LS.run(c, budget=B)
        have = len(glob.glob(os.path.join(ST.BASE, "lora", c, "candidates", "*.png")))
        if done and have >= C.LORA_SRC_N * 0.9:
            ST.mark("lora_src_" + c, "done", "%d장" % have)
        AS.flush("lora src " + c)
    return all(ST.is_done("lora_src_" + c) for c in K.CHARS)


def stage_select_dataset():
    if not C.ENABLE_LORA:
        return True
    import bs_select as SEL, bs_dataset as DS
    importlib.reload(SEL)
    importlib.reload(DS)
    ready = [c for c in K.CHARS
             if glob.glob(os.path.join(ST.BASE, "lora", c, "candidates", "*.png"))]
    if not ready:
        L.warn("후보 이미지 없음 - 선별/데이터셋 생략")
        return False
    for c in ready:
        SEL.select(c)
    for c in ready:
        DS.build(c)
    ST.mark("cellA2_select", "done")
    ST.mark("cellA3_dataset", "done")
    AS.flush("dataset")
    return True


def stage_train():
    if not C.ENABLE_LORA:
        return True
    import bs_kohya as KO
    importlib.reload(KO)
    todo = [c for c in K.CHARS
            if not ST.is_done("lora_" + c)
            and glob.glob(os.path.join(ST.BASE, "lora", c, "img", "*_*"))]
    if not todo:
        L.ok("LoRA 학습 : 남은 대상 없음")
        KO.deploy()
        return True
    prec, opt, gpus = KO.caps()
    gpu_id = None
    if gpus >= 2:
        L.log("GPU %d장 - Forge 유지하고 GPU1 에서 학습합니다" % gpus)
        gpu_id = 1
    else:
        L.warn("GPU 1장 - 학습 전 Forge 를 종료합니다 (OOM 방지)")
        FG.stop()
    trained = 0
    for c in todo:
        if not B.can(C.EST_TRAIN_MIN):
            L.warn("시간 예산 부족 - 학습 단계 중단 (%s 부터 다음 세션)" % c)
            break
        if KO.train(c, gpu_id=gpu_id):
            trained += 1
            KO.deploy()
            try:
                import bs_backup as BK
                BK.hf_backup(include_raw=False)
            except Exception as e:
                L.warn("HF 업로드 실패: %s" % e)
        AS.flush("lora train " + c)
    KO.deploy()
    L.ok("이번 세션 학습 완료 %d명 / 총 LoRA %d개"
         % (trained, len(glob.glob(ST.LORA_OUT + "/*.safetensors"))))
    return all(ST.is_done("lora_" + c) for c in K.CHARS)


def stage_char():
    if not _forge():
        return False
    import bs_run_char as R
    importlib.reload(R)
    by = ST.by_char()
    todo = [c for c in K.CHARS if by.get(c, 0) < 60]
    if not todo:
        L.ok("인물 720장 완료")
        return True
    for c in todo:
        if not B.can(5):
            L.warn("시간 예산 부족 - 인물 단계 중단 (%s 부터 다음 세션)" % c)
            return False
        R.run(c, budget=B)
        if ST.by_char().get(c, 0) >= 60:
            ST.mark("cellB2_char_" + c, "done")
        AS.flush("char " + c)
    return all(v >= 60 for v in ST.by_char().values())


def stage_bg():
    if ST.rescan()["counts"]["bg"] >= len(ST.WANT_BG):
        L.ok("배경 68장 완료")
        return True
    if not _forge():
        return False
    import bs_bg as BG
    importlib.reload(BG)
    if len(BG.BG) != 68:
        L.warn("배경 정의 %d개 (68 기대)" % len(BG.BG))
    BG.run(budget=B)
    AS.flush("bg")
    done = ST.rescan()["counts"]["bg"] >= len(ST.WANT_BG)
    if done:
        ST.mark("cellB3_bg", "done")
    return done


def stage_ui():
    if ST.rescan()["counts"]["ui"] >= len(ST.WANT_UI):
        L.ok("UI 8장 완료")
        return True
    if not _forge():
        return False
    import bs_ui as UI
    importlib.reload(UI)
    UI.run()
    AS.flush("ui")
    done = ST.rescan()["counts"]["ui"] >= len(ST.WANT_UI)
    if done:
        ST.mark("cellB4_ui", "done")
    return done


def stage_verify():
    import bs_verify as V
    importlib.reload(V)
    rep = V.verify()
    need = rep["redo_char"] or rep["redo_bg"] or rep["redo_ui"]
    if need and _forge(required=False):
        V.redo(rep, budget=B)
        rep = V.verify()
    AS.flush("verify")
    return not (rep["miss"] or rep["bad"] or rep["blurry"])


def stage_publish():
    AS.flush("final sync")
    try:
        import bs_backup as BK
        importlib.reload(BK)
        BK.hf_backup(include_raw=True)
        BK.cdn_check(full_purge=not ST.is_done("cdn_purged"))
        ST.mark("cdn_purged", "done")
    except Exception as e:
        L.warn("발행 단계 경고: %s" % e)
    return True


STAGES = [("LoRA 소스 생성", stage_lora_src),
          ("선별 + 데이터셋", stage_select_dataset),
          ("LoRA 학습", stage_train),
          ("인물 720장", stage_char),
          ("배경 68장", stage_bg),
          ("UI 8장", stage_ui),
          ("품질 검증/재생성", stage_verify),
          ("동기화/백업/CDN", stage_publish)]


def run_all():
    L.banner("무인 파이프라인 시작")
    L.log(B.status())
    results = []
    for name, fn in STAGES:
        if B.exhausted():
            L.warn("시간 예산 소진 - 남은 단계는 다음 세션에서 이어집니다")
            break
        L.banner("단계 : " + name)
        try:
            ok = bool(fn())
        except Exception as e:
            L.err("단계 실패 [%s] : %s" % (name, e))
            L.exc()
            ok = False
        results.append((name, ok))
        L.log("단계 결과 [%s] : %s | %s" % (name, "완료" if ok else "미완/부분",
                                             B.status()))
        AS.flush("stage " + name)
    L.banner("파이프라인 요약")
    for name, ok in results:
        L.log("  %-18s %s" % (name, "완료" if ok else "미완 - 다음 세션 계속"))
    ST.report()
    return results
