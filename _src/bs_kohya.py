
# -*- coding: utf-8 -*-
import os, sys, json, time, glob, shutil, subprocess
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_state as ST, bs_common as P, bs_forge as F, bs_autosave as AS

ENV = json.load(open("/kaggle/temp/bs_env.json", encoding="utf-8"))
C, SEC = ENV["cfg"], ENV["secrets"]
VK, SDS = C["VENV_KOHYA"], C["SDS_DIR"]
PY = f"{VK}/bin/python"
CKPT = f"{C['MODEL_DIR']}/Stable-diffusion/bs_base.safetensors"
TOML = os.path.join(ST.BASE, "toml")
LOGD = os.path.join(ST.BASE, "logs")

def sh(cmd, cwd=None, show=True):
    p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    if show and out.strip():
        print(out[-2000:])
    return p.returncode, out

def setup():
    if os.path.exists(PY) and ST.is_done("kohya_env"):
        return True
    sh("pip install -q --no-input uv", show=False)
    sh("uv python install 3.10", show=False)
    if not os.path.exists(PY):
        rc, _ = sh(f"uv venv {VK} --python 3.10")
        if rc != 0:
            sh(f"python3.10 -m venv {VK}")
    U = f"uv pip install --python {PY} -q"
    if not os.path.isdir(os.path.join(SDS, ".git")):
        shutil.rmtree(SDS, ignore_errors=True)
        sh(f"git clone https://github.com/kohya-ss/sd-scripts.git {SDS}",
           cwd="/kaggle/temp")
    rc, out = sh(f'git rev-list -1 --before="{C["SDS_PIN_DATE"]}" origin/main',
                 cwd=SDS, show=False)
    if out.strip():
        sh(f"git checkout -q {out.strip()}", cwd=SDS, show=False)
    sh(f"{U} --index-url https://download.pytorch.org/whl/cu121 "
       f"torch==2.4.1 torchvision==0.19.1")
    sh(f"{U} 'accelerate==0.33.0' 'transformers==4.44.0' 'diffusers[torch]==0.25.0' "
       f"'safetensors==0.4.4' 'huggingface-hub==0.24.5' 'numpy==1.26.4' "
       f"'opencv-python-headless==4.10.0.84' einops ftfy toml voluptuous "
       f"'altair<5' 'rich' 'sentencepiece' 'imagesize' 'pytorch-lightning==1.9.0' "
       f"'library' 2>/dev/null; true")
    sh(f"{U} 'accelerate==0.33.0' 'transformers==4.44.0' 'diffusers[torch]==0.25.0' "
       f"'safetensors==0.4.4' 'numpy==1.26.4' einops ftfy toml voluptuous "
       f"imagesize sentencepiece")
    rc, _ = sh(f'{PY} -c "import torch;print(torch.__version__, torch.cuda.is_available())"')
    ST.mark("kohya_env", "done" if rc == 0 else "failed")
    return rc == 0

ARGS = (
 "--network_module networks.lora --network_dim 32 --network_alpha 16 "
 "--network_train_unet_only "
 "--learning_rate 1e-4 --unet_lr 1e-4 "
 "--optimizer_type Adafactor "
 '--optimizer_args "relative_step=False" "scale_parameter=False" "warmup_init=False" '
 "--lr_scheduler constant_with_warmup --lr_warmup_steps 100 "
 "--max_train_epochs 8 --save_every_n_epochs 4 "
 "--mixed_precision fp16 --save_precision fp16 "          # T4 는 bf16 불가
 "--gradient_checkpointing --cache_latents --cache_latents_to_disk "
 "--no_half_vae --sdpa --train_batch_size 1 "
 "--max_data_loader_n_workers 2 --persistent_data_loader_workers "
 "--min_snr_gamma 5 --noise_offset 0.0357 --seed 42 "
 "--max_token_length 225 --caption_extension .txt "
 "--save_model_as safetensors"
)

def hf_push(path):
    if not (SEC.get("HF_TOKEN") and SEC.get("HF_USER")):
        return
    try:
        from huggingface_hub import HfApi, create_repo
        rid = f"{SEC['HF_USER']}/bluesummer-lora"
        create_repo(rid, repo_type="dataset", private=True,
                    token=SEC["HF_TOKEN"], exist_ok=True)
        HfApi(token=SEC["HF_TOKEN"]).upload_file(
            path_or_fileobj=path, path_in_repo=os.path.basename(path),
            repo_id=rid, repo_type="dataset")
        print("   HF 업로드 완료:", os.path.basename(path))
    except Exception as e:
        print("   HF 업로드 실패:", e)

def train_one(c):
    out = os.path.join(ST.LORA_OUT, f"bs_{c.lower()}.safetensors")
    if os.path.exists(out):
        print(f"{c}: 이미 학습됨")
        return True
    toml = os.path.join(TOML, f"{c}.toml")
    if not os.path.exists(toml):
        print(f"{c}: toml 없음 — 건너뜀")
        return False
    os.makedirs(ST.LORA_OUT, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    cmd = (f"{VK}/bin/accelerate launch --num_cpu_threads_per_process 2 "
           f"--mixed_precision fp16 --num_processes 1 --gpu_ids 0 "
           f"sdxl_train_network.py "
           f"--pretrained_model_name_or_path {CKPT} "
           f"--dataset_config {toml} "
           f"--output_dir {ST.LORA_OUT} --output_name bs_{c.lower()} "
           f"--logging_dir {LOGD} {ARGS}")
    print(f"── {c} 학습 시작 (T4 기준 약 55분)")
    rc, log = sh(cmd, cwd=SDS, show=False)
    tail = "\n".join(log.strip().splitlines()[-25:])
    print(tail)
    ok = os.path.exists(out)
    ST.mark(f"lora_{c}", "done" if ok else "failed", tail[-300:])
    if ok:
        hf_push(out)
        AS.flush(f"lora {c}")
    return ok

def run(chars=None, deadline=None):
    if not setup():
        print("kohya 환경 구성 실패")
        return False
    F.stop()                      # VRAM 확보 (동시 구동은 반드시 OOM)
    time.sleep(10)
    for c in (chars or ST.CHARS):
        if deadline and time.time() > deadline - 60 * 60:
            print("남은 시간 부족 — 다음 세션에서 이어감")
            return False
        train_one(c)
    return True
