# -*- coding: utf-8 -*-
"""BLUE SUMMER v3 : 화질·학습·자동화 규격의 단일 원천."""
import os

# -------------------------------------------------- 모델
CKPT_NAME   = "novaAnimeXL_ilV190"
CKPT_FILE   = "novaAnimeXL_ilV190.safetensors"
CKPT_SHA256 = "FA486CAAFC330F133605D3C18B418D183812F14946631C6544BFB28730DB6D6F"
CKPT_PATH   = "/kaggle/temp/models/Stable-diffusion/" + CKPT_FILE
VAE_NAME    = "sdxl_vae.safetensors"
VAE_PATH    = "/kaggle/temp/models/VAE/" + VAE_NAME
CLIP_SKIP   = 2

# -------------------------------------------------- 업스케일러 (2종 상시)
UPSCALER_HIRES = "4x-UltraSharp"   # Hires fix 1차 : 텍스처·의상 디테일
UPSCALER_LINE  = "4x-AnimeSharp"   # extras 2차   : 라인아트 선예도
EXTRAS_BLEND   = 0.55
EXTRAS_SCALE   = 1.6

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
LORA_SRC_N    = 48          # 인당 후보 장수
LORA_SELECT_N = 24          # 자동 선별 장수
LORA_REPEATS  = 10
LORA_EPOCHS   = 8
LORA_BATCH    = 1
LORA_DIM, LORA_ALPHA = 32, 16
LORA_TRAIN_TE = True

# -------------------------------------------------- 자동화 / 예산
PUSH_EVERY      = 20        # N장마다 GitHub 푸시
AUTOSAVE_MIN    = 20
EST_CHAR_MIN    = 1.9       # 인물 1장 예상 소요(분) - 실측되면 자동 대체
EST_BG_MIN      = 1.6
EST_UI_MIN      = 1.0
EST_LORASRC_MIN = 1.3
EST_TRAIN_MIN   = 95.0      # LoRA 1인 학습 예상(분)
SMOKE_TEST      = os.environ.get("BS_SMOKE", "0") == "1"
PURGE_TAG       = "v3-nova19"
