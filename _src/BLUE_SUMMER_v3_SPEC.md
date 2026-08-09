# BLUE SUMMER v3 - 이미지 파이프라인 규격서

## 모델

- 체크포인트 : novaAnimeXL_ilV190.safetensors  (Civitai 376130 / version 2940478)
- SHA256     : FA486CAAFC330F133605D3C18B418D183812F14946631C6544BFB28730DB6D6F
- 베이스     : Illustrious SDXL / NoobAI EPS v1.1 병합
- 주의       : EPS 계열 -> v_parameterization / zero_terminal_snr 사용 금지

## 업스케일러 (2종 상시)

- Hires 1차 : 4x-UltraSharp
- extras 2차 : 4x-UltraSharp + 4x-AnimeSharp 블렌드 0.55 / 1.6x
- LoRA 데이터셋 : 4x-AnimeSharp 우세 블렌드 0.70~0.75

## 생성 파라미터

- Sampler Euler a / Schedule Automatic / Steps 26 / CFG 4.5
- Base 832x1216 -> Hires 1.5x (steps 12, denoise 0.42, cfg 4.0)
- Clip skip 2 / VAE sdxl_vae.safetensors
- 최종 512x768 WebP q92
- ADetailer face_yolov8s.pt(denoise 0.38) + hand_yolov8n.pt(denoise 0.3)

## 파일명 규칙

- 인물 c/<코드3><의상1><감정2>.webp  예: HRMW02.webp (대소문자 구분)
- 배경 bg/<코드>.webp / UI ui/<키>.webp
