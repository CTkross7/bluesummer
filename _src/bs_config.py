# -*- coding: utf-8 -*-
"""BLUE SUMMER v3.2 : 화질·학습·자동화 규격의 단일 원천.

v3.1 -> v3.2 변경점 (GPU 한도 소진 대비 CPU 폴백)
  · 파일 맨 아래에 'CPU 폴백 자동 조정' 블록 추가.
  · CPU 모드에서도 화질 파라미터는 단 하나도 바꾸지 않는다.
    (체크포인트/샘플러/steps/CFG/해상도/Hires/ADetailer/프롬프트 동일)
  · 바뀌는 것은 타임아웃 · 진단 주기 · 시간 예산 추정치 · 푸시 주기뿐.
"""
import os

# -------------------------------------------------- 모델
CKPT_NAME   = "novaAnimeXL_ilV190"
CKPT_FILE   = "novaAnimeXL_ilV190.safetensors"
CKPT_SHA256 = "FA486CAAFC330F133605D3C18B418D183812F14946631C6544BFB28730DB6D6F"
CKPT_PATH   = "/kaggle/temp/models/Stable-diffusion/" + CKPT_FILE
VAE_NAME    = "sdxl_vae.safetensors"
VAE_PATH    = "/kaggle/temp/models/VAE/" + VAE_NAME
CLIP_SKIP   = 2

# -------------------------------------------------- 업스케일러
UPSCALER_HIRES = "4x-UltraSharp"   # Hires fix 1차 : 텍스처·의상 디테일 (항상 사용)
UPSCALER_LINE  = "4x-AnimeSharp"   # extras 2차   : 라인아트 (선택 사용)

# -------------------------------------------------- extras(2차 정제) 정책
EXTRAS_ENABLE      = False     # 기본 OFF. True 로 바꾸면 다시 사용한다.
EXTRAS_DUAL        = False     # True 면 업스케일러 2종 블렌드(=구 동작, 2배 느림)
EXTRAS_SCALE       = 1.35      # 2.0 이상은 T4 에서 비현실적
EXTRAS_BLEND       = 0.55      # EXTRAS_DUAL=True 일 때만 의미 있음
EXTRAS_MAX_INPUT_PX = 1200000  # 입력이 이보다 크면 먼저 LANCZOS 축소 후 투입
EXTRAS_TIMEOUT     = 300       # 하드 타임아웃(초). 초과하면 원본을 그대로 쓴다
EXTRAS_SLOW_SEC    = 150       # 이보다 느리면 '느림' 카운트
EXTRAS_SLOW_LIMIT  = 2         # 느림/실패가 이 횟수를 넘으면 세션 내 자동 비활성화

# -------------------------------------------------- 로컬 샤프닝 (extras 대체)
LOCAL_SHARPEN     = True
SHARPEN_RADIUS    = 1.0
SHARPEN_PERCENT   = 55
SHARPEN_THRESHOLD = 3

# -------------------------------------------------- 샘플링 (IL v19.0 공식 권장)
SAMPLER    = "Euler a"
SCHEDULER  = "Automatic"
STEPS      = 26
CFG        = 4.5
WIDTH      = 832
HEIGHT     = 1216
HR_SCALE   = 1.5
HR_STEPS   = 12
HR_DENOISE = 0.42
HR_CFG     = 4.0

BG_STEPS, BG_CFG, BG_HR_STEPS, BG_HR_DENOISE = 28, 5.0, 14, 0.40

OUT_W, OUT_H = 512, 768
WEBP_QUALITY = 92
WEBP_METHOD  = 6

# -------------------------------------------------- ADetailer
AD_ENABLE   = True
AD_FACE     = "face_yolov8s.pt"
AD_HAND     = "hand_yolov8n.pt"
AD_DENOISE  = 0.38
AD_HAND_DENOISE = 0.30
AD_CONF     = 0.30
AD_BLUR     = 4
AD_PROMPT   = ("detailed face, glossy detailed eyes, sharp pupil highlight, "
               "detailed eyelashes, clean lineart, cel shading, perfect anatomy")
AD_HAND_PROMPT = "detailed hands, five fingers, natural finger pose, clean lineart"
AD_NEG      = ("blurry, bad face, deformed face, extra eyes, asymmetric eyes, "
               "lowres, jpeg artifacts, (worst quality, bad quality:1.2)")

# -------------------------------------------------- 프롬프트 블록
QUALITY_HEAD = ("masterpiece, best quality, amazing quality, 4k, very aesthetic, "
                "high resolution, ultra-detailed, absurdres, newest, esthetic")

STYLE_BA = ("official art, key visual, anime style illustration, clean crisp lineart, "
            "cel shading, soft gradient shading, glossy highly detailed eyes, "
            "detailed eyelashes, symmetrical eyes, sharp pupil highlight, "
            "delicate hair strands, fine fabric emphasis, detailed clothing folds, "
            "rim light, backlighting, subsurface scattering, bloom, "
            "vibrant saturated colors, high contrast, sharp focus, perfect anatomy")

TAIL = ("depth of field, volumetric lighting, cinematic lighting, bokeh, "
        "atmospheric perspective")

SCENERY_HEAD = ("masterpiece, best quality, amazing quality, 4k, very aesthetic, "
                "high resolution, ultra-detailed, absurdres, newest, esthetic, scenery, "
                "no humans, empty, anime background art, official art, "
                "highly detailed environment, detailed sky, detailed texture, "
                "clean lineart, vibrant colors, high contrast, sharp focus, "
                "korean seaside town, summer, cinematic composition")

NEG_COMMON = (
    "photorealistic, realistic, 3d, render, cgi, doll, figurine, "
    "(particles, adversarial_noise:1.2), multiple views, multiple angle, split view, "
    "grid view, two shot, outside border, picture frame, framed, border, "
    "letterboxed, pillarboxed, 2koma, modern, recent, old, oldest, "
    "cartoon, graphic, text, english text, korean text, painting, crayon, graphite, "
    "abstract, glitch, deformed, mutated, ugly, disfigured, long body, "
    "lowres, bad anatomy, bad hands, missing fingers, extra fingers, extra digits, "
    "fewer digits, fused fingers, mutated hands, extra limbs, extra arms, extra legs, "
    "cropped, cropped head, out of frame, very displeasing, "
    "(worst quality, bad quality:1.2), sketch, unfinished, jpeg artifacts, "
    "signature, watermark, username, artist name, logo, "
    "(censored, bar_censor, mosaic_censor:1.2), conjoined, bad ai-generated, "
    "nsfw, nude, naked, topless, nipples, sex, cum, explicit, lingerie, "
    "loli, child, kid, toddler, shota, teenager, aged down")

NEG_CHAR = NEG_COMMON + ", multiple girls, 2girls, another person, background people, simple background"
NEG_BG   = (NEG_COMMON + ", 1girl, 1boy, solo, person, people, human, crowd, face, "
                         "portrait, hands, character, silhouette of person, "
                         "distorted perspective, warped architecture, tiling")
NEG_DATASET = NEG_COMMON + ", multiple girls, 2girls, another person, background people"

# -------------------------------------------------- LoRA
ENABLE_LORA   = True
LORA_VER      = "v3"
LORA_WEIGHT   = 0.85
DATASET_RES   = 1024
LORA_SRC_N    = 48
LORA_SELECT_N = 24
LORA_REPEATS  = 10
LORA_EPOCHS   = 8
LORA_BATCH    = 1
LORA_DIM, LORA_ALPHA = 32, 16
LORA_TRAIN_TE = True

# -------------------------------------------------- 자동화 / 예산
PUSH_EVERY      = 20
AUTOSAVE_MIN    = 20
EST_CHAR_MIN    = 2.3       # extras 제거 후 실측 기준(생성 2분 + 저장)
EST_BG_MIN      = 2.0
EST_UI_MIN      = 1.0
EST_LORASRC_MIN = 1.6
EST_TRAIN_MIN   = 95.0
SMOKE_TEST      = os.environ.get("BS_SMOKE", "0") == "1"
PURGE_TAG       = "v3-nova19"

# -------------------------------------------------- 진단 / 로깅
DEBUG              = os.environ.get("BS_DEBUG", "1") == "1"
VERBOSE_GEN        = True
PROGRESS_POLL_SEC  = 5.0
HEARTBEAT_SEC      = 30.0
STALL_WARN_SEC     = 180.0
FORGE_LOG_TAIL     = True
FORGE_LOG_TAIL_SEC = 4.0
FORGE_LOG_TAIL_MAX = 3
GEN_TIMEOUT        = 1800
VRAM_LOG           = True

# =====================================================================
# CPU 폴백 자동 조정
# ---------------------------------------------------------------------
# GPU 주간 한도가 소진되어 CPU 로 돌 때 적용된다.
#
#  [절대 바꾸지 않는 것 = 화질]
#    CKPT / VAE / CLIP_SKIP / SAMPLER / SCHEDULER / STEPS / CFG /
#    WIDTH / HEIGHT / HR_SCALE / HR_STEPS / HR_DENOISE / HR_CFG /
#    BG_* / AD_* / OUT_W / OUT_H / WEBP_* / 프롬프트·네거티브 전체
#    -> 즉 CPU 로 뽑아도 GPU 결과물과 픽셀 규격·처리 순서가 동일하다.
#       (같은 seed 면 부동소수점 연산 순서 차이로 미세한 차이는 날 수 있으나
#        품질 등급은 동일하다)
#
#  [바꾸는 것 = 시간]
#    타임아웃 / 진단 주기 / 장당 소요 추정 / 푸시 주기
# =====================================================================
CPU_MODE = False
CPU_THREADS = 0
CPU_FAST_HIRES = False
ENABLE_LORA_TRAIN_ON_CPU = True

try:
    import bs_device as _D
    CPU_MODE = (_D.detect() == "cpu")
    CPU_THREADS = _D.threads()
except Exception:
    _D = None
    CPU_MODE = False

if CPU_MODE and _D is not None:
    _D.apply_env()
    try:
        _D.apply_forge()
    except Exception:
        pass

    # ---- 타임아웃 : CPU 1장은 30~60분이 걸린다 ----
    GEN_TIMEOUT        = int(os.environ.get("BS_CPU_GEN_TIMEOUT", "21600"))  # 6시간
    PROGRESS_POLL_SEC  = 20.0
    HEARTBEAT_SEC      = 120.0
    STALL_WARN_SEC     = 2400.0    # CPU 는 1스텝에 수십 초 걸린다
    FORGE_LOG_TAIL_SEC = 15.0
    FORGE_LOG_TAIL_MAX = 2
    VRAM_LOG           = False     # nvidia-smi 가 없으므로 RAM 표기로 대체

    # ---- extras 2차 정제 : CPU 에서는 절대 켜지 않는다 ----
    EXTRAS_ENABLE      = False
    EXTRAS_TIMEOUT     = 7200
    EXTRAS_SLOW_SEC    = 1800
    EXTRAS_SLOW_LIMIT  = 1
    LOCAL_SHARPEN      = True      # 라인 선예도는 언샵 마스크가 담당(GPU 와 동일)

    # ---- 저장 주기 : 1장이 오래 걸리므로 자주 커밋 ----
    PUSH_EVERY         = 2
    AUTOSAVE_MIN       = 15

    # ---- 소요 추정(분) : 실측이 쌓이면 bs_state.timing_avg 가 자동 대체 ----
    EST_CHAR_MIN       = float(os.environ.get("BS_CPU_EST_CHAR_MIN", "45"))
    EST_BG_MIN         = float(os.environ.get("BS_CPU_EST_BG_MIN", "40"))
    EST_UI_MIN         = float(os.environ.get("BS_CPU_EST_UI_MIN", "12"))
    EST_LORASRC_MIN    = float(os.environ.get("BS_CPU_EST_LORASRC_MIN", "35"))
    EST_TRAIN_MIN      = 100000.0   # CPU LoRA 학습은 사실상 불가능

    # 이미 학습된 LoRA 는 CPU 생성에도 그대로 적용된다(ENABLE_LORA 유지).
    # 학습 자체는 BS_CPU_TRAIN=1 을 주지 않는 한 건너뛴다.
    ENABLE_LORA_TRAIN_ON_CPU = os.environ.get("BS_CPU_TRAIN", "0") == "1"

    # ---- (선택) 화질을 조금 포기하고 속도를 얻고 싶을 때만 ----
    # BS_CPU_FAST_HIRES=1 이면 Hires 업스케일러를 ESRGAN -> Lanczos 로 바꾼다.
    # 장당 10~20분이 줄지만 텍스처 디테일이 떨어진다. 기본값은 OFF(=동일 화질).
    CPU_FAST_HIRES = os.environ.get("BS_CPU_FAST_HIRES", "0") == "1"
    if CPU_FAST_HIRES:
        UPSCALER_HIRES = "Lanczos"
