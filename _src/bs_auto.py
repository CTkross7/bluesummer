# -*- coding: utf-8 -*-
"""무인 오케스트레이터. 순서 : LoRA 소스 -> 선별 -> 데이터셋 -> 학습 -> 배치
   -> 인물 -> 배경 -> UI -> 검증 -> 재생성 -> 동기화 -> 백업.

   CPU 폴백 대응
     · CPU 세션에서는 LoRA 소스/선별/데이터셋/학습 단계를 건너뛴다
       (SDXL LoRA 학습은 CPU 로 수 주가 걸려 현실성이 없다).
     · 이미 학습된 LoRA 가 lora_out/ 에 있으면 Forge 에 배치해
       CPU 생성에도 GPU 때와 동일하게 적용한다.
     · 단계별 시간 판정은 실측 평균(ST.timing_avg)을 사용하므로
       CPU 의 느린 속도가 자동 반영된다.

   환경변수
     BS_CHARS   = HRM,SRA   이번 세션에서 처리할 캐릭터만 지정
                            (CPU 세션 여러 개를 병렬로 돌릴 때 분담용)
     BS_CPU_TRAIN = 1       CPU 에서도 LoRA 학습을 강행
"""
import os, sys, glob, shutil, importlib, time
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_config as C, bs_log as L, bs_state as ST, bs_budget as B
import bs_autosave as AS, bs_forge as FG, bs_common as K

try:
    import bs_device as D
except Exception:
    D = None


# =====================================================================
# 공통 유틸
# =====================================================================

def _cpu():
    return bool(getattr(C, "CPU_MODE", False))


def _train_allowed():
    if not C.ENABLE_LORA:
        return False
    if _cpu() and not getattr(C, "ENABLE_LORA_TRAIN_ON_CPU", False):
        return False
    return True


def _char_list():
    """BS_CHARS 로 이번 세션 담당 캐릭터를 좁힐 수 있다."""
    raw = os.environ.get("BS_CHARS", "").strip()
    if not raw:
        return list(K.CHARS)
    want = [x.strip().upper() for x in raw.replace(" ", ",").split(",") if x.strip()]
    picked = [c for c in K.CHARS if c in want]
    if picked:
        L.log("BS_CHARS 지정 - 이번 세션 담당 : %s" % picked)
        return picked
    L.warn("BS_CHARS 값(%s)이 유효하지 않아 전체를 대상으로 합니다" % raw)
    return list(K.CHARS)


def _per_image_min(kind, default_min):
    """실측 평균(초)을 분으로. 측정치가 없으면 config 추정치."""
    return ST.timing_avg(kind, float(default_min) * 60.0) / 60.0


def _forge(required=True):
    if D is not None:
        try:
            D.apply_env()
            D.apply_forge()
        except Exception as e:
            L.warn("디바이스 어댑터 적용 경고: %s" % e)
    if FG.alive() and FG.verify():
        if D is not None:
            try:
                D.patch_engine()
            except Exception:
                pass
        return True
    L.warn("Forge 미기동 - 복구 시도")
    ok = FG.ensure(clip_skip=C.CLIP_SKIP)
    if ok and D is not None:
        try:
            D.patch_engine()
        except Exception:
            pass
    if not ok and required:
        L.err("Forge 복구 실패 - 생성 단계를 건너뜁니다")
    return ok


def _deploy_existing_lora():
    """이전 세션/HF 백업에서 확보한 LoRA 를 Forge 가 인식하도록 배치."""
    dst = "/kaggle/temp/models/Lora"
    os.makedirs(dst, exist_ok=True)
    n = 0
    for p in sorted(glob.glob(os.path.join(ST.LORA_OUT, "*.safetensors"))):
        t = os.path.join(dst, os.path.basename(p))
        try:
            if (not os.path.exists(t)) or os.path.getsize(t) != os.path.getsize(p):
                shutil.copy2(p, t)
            n += 1
        except Exception as e:
            L.warn("LoRA 배치 실패 %s: %s" % (os.path.basename(p), e))
    if n:
        try:
            import requests
            requests.post(FG.API + "/sdapi/v1/refresh-loras", timeout=120)
        except Exception:
            pass
    L.log("기존 LoRA %d개 배치 (%s)" % (n, dst))
    return n


# =====================================================================
# 단계
# =====================================================================

def stage_lora_src():
    if not C.ENABLE_LORA:
        return True
    if not _train_allowed():
        L.warn("CPU 모드 - LoRA 소스 생성을 건너뜁니다 "
               "(학습을 못 하므로 소스만 뽑아봐야 의미가 없습니다)")
        L.log("  강행하려면 세션 환경변수 BS_CPU_TRAIN=1 을 주세요")
        return True
    todo = [c for c in _char_list() if not ST.is_done("lora_src_" + c)]
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
    return all(ST.is_done("lora_src_" + c) for c in _char_list())


def stage_select_dataset():
    if not C.ENABLE_LORA:
        return True
    if not _train_allowed():
        L.log("CPU 모드 - 선별/데이터셋 단계 생략")
        return True
    import bs_select as SEL, bs_dataset as DS
    importlib.reload(SEL)
    importlib.reload(DS)
    ready = [c for c in _char_list()
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

    if not _train_allowed():
        L.warn("CPU 모드 - LoRA 학습을 건너뜁니다")
        L.log("  SDXL LoRA 를 4코어 CPU 로 학습하면 캐릭터 1명당 수십~수백 시간입니다.")
        L.log("  대신 이미 학습해 둔 LoRA 가 있으면 그대로 사용합니다.")
        n = _deploy_existing_lora()
        if n == 0:
            L.warn("  사용 가능한 LoRA 가 없습니다 -> 이번 세션은 LoRA 없이 생성합니다")
            L.warn("  (bs_common.lora_ready 가 자동으로 판단하므로 생성은 정상 진행됩니다)")
        ST.rescan()
        return True

    import bs_kohya as KO
    importlib.reload(KO)
    todo = [c for c in _char_list()
            if not ST.is_done("lora_" + c)
            and glob.glob(os.path.join(ST.BASE, "lora", c, "img", "*_*"))]
    if not todo:
        L.ok("LoRA 학습 : 남은 대상 없음")
        KO.deploy()
        _deploy_existing_lora()
        return True
    prec, opt, gpus = KO.caps()
    gpu_id = None
    if gpus >= 2:
        L.log("GPU %d장 - Forge 유지하고 GPU1 에서 학습합니다" % gpus)
        gpu_id = 1
    else:
        L.warn("GPU 1장 이하 - 학습 전 Forge 를 종료합니다 (메모리 확보)")
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
    _deploy_existing_lora()
    L.ok("이번 세션 학습 완료 %d명 / 총 LoRA %d개"
         % (trained, len(glob.glob(ST.LORA_OUT + "/*.safetensors"))))
    return all(ST.is_done("lora_" + c) for c in _char_list())


def stage_char():
    if not _forge():
        return False
    import bs_run_char as R
    importlib.reload(R)
    by = ST.by_char()
    targets = _char_list()
    todo = [c for c in targets if by.get(c, 0) < 60]
    if not todo:
        L.ok("인물 : 담당 분량 완료")
        return True
    per = _per_image_min("char", C.EST_CHAR_MIN)
    L.log("인물 1장 예상 %.1f분 (%s)" % (per, "CPU" if _cpu() else "GPU"))
    for c in todo:
        if not B.can(per):
            L.warn("시간 예산 부족 - 인물 단계 중단 (%s 부터 다음 세션)" % c)
            return False
        R.run(c, budget=B)
        if ST.by_char().get(c, 0) >= 60:
            ST.mark("cellB2_char_" + c, "done")
        AS.flush("char " + c)
    by = ST.by_char()
    return all(by.get(c, 0) >= 60 for c in targets)


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
    per = _per_image_min("bg", C.EST_BG_MIN)
    if not B.can(per):
        L.warn("시간 예산 부족 - 배경 단계 생략 (1장 %.1f분 필요)" % per)
        return False
    L.log("배경 1장 예상 %.1f분" % per)
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
    if not B.can(C.EST_UI_MIN):
        L.warn("시간 예산 부족 - UI 단계 생략")
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
    if need:
        per = _per_image_min("char", C.EST_CHAR_MIN)
        if not B.can(per):
            L.warn("시간 예산 부족 - 재생성은 다음 세션으로 미룹니다")
        elif _forge(required=False):
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
    if D is not None:
        D.report()
    L.log(B.status())
    if _cpu():
        L.warn("CPU 모드 - 화질은 GPU 와 동일하지만 장당 30~60분이 걸립니다.")
        L.warn("이 세션에서 완성되는 분량은 대략 %d~%d장입니다."
               % (max(1, int(B.usable_min() / 60)),
                  max(1, int(B.usable_min() / 30))))
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
