# -*- coding: utf-8 -*-
"""BLUE SUMMER v3.1 : 화질·학습·자동화 규격의 단일 원천.

v3.1 변경점 (extras 정체 사고 대응)
  · EXTRAS_ENABLE 기본 False  - 2차 ESRGAN 업스케일이 장당 4~8분을 잡아먹고
    512x768 최종본에는 거의 기여하지 않으므로 기본 경로에서 제외한다.
  · LOCAL_SHARPEN True        - LANCZOS 축소 직후 UnsharpMask 로 라인 선예도 확보.
  · EXTRAS_* 안전장치 추가    - 입력 픽셀 상한 / 단일 업스케일러 / 하드 타임아웃 /
    느리면 세션 내 자동 비활성화.
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
